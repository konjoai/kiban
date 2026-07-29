"""lib/defect_shapes.py: the four new Phase 14 mechanical detectors."""

from __future__ import annotations

from lib import defect_shapes


def test_missing_timeout_fires_with_no_timeout_token() -> None:
    added = 'requests.get("http://example.com")\n'
    hits = defect_shapes.scan_missing_timeout(added)
    assert hits
    assert "requests.get(" in hits[0]


def test_missing_timeout_silent_when_timeout_present() -> None:
    added = 'requests.get("http://example.com", timeout=5)\n'
    assert defect_shapes.scan_missing_timeout(added) == []


def test_missing_timeout_silent_with_no_external_call() -> None:
    added = "x = 1 + 2\n"
    assert defect_shapes.scan_missing_timeout(added) == []


def test_untyped_error_boundary_catches_bare_except() -> None:
    added = "try:\n    f()\nexcept:\n    pass\n"
    hits = defect_shapes.scan_untyped_error_boundary(added)
    assert any("python_bare_except" in h for h in hits)


def test_untyped_error_boundary_catches_rust_unwrap() -> None:
    hits = defect_shapes.scan_untyped_error_boundary("let x = risky().unwrap();\n")
    assert any("rust_unwrap" in h for h in hits)


def test_untyped_error_boundary_silent_on_typed_result() -> None:
    added = "let x: Result<i32, MyError> = risky();\n"
    assert defect_shapes.scan_untyped_error_boundary(added) == []


def test_missing_test_failure_path_fires_on_happy_path_only() -> None:
    diff = (
        "--- a/src/lib.rs\n+++ b/src/lib.rs\n@@\n"
        "+pub fn parse(x: &str) -> i32 { x.parse().unwrap() }\n"
        "--- a/tests/lib_tests.rs\n+++ b/tests/lib_tests.rs\n@@\n"
        '+fn test_parse_ok() { assert_eq!(parse("1"), 1); }\n'
    )
    hits = defect_shapes.scan_missing_test_failure_path(
        diff, ["src/lib.rs", "tests/lib_tests.rs"]
    )
    assert hits


def test_missing_test_failure_path_silent_when_failure_case_present() -> None:
    diff = (
        "--- a/src/lib.rs\n+++ b/src/lib.rs\n@@\n"
        "+pub fn parse(x: &str) -> i32 { x.parse().unwrap() }\n"
        "--- a/tests/lib_tests.rs\n+++ b/tests/lib_tests.rs\n@@\n"
        '+fn test_parse_ok() { assert_eq!(parse("1"), 1); }\n'
        "+#[should_panic]\n"
        '+fn test_parse_rejects_invalid() { parse("x"); }\n'
    )
    hits = defect_shapes.scan_missing_test_failure_path(
        diff, ["src/lib.rs", "tests/lib_tests.rs"]
    )
    assert hits == []


def test_missing_test_failure_path_silent_with_no_new_tests() -> None:
    diff = "--- a/src/lib.rs\n+++ b/src/lib.rs\n@@\n+pub fn f() {}\n"
    assert defect_shapes.scan_missing_test_failure_path(diff, ["src/lib.rs"]) == []


def test_missing_test_failure_path_silent_when_only_tests_touched() -> None:
    diff = (
        "--- a/tests/lib_tests.rs\n+++ b/tests/lib_tests.rs\n@@\n"
        '+fn test_parse_ok() { assert_eq!(parse("1"), 1); }\n'
    )
    assert defect_shapes.scan_missing_test_failure_path(diff, ["tests/lib_tests.rs"]) == []


# --- added_lines_excluding_test_scope (Phase 14, Phase 3 regression) ------------------
# Found live: a `.unwrap()`/`oneshot::channel()` inside a `mod tests { ... }` block
# scored identically to a real production error boundary / unbounded queue, because
# nothing distinguished test scaffolding from production code in the added-line scan.

def test_excludes_lines_after_an_added_mod_tests_marker() -> None:
    diff = (
        "diff --git a/a.rs b/a.rs\n--- a/a.rs\n+++ b/a.rs\n@@ -1,0 +2,6 @@\n"
        "+pub fn real_fn() { risky().unwrap(); }\n"
        "+\n"
        "+#[cfg(test)]\n"
        "+mod tests {\n"
        "+    fn helper() { risky().unwrap(); }\n"
        "+}\n"
    )
    stripped = defect_shapes.added_lines_excluding_test_scope(diff)
    assert "real_fn" in stripped
    assert "helper" not in stripped


def test_excludes_lines_whose_hunk_header_shows_mod_tests_context() -> None:
    # The `mod tests { ... }` opener itself is far above this hunk and never appears
    # in the diff body -- only in git's own hunk-header context annotation, exactly
    # the real shape found in Phase 14, Phase 3's live measurement.
    diff = (
        "diff --git a/a.rs b/a.rs\n--- a/a.rs\n+++ b/a.rs\n"
        "@@ -357,4 +429,6 @@ mod tests {\n"
        "+    fn new_test() {\n"
        "+        let store = open().await.unwrap();\n"
        "+    }\n"
    )
    stripped = defect_shapes.added_lines_excluding_test_scope(diff)
    assert "unwrap" not in stripped


def test_production_code_still_counted_when_no_test_marker_present() -> None:
    diff = (
        "diff --git a/a.rs b/a.rs\n--- a/a.rs\n+++ b/a.rs\n@@ -1,0 +2,1 @@\n"
        "+pub fn f() { risky().unwrap(); }\n"
    )
    stripped = defect_shapes.added_lines_excluding_test_scope(diff)
    assert "unwrap" in stripped
