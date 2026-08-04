"""Tests for section 1's uncovered-item extraction (lib/uncovered_items.py).

Rust mapping is tested against the real `konjo-ast-diff-rs --items` binary (built
release or debug -- skipped if neither exists, same convention `lib/backfill.py`'s own
tests use) so a schema drift in the Rust side is not silently invisible to Python
tests. Python mapping needs no external binary (`ast` is stdlib), tested directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib import uncovered_items as ui

KIBAN_ROOT = Path(__file__).resolve().parent.parent
AST_DIFF_BIN = ui.find_ast_diff_bin(KIBAN_ROOT)

requires_ast_diff_bin = pytest.mark.skipif(
    AST_DIFF_BIN is None, reason="konjo-ast-diff binary not built"
)


def test_parse_lcov_basic():
    text = """SF:src/a.rs
DA:1,3
DA:2,0
DA:3,0
end_of_record
SF:src/b.rs
DA:1,1
end_of_record
"""
    result = ui.parse_lcov(text)
    assert result == {"src/a.rs": {2, 3}, "src/b.rs": set()}


def test_parse_lcov_ignores_da_before_sf():
    text = "DA:1,0\nSF:src/a.rs\nDA:2,0\nend_of_record\n"
    result = ui.parse_lcov(text)
    assert result == {"src/a.rs": {2}}


def test_relativize_converts_absolute_paths_under_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    by_file = {str(repo / "crates/a/src/lib.rs"): {1, 2}}
    result = ui.relativize(by_file, repo)
    assert result == {"crates/a/src/lib.rs": {1, 2}}


def test_relativize_drops_paths_outside_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "elsewhere" / "x.rs"
    result = ui.relativize({str(outside): {1}}, repo)
    assert result == {}


def test_relativize_leaves_relative_paths_untouched(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    result = ui.relativize({"crates/a/src/lib.rs": {3}}, repo)
    assert result == {"crates/a/src/lib.rs": {3}}


def test_parse_coverage_json():
    data = {
        "files": {
            "pkg/mod.py": {"missing_lines": [4, 5, 9], "executed_lines": [1, 2, 3]},
            "pkg/other.py": {"missing_lines": []},
        }
    }
    result = ui.parse_coverage_json(data)
    assert result == {"pkg/mod.py": {4, 5, 9}, "pkg/other.py": set()}


def test_map_python_items_finds_enclosing_function(tmp_path: Path):
    src = (
        "def top_level():\n"
        "    x = 1\n"
        "    return x\n"
        "\n"
        "class Foo:\n"
        "    def method(self):\n"
        "        y = 2\n"
        "        return y\n"
    )
    f = tmp_path / "mod.py"
    f.write_text(src)
    items = ui.map_python_items(tmp_path, "mod.py", {2, 7})
    by_name = {i.qualified_name: i for i in items}
    assert by_name["top_level"].uncovered_lines == [2]
    assert by_name["Foo::method"].uncovered_lines == [7]


def test_map_python_items_no_hits_returns_empty(tmp_path: Path):
    f = tmp_path / "mod.py"
    f.write_text("def a():\n    return 1\n")
    assert ui.map_python_items(tmp_path, "mod.py", {100}) == []


def test_map_python_items_syntax_error_raises(tmp_path: Path):
    f = tmp_path / "bad.py"
    f.write_text("def a(:\n")
    with pytest.raises(ui.UncoveredItemsError):
        ui.map_python_items(tmp_path, "bad.py", {1})


def test_rank_items_orders_by_count_desc_then_file_then_line():
    items = [
        ui.UncoveredItem("b.rs", "f1", 1, 5, [1, 2]),
        ui.UncoveredItem("a.rs", "f2", 10, 15, [10, 11, 12]),
        ui.UncoveredItem("a.rs", "f3", 1, 5, [1, 2, 3]),
    ]
    ranked = ui.rank_items(items)
    assert [(i.file, i.start_line) for i in ranked] == [
        ("a.rs", 1),  # count 3, tie with a.rs@10 broken by ascending start line
        ("a.rs", 10),  # count 3
        ("b.rs", 1),  # count 2
    ]


@requires_ast_diff_bin
def test_map_rust_items_finds_enclosing_fn_and_method(tmp_path: Path):
    src = (
        "fn top_level() {\n"
        "    let x = 1;\n"
        "    let _ = x;\n"
        "}\n"
        "\n"
        "struct Foo;\n"
        "\n"
        "impl Foo {\n"
        "    fn method(&self) -> i32 {\n"
        "        let y = 2;\n"
        "        y\n"
        "    }\n"
        "}\n"
    )
    f = tmp_path / "mod.rs"
    f.write_text(src)
    items = ui.map_rust_items(tmp_path, "mod.rs", {2, 10}, ast_diff_binary=AST_DIFF_BIN)
    by_name = {i.qualified_name: i for i in items}
    assert by_name["top_level"].uncovered_lines == [2]
    assert by_name["Foo::method"].uncovered_lines == [10]


@requires_ast_diff_bin
def test_map_rust_items_parse_error_raises(tmp_path: Path):
    f = tmp_path / "bad.rs"
    f.write_text("fn a( {\n")
    with pytest.raises(ui.UncoveredItemsError):
        ui.map_rust_items(tmp_path, "bad.rs", {1}, ast_diff_binary=AST_DIFF_BIN)


@requires_ast_diff_bin
def test_extract_uncovered_items_mixed_languages(tmp_path: Path):
    (tmp_path / "mod.rs").write_text(
        "fn a() {\n    let x = 1;\n    let _ = x;\n}\n"
    )
    (tmp_path / "mod.py").write_text("def b():\n    return 1\n")
    uncovered_by_file = {"mod.rs": {2}, "mod.py": {2}}
    items = ui.extract_uncovered_items(tmp_path, uncovered_by_file, ast_diff_binary=AST_DIFF_BIN)
    assert {i.qualified_name for i in items} == {"a", "b"}


def test_extract_uncovered_items_skips_missing_file(tmp_path: Path):
    items = ui.extract_uncovered_items(tmp_path, {"gone.rs": {1}}, ast_diff_binary=None)
    assert items == []


def test_extract_uncovered_items_raises_without_binary_for_rust(tmp_path: Path):
    (tmp_path / "mod.rs").write_text("fn a() {}\n")
    # No ast_diff_binary passed -> .rs files are skipped (error is caught, not raised)
    items = ui.extract_uncovered_items(tmp_path, {"mod.rs": {1}}, ast_diff_binary=None)
    assert items == []
