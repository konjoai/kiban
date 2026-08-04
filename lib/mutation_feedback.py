"""Surviving-mutant -> assertion feedback formatter (review-pipeline Sprint P2, section 2).

Given a completed `cargo mutants --output <dir>` run's `outcomes.json`, emit one
structured feedback record per surviving mutant: the enclosing item's source, the
exact mutation applied (original -> replacement), the file:line, and the tests
that currently exercise that item and still passed against the mutant.

Reuses `outcomes.json`'s own schema directly -- confirmed live (Sprint P2 pre-flight
PF-2) that cargo-mutants already resolves each mutant to its enclosing item's
qualified name and full line span (`scenario.Mutant.function.function_name` /
`.function.span`), so this module does not need a second AST walker
(`konjo-ast-diff-rs`) the way section 1's coverage-line mapping does -- lcov/
coverage.py output carries no such item context, cargo-mutants' own report already
does.

"Tests that exercise this item" is a best-effort, file-scoped heuristic: every
`#[test]`/`#[tokio::test]`-annotated function inside a `mod tests { ... }` block in
the *same source file* as the mutated item. This is not precise per-test coverage
attribution (that needs per-test line coverage this pass does not compute) --
documented here rather than silently assumed exact. It is still useful signal: it
tells the model which existing assertions ran and passed despite the mutation,
narrowing "something is untested" to "these specific tests were too weak."

Output is capped (`cap`, default 20) and each record carries one line of rationale
(L5 in the review-pipeline plan) -- this module never emits a prose report.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

_TEST_FN_RE = re.compile(
    r"#\[\s*(?:tokio::)?test[^\]]*\]\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)"
)
_MOD_TESTS_RE = re.compile(r"#\[cfg\(test\)\]\s*(?:#\[[^\]]*\]\s*)*mod\s+tests\s*\{")


class MutationFeedbackError(Exception):
    """The outcomes.json report or a referenced source file could not be read."""


@dataclass
class FeedbackRecord:
    """One surviving mutant, formatted for a test-writing model turn."""

    file: str
    line: int
    function: str
    original: str
    replacement: str
    item_source: str
    tests_still_passing: list[str]
    rationale: str


def _read_lines(repo: Path, file: str) -> list[str]:
    path = repo / file
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise MutationFeedbackError(f"could not read {file}: {exc}") from exc


def _span_text(lines: list[str], start_line: int, end_line: int) -> str:
    # cargo-mutants spans are 1-indexed and inclusive.
    return "\n".join(lines[start_line - 1 : end_line])


def _tests_in_file(lines: list[str]) -> list[str]:
    """Every test fn name inside a `#[cfg(test)] mod tests { ... }` block.

    File-scoped, not item-scoped: a real per-item call-graph needs per-test
    coverage data this pass does not compute (see module docstring).
    """
    text = "\n".join(lines)
    m = _MOD_TESTS_RE.search(text)
    if not m:
        return []
    # Bound the scan to the tests module's own text, not the whole file, so a
    # helper fn or non-test item elsewhere in the file never gets swept in.
    depth = 0
    i = m.end() - 1  # index of the mod's opening brace
    start = i
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                body = text[start:j]
                return _TEST_FN_RE.findall(body)
    return _TEST_FN_RE.findall(text[start:])


def load_missed_mutants(mutants_out_dir: Path) -> list[dict]:
    """Every `MissedMutant` outcome from a `cargo mutants --output` run."""
    outcomes_path = mutants_out_dir / "outcomes.json"
    try:
        data = json.loads(outcomes_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise MutationFeedbackError(f"could not read {outcomes_path}: {exc}") from exc
    missed = []
    for o in data.get("outcomes", []):
        if o.get("summary") != "MissedMutant":
            continue
        mutant = o.get("scenario", {}).get("Mutant")
        if mutant is None:
            continue
        missed.append(mutant)
    return missed


def build_record(repo: Path, mutant: dict) -> FeedbackRecord:
    """One `FeedbackRecord` from a single `scenario.Mutant` dict."""
    file = mutant["file"]
    lines = _read_lines(repo, file)
    fn = mutant["function"]
    item_source = _span_text(lines, fn["span"]["start"]["line"], fn["span"]["end"]["line"])
    original_line = lines[mutant["span"]["start"]["line"] - 1].strip()
    tests = _tests_in_file(lines)
    rationale = (
        f"{len(tests)} existing test(s) in this file still pass with "
        f"`{mutant['replacement']}` in place of the original expression on "
        f"line {mutant['span']['start']['line']} -- none of them assert the "
        f"specific value this mutation would change."
    )
    return FeedbackRecord(
        file=file,
        line=mutant["span"]["start"]["line"],
        function=fn["function_name"],
        original=original_line,
        replacement=mutant["replacement"],
        item_source=item_source,
        tests_still_passing=tests,
        rationale=rationale,
    )


def format_feedback(repo: Path, mutants_out_dir: Path, *, cap: int = 20) -> list[dict]:
    """Structured feedback records for up to `cap` surviving mutants.

    Ranked by ascending line number within each file (stable, deterministic --
    matches section 1's own "deterministic ranking makes runs comparable" rule) so
    repeated runs against an unchanged report always produce the same capped set.
    Silent truncation is exactly what the plan's own no-silent-caps rule forbids,
    so the return value's length is the count actually available up to `cap`; a
    caller that wants to know whether truncation happened should compare against
    `len(load_missed_mutants(mutants_out_dir))`.
    """
    mutants = load_missed_mutants(mutants_out_dir)
    mutants.sort(key=lambda m: (m["file"], m["span"]["start"]["line"]))
    records = [build_record(repo, m) for m in mutants[:cap]]
    return [asdict(r) for r in records]
