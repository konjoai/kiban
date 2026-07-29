"""Phase 14, Phase 2: mechanical detectors for defect-taxonomy classes with no existing
kiban detector to reuse.

`evals/genfixtures.py`'s `DEFECT_TAXONOMY` had 3 of 8 classes mechanically classified at
1.8.0 (`secret_in_source`, `unconfigured_permit_branch`, `untrusted_input_reaching_exec`)
by reusing `lib.redact`, `lib.polarity`, `lib.threat` verbatim. This module adds the
detectors for the classes where reuse was possible or a new hint-shaped scan was cheap
and honest to write. It does NOT attempt every remaining class -- `raw_index_external_input`
stays `None` (see `evals/genfixtures.py`'s `classify_diff` docstring for why: it needs
dataflow/taint tracking a line-diff regex scan cannot provide without an unacceptable
false-positive rate for a class whose whole point is a *counted* measurement, not a
human-reviewed hint).

Same carried limit as `lib.threat.classify` and `lib.polarity.lint_text` applied to a
diff: these are line-shaped hints over the added-line text (or the raw diff, where a
hunk needs to be told test-file from production-file), not a full post-change parse.
Under-triggering is the safer failure for a *count* used to compare contexts (it costs
recall, not a false "the candidate helped"); over-triggering is the one to watch, so
each pattern here is narrower than `lib.threat`'s hint style, not broader.
"""

from __future__ import annotations

import re

# A Rust (or Python/TS) test marker: once seen in a file's diff section, every line
# after it is presumed test code for the rest of that file. Rust convention puts
# `mod tests { ... }` at a file's end; a per-attribute check (`#[test]`,
# `#[tokio::test]`) would need real brace-depth scope tracking to know where a single
# test function ends and production code resumes, which this line-scanner does not
# attempt -- `mod tests` is the one marker common enough, and reliably tail-of-file
# enough in practice, to make "stop scanning for production defects here" a safe
# default. Found live, not designed in the abstract: Phase 14, Phase 3's real
# `lopi-whatsapp-cost-command` measurement flagged `.unwrap()` calls inside a
# `#[tokio::test]` body every single run, in every context tested, because nothing
# distinguished them from a production error boundary -- the org's own real
# convention ("No unwrap()/expect() outside tests") explicitly permits exactly what
# this was flagging.
_TEST_SCOPE_MARKER_RE = re.compile(r"mod\s+tests\s*\{|#\[cfg\(test\)\]")


def added_lines_excluding_test_scope(diff_text: str) -> str:
    """The added-line text of a diff, stripped of the `+`, with every line inside a
    `mod tests { ... }` / `#[cfg(test)]` scope dropped. Under-triggers by design (a
    `#[test]` fn mixed into production code with neither marker still counts) -- the
    safer failure for a count Phase 3 compares across contexts, per this module's own
    docstring.

    Two signals, since either alone misses real cases: (1) a unified diff's hunk
    header (`@@ ... @@ <enclosing context>`) often names the enclosing scope git found
    for that hunk -- `@@ -357,4 +429,74 @@ mod tests {` means every line in that hunk
    is already inside `mod tests`, even though the `mod tests {` line itself is far
    above the hunk and never appears in the diff body at all (confirmed live: this is
    exactly why an earlier version of this function, which only scanned diff *body*
    lines for the marker, missed every hit in Phase 14, Phase 3's real
    `lopi-whatsapp-cost-command` measurement -- the file's `mod tests {` predates this
    diff). (2) Once an ADDED line itself opens `mod tests { ... }` or `#[cfg(test)]`,
    every added line for the rest of that file's diff section is presumed test code
    too (the tail-of-file convention named in this module's docstring).
    """
    in_test = False
    kept: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            in_test = False
            continue
        if line.startswith("@@"):
            trailer = line.split("@@", 2)[-1]
            if _TEST_SCOPE_MARKER_RE.search(trailer):
                in_test = True
            continue
        if in_test:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:]
            if _TEST_SCOPE_MARKER_RE.search(content):
                in_test = True
                continue
            kept.append(content)
    return "\n".join(kept)


# --- missing_timeout -------------------------------------------------------------
# A call site shaped like an external call (network, subprocess) with no `timeout`
# token anywhere in the same diff's added-line text. Diff-scoped, not call-site-scoped
# (the same approximation `classify_diff` already accepts for polarity/threat): a
# timeout configured on a client built a few lines above the call, both added in this
# diff, still satisfies the check, since both lines are in `added_text`. A timeout
# configured in a file this diff does NOT touch will not be seen -- a false positive
# this scan can produce, named rather than hidden.
_EXTERNAL_CALL_RE = re.compile(
    r"(?i)\b("
    r"reqwest::(Client::new|get)\(|requests\.(get|post|put|delete)\(|"
    r"subprocess\.(run|Popen|call|check_output)\(|Command::new\(|"
    r"\.exec\(|child_process\.(spawn|exec)\(|axios\.(get|post)\(|fetch\("
    r")"
)
_TIMEOUT_TOKEN_RE = re.compile(r"(?i)timeout")


def scan_missing_timeout(added_text: str) -> list[str]:
    hits = sorted({m.group(0) for m in _EXTERNAL_CALL_RE.finditer(added_text)})
    if not hits or _TIMEOUT_TOKEN_RE.search(added_text):
        return []
    return [f"external call added with no 'timeout' token anywhere in the diff: {h}" for h in hits]


# --- untyped_error_boundary -------------------------------------------------------
# A caught or returned error whose type carries no information: Python's bare or
# `Exception`-wide except, Rust's `.unwrap()`/`.expect(`/a `Box<dyn Error>` boundary
# return, TypeScript's untyped `catch`.
_UNTYPED_ERROR_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("python_bare_except", re.compile(r"^\s*except\s*:", re.MULTILINE)),
    ("python_except_exception", re.compile(r"\bexcept\s+Exception\b")),
    ("rust_unwrap", re.compile(r"\.unwrap\(\)")),
    ("rust_expect", re.compile(r"\.expect\(")),
    ("rust_boxed_dyn_error", re.compile(r"Box<dyn\s+(?:std::error::)?Error>")),
    ("ts_catch_any", re.compile(r"catch\s*\(\s*\w+\s*:\s*any\s*\)")),
    ("ts_catch_untyped", re.compile(r"catch\s*\(\s*\w+\s*\)\s*\{")),
]


def scan_untyped_error_boundary(added_text: str) -> list[str]:
    hits: list[str] = []
    for name, pat in _UNTYPED_ERROR_PATTERNS:
        if pat.search(added_text):
            hits.append(f"untyped error boundary shape: {name}")
    return hits


# --- missing_test_failure_path -----------------------------------------------------
# Approximate, diff-scoped version of the same question `gate_can_fail` asks at merge
# time with a real rejects-test run: does this change's test coverage include a
# failure/rejection case, or only the happy path? Fires only when the diff both (a)
# changes non-test production code (so new behavior actually shipped) and (b) adds at
# least one new test function, none of which is shaped like a failure-path assertion.
# A diff that touches no test file at all is a `missing_test_failure_path` candidate
# too in spirit, but that is exactly what `gate_can_fail`'s rejects-test contract
# already owns at merge time -- this scan only adds signal for the case that contract
# does not see: tests were added, but all of them assert the success case.
_TEST_PATH_RE = re.compile(r"(?i)(^|/)(test_|tests?/|_test\.|_tests\.|\.test\.|\.spec\.)")
_NEW_TEST_FN_RE = re.compile(
    r"^\+\s*(?:def\s+test_\w+|(?:pub\s+)?(?:async\s+)?fn\s+test_\w+|"
    r"(?:it|test)\(['\"])",
    re.MULTILINE,
)
_FAILURE_SHAPE_RE = re.compile(
    r"(?i)(fail|reject|invalid|error|panic|raises|throw|should_panic|assert_err|"
    r"expect.*\.(reject|toThrow))"
)


def scan_missing_test_failure_path(diff_text: str, changed_paths: list[str]) -> list[str]:
    touches_production = any(not _TEST_PATH_RE.search(p) for p in changed_paths)
    if not touches_production:
        return []
    new_test_lines = [
        line
        for line in diff_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    added_test_fns = _NEW_TEST_FN_RE.findall("\n".join(new_test_lines))
    if not added_test_fns:
        return []
    has_failure_case = any(_FAILURE_SHAPE_RE.search(line) for line in new_test_lines)
    if has_failure_case:
        return []
    return [
        f"{len(added_test_fns)} new test function(s) added alongside a production change, "
        "none shaped like a failure/rejection case"
    ]
