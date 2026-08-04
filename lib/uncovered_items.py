"""Section 1 (review-pipeline Sprint P2b): uncovered-item extraction.

Maps each repo's own native coverage output -- lcov for lopi (`cargo llvm-cov nextest
--lcov`), coverage.py's own JSON report for squish (`coverage json`) -- to the
enclosing function/method, and ranks items by uncovered-line count descending (ties
broken by file, then item start line, so repeated runs against an unchanged tree
produce a stable, comparable order). Never a third coverage tool, per the same rule
`kiban bench` already applies (`lib/bench.py` module docstring).

Rust mapping shells out to `konjo-ast-diff-rs`'s `--items` mode (real line spans via
`syn`'s `Spanned` trait, confirmed live against proc-macro2's `span-locations` feature
in Sprint P2b PF-1b -- see that crate's Cargo.toml comment). This is the same crate
`lib/backfill.py` already shells out to for AST delta; `--items` is a second, additive
output mode on the same binary rather than a second parser.

Python mapping does not need an external tool at all: the standard library's `ast`
module already carries real `lineno`/`end_lineno` on every `FunctionDef`/
`AsyncFunctionDef` node, so `map_python_items` parses in-process.
"""

from __future__ import annotations

import ast
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_AST_DIFF_BIN_CANDIDATES = (
    "packages/konjo-ast-diff-rs/target/release/konjo-ast-diff",
    "packages/konjo-ast-diff-rs/target/debug/konjo-ast-diff",
)


class UncoveredItemsError(Exception):
    """Coverage report or a referenced source file could not be read/parsed."""


@dataclass
class UncoveredItem:
    """One item (fn/method) with at least one uncovered line."""

    file: str
    qualified_name: str
    start_line: int
    end_line: int
    uncovered_lines: list[int] = field(default_factory=list)

    @property
    def uncovered_count(self) -> int:
        return len(self.uncovered_lines)

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "qualified_name": self.qualified_name,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "uncovered_lines": self.uncovered_lines,
            "uncovered_count": self.uncovered_count,
        }


def find_ast_diff_bin(kiban_root: Path) -> Path | None:
    for cand in _AST_DIFF_BIN_CANDIDATES:
        p = kiban_root / cand
        if p.exists():
            return p
    return None


def parse_lcov(text: str) -> dict[str, set[int]]:
    """file -> set of zero-hit line numbers, from `cargo llvm-cov ... --lcov` output.

    Standard lcov tracefile grammar: `SF:<path>` opens a record, `DA:<line>,<hits>`
    lines follow, `end_of_record` closes it. A `DA` line before any `SF` is ignored
    (malformed input, not this parser's job to reject).
    """
    result: dict[str, set[int]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("SF:"):
            current = line[3:].strip()
            result.setdefault(current, set())
        elif line.startswith("DA:") and current is not None:
            parts = line[3:].split(",")
            if len(parts) < 2:
                continue
            try:
                lineno, hits = int(parts[0]), int(parts[1])
            except ValueError:
                continue
            if hits == 0:
                result[current].add(lineno)
        elif line.strip() == "end_of_record":
            current = None
    return result


def relativize(by_file: dict[str, set[int]], repo: Path) -> dict[str, set[int]]:
    """Normalize any absolute `SF:` paths to repo-relative -- `cargo llvm-cov`'s own
    lcov output uses absolute paths (confirmed live, Sprint P2b section 1 verify run),
    while the rest of this module (and `mutation_feedback.py`'s `FeedbackRecord.file`)
    treats file keys as repo-relative. A path outside `repo` is dropped, not raised:
    lcov can legitimately reference build-script-generated files outside the tree.
    """
    repo = repo.resolve()
    out: dict[str, set[int]] = {}
    for f, lines in by_file.items():
        p = Path(f)
        if p.is_absolute():
            try:
                f = str(p.resolve().relative_to(repo))
            except ValueError:
                continue
        out[f] = lines
    return out


def parse_coverage_json(data: dict) -> dict[str, set[int]]:
    """file -> set of missing line numbers, from `coverage json`'s own report shape:
    `{"files": {"<path>": {"missing_lines": [...], ...}, ...}}`.
    """
    result: dict[str, set[int]] = {}
    for path, info in data.get("files", {}).items():
        result[path] = set(info.get("missing_lines", []))
    return result


def _run_ast_diff_items(binary: Path, source: str) -> list[dict]:
    try:
        proc = subprocess.run(
            [str(binary), "--items"],
            input=json.dumps({"source": source}),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise UncoveredItemsError(f"{binary} --items timed out: {exc}") from exc
    if proc.returncode != 0:
        raise UncoveredItemsError(f"{binary} --items failed (exit {proc.returncode}): {proc.stderr}")
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise UncoveredItemsError(f"{binary} --items produced bad JSON: {exc}") from exc
    if out.get("parse_error"):
        raise UncoveredItemsError(f"parse error: {out['parse_error']}")
    return out["items"]


def map_rust_items(
    repo: Path, file: str, uncovered_lines: set[int], *, ast_diff_binary: Path
) -> list[UncoveredItem]:
    source = (repo / file).read_text(encoding="utf-8")
    raw_items = _run_ast_diff_items(ast_diff_binary, source)
    out = []
    for it in raw_items:
        hit = sorted(ln for ln in uncovered_lines if it["start_line"] <= ln <= it["end_line"])
        if hit:
            out.append(UncoveredItem(
                file=file,
                qualified_name=it["qualified_name"],
                start_line=it["start_line"],
                end_line=it["end_line"],
                uncovered_lines=hit,
            ))
    return out


def _qualified_name(node: ast.AST, class_stack: list[str]) -> str:
    prefix = "".join(f"{c}::" for c in class_stack)
    return f"{prefix}{node.name}"


def map_python_items(repo: Path, file: str, uncovered_lines: set[int]) -> list[UncoveredItem]:
    """Python needs no external tool: `ast` carries real `lineno`/`end_lineno`."""
    source = (repo / file).read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=file)
    except SyntaxError as exc:
        raise UncoveredItemsError(f"{file}: {exc}") from exc

    out: list[UncoveredItem] = []

    def visit(node: ast.AST, class_stack: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = child.lineno
                end = child.end_lineno or start
                hit = sorted(ln for ln in uncovered_lines if start <= ln <= end)
                if hit:
                    out.append(UncoveredItem(
                        file=file,
                        qualified_name=_qualified_name(child, class_stack),
                        start_line=start,
                        end_line=end,
                        uncovered_lines=hit,
                    ))
                # Do not descend into a nested def's own body for a second, inner
                # item -- each uncovered line belongs to its innermost enclosing
                # def, and Python code rarely nests defs meaningfully for this
                # purpose; still recurse for classes nested inside.
                visit(child, class_stack)
            elif isinstance(child, ast.ClassDef):
                visit(child, [*class_stack, child.name])
            else:
                visit(child, class_stack)

    visit(tree, [])
    return out


def rank_items(items: list[UncoveredItem]) -> list[UncoveredItem]:
    """Uncovered-line count descending; ties broken by file, then start line --
    deterministic so repeated runs against an unchanged tree are comparable.
    """
    return sorted(items, key=lambda i: (-i.uncovered_count, i.file, i.start_line))


def extract_uncovered_items(
    repo: Path,
    uncovered_by_file: dict[str, set[int]],
    *,
    ast_diff_binary: Path | None = None,
) -> list[UncoveredItem]:
    """Rank uncovered items across every file in `uncovered_by_file`.

    `.rs` files route through `konjo-ast-diff-rs --items` (`ast_diff_binary` required);
    `.py` files route through the stdlib `ast` module directly. Any other extension,
    or a file that no longer exists on disk, is skipped rather than raising -- a stale
    coverage report referencing a since-deleted file is not this function's job to
    reject; it just contributes nothing to the ranking.
    """
    all_items: list[UncoveredItem] = []
    for file, lines in uncovered_by_file.items():
        if not lines:
            continue
        path = repo / file
        if not path.exists():
            continue
        try:
            if file.endswith(".rs"):
                if ast_diff_binary is None:
                    raise UncoveredItemsError("ast_diff_binary required for .rs files")
                all_items.extend(map_rust_items(repo, file, lines, ast_diff_binary=ast_diff_binary))
            elif file.endswith(".py"):
                all_items.extend(map_python_items(repo, file, lines))
        except UncoveredItemsError:
            continue
    return rank_items(all_items)
