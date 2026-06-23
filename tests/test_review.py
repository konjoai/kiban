"""Unit tests for the keystone review interface (lib/review.py).

All deterministic: a ScriptedBackend stands in for the Claude CLI, so these test the
plumbing (selection, parsing, fingerprint dedup, the confidence gate) without any
network call.
"""

from __future__ import annotations

import json

from lib import diff_scope, review
from lib.review import Finding, ScriptedBackend, review_diff

SQUISH = {"specialists": ["numerics", "memory-bandwidth", "concurrency", "api-surface"]}

MLX_DIFF = """diff --git a/squish/kv_cache.py b/squish/kv_cache.py
--- a/squish/kv_cache.py
+++ b/squish/kv_cache.py
@@ -1,3 +1,3 @@
-self.k = mx.concatenate([self.k, keys], axis=2)
+self.k = mx.concatenate([self.k, keys.astype(mx.float32)], axis=2)
"""

DOCS_DIFF = """diff --git a/docs/guide.md b/docs/guide.md
--- a/docs/guide.md
+++ b/docs/guide.md
@@ -1 +1 @@
-old line
+new line
"""


def _finding_json(**kw: object) -> str:
    base = {
        "severity": "CRITICAL",
        "confidence": 9,
        "path": "squish/kv_cache.py",
        "line": 14,
        "category": "numerics",
        "summary": "fp16 KV cache silently promoted to fp32",
        "fix": "keep the cache in fp16",
    }
    base.update(kw)
    return json.dumps([base])


def test_changed_files_and_scope_mlx() -> None:
    files = review.changed_files(MLX_DIFF)
    assert files == ["squish/kv_cache.py"]
    flags = diff_scope.scope(files, MLX_DIFF)
    assert flags["SCOPE_PYTHON"] and flags["SCOPE_MLX"]
    assert diff_scope.has_code(flags)


def test_docs_only_runs_zero_code_specialists() -> None:
    backend = ScriptedBackend({})
    result = review_diff(DOCS_DIFF, SQUISH, backend=backend)
    assert result.selected == []
    assert backend.calls == []  # nothing dispatched
    flags = result.scope_flags
    assert flags["SCOPE_DOCS"] and not diff_scope.has_code(flags)


def test_mlx_selects_numerics_and_redteam_last() -> None:
    backend = ScriptedBackend({"numerics": _finding_json()})
    result = review_diff(MLX_DIFF, SQUISH, backend=backend)
    assert "numerics" in result.selected
    assert result.selected[-1] == "red-team"  # red-team always last
    assert result.has("numerics", "CRITICAL")


def test_confidence_gate_daily_drops_low_deep_keeps() -> None:
    low = ScriptedBackend({"numerics": _finding_json(confidence=5)})
    daily = review_diff(MLX_DIFF, SQUISH, backend=low, mode="daily")
    assert daily.findings == []  # 5 < daily threshold 8

    low2 = ScriptedBackend({"numerics": _finding_json(confidence=5)})
    deep = review_diff(MLX_DIFF, SQUISH, backend=low2, mode="deep")
    assert deep.has("numerics", "CRITICAL")  # 5 >= deep threshold 2


def test_fingerprint_dedup_keeps_highest_and_records_specialists() -> None:
    # numerics and red-team report the same issue on different lines: one finding,
    # highest confidence kept, both specialists recorded.
    backend = ScriptedBackend(
        {
            "numerics": _finding_json(confidence=7, line=14),
            "red-team": _finding_json(confidence=9, line=99),
        }
    )
    result = review_diff(MLX_DIFF, SQUISH, backend=backend, mode="deep")
    same = [f for f in result.findings if f.category == "numerics"]
    assert len(same) == 1
    assert same[0].confidence == 9
    assert set(same[0].specialists) == {"numerics", "red-team"}


def test_parse_is_defensive() -> None:
    assert review.parse_findings("NO FINDINGS", "numerics", "numerics") == []
    assert review.parse_findings("", "numerics", "numerics") == []
    assert review.parse_findings("not json at all {", "numerics", "numerics") == []
    fenced = "```json\n" + _finding_json() + "\n```"
    parsed = review.parse_findings(fenced, "numerics", "numerics")
    assert len(parsed) == 1 and parsed[0].severity == "CRITICAL"


def test_per_run_recorded_for_multiple_runs() -> None:
    backend = ScriptedBackend({"numerics": _finding_json()})
    result = review_diff(MLX_DIFF, SQUISH, backend=backend, runs=3)
    assert result.runs == 3
    assert len(result.per_run) == 3
    assert all(any(f.category == "numerics" for f in run) for run in result.per_run)


def test_malformed_reply_is_zero_findings_not_crash() -> None:
    backend = ScriptedBackend({"numerics": "[ {bad json"})
    result = review_diff(MLX_DIFF, SQUISH, backend=backend, mode="deep")
    # numerics dispatched but contributed nothing; no crash.
    rep = {r.name: r for r in result.specialist_reports}
    assert rep["numerics"].dispatched
    assert all(f.specialist != "numerics" for f in result.findings)


def test_finding_fingerprint_ignores_line() -> None:
    # Same path and issue on different lines (and different summary whitespace/case)
    # collapse to one fingerprint; the line number is deliberately not part of it.
    a = Finding("HIGH", 8, "squish/x.py", 10, "numerics", "same issue here", "fix", "numerics")
    b = Finding("HIGH", 8, "squish/x.py", 999, "numerics", "Same  issue   here.", "fix", "numerics")
    assert a.fingerprint == b.fingerprint
    # A different path is a different finding.
    c = Finding("HIGH", 8, "squish/y.py", 10, "numerics", "same issue here", "fix", "numerics")
    assert a.fingerprint != c.fingerprint
