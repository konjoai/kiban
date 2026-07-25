"""Unit tests for the keystone review interface (lib/review.py).

All deterministic: a ScriptedBackend stands in for the Claude CLI, so these test the
plumbing (selection, parsing, fingerprint dedup, the confidence gate) without any
network call.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from lib import diff_scope, review
from lib.review import ClaudeCLIBackend, Finding, ScriptedBackend, review_diff

SQUISH = {
    "stack": ["python", "mlx"],
    "specialists": ["numerics", "memory-bandwidth", "concurrency", "api-surface"],
}

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
    # highest confidence kept, both specialists recorded. Pinned to runs=1 -- this
    # is about cross-specialist dedup, not the recurrence-confidence bump.
    backend = ScriptedBackend(
        {
            "numerics": _finding_json(confidence=7, line=14),
            "red-team": _finding_json(confidence=9, line=99),
        }
    )
    result = review_diff(MLX_DIFF, SQUISH, backend=backend, runs=1, mode="deep")
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


def test_live_default_is_multi_run_and_clean_diff_still_passes() -> None:
    # The blocking review must not be weaker than the eval harness that validates it
    # (evals/runner.py's DEFAULT_RUNS == 3): the live default matches.
    assert review.DEFAULT_LIVE_RUNS > 1
    backend = ScriptedBackend({})
    result = review_diff(MLX_DIFF, SQUISH, backend=backend, mode="deep")
    assert result.runs == review.DEFAULT_LIVE_RUNS
    assert len(result.per_run) == review.DEFAULT_LIVE_RUNS
    # A clean diff (no findings on any run) still passes clean at the new default.
    assert result.findings == []
    assert not result.incomplete


class _FlakyBackend:
    """Simulates a reviewer LLM that only catches a real defect on some passes:
    `numerics` reports the finding on its first `hits` calls then goes quiet; every
    other specialist (e.g. red-team) always reports nothing, so it can't contaminate
    the recurrence count being tested."""

    def __init__(self, hits: int, reply: str) -> None:
        self.hits = hits
        self.reply = reply
        self.calls: dict[str, int] = {}

    def dispatch(
        self, specialist: str, system_prompt: str, user_prompt: str, *, model: str | None = None
    ) -> str | None:
        n = self.calls.get(specialist, 0) + 1
        self.calls[specialist] = n
        if specialist == "numerics" and n <= self.hits:
            return self.reply
        return "NO FINDINGS"


def test_union_keeps_a_finding_seen_on_only_one_of_n_runs() -> None:
    # Recall is the priority on the blocking path: a finding a noisy reviewer only
    # caught once out of three runs must still surface, not be silently dropped.
    backend = _FlakyBackend(hits=1, reply=_finding_json(confidence=6))
    result = review_diff(MLX_DIFF, SQUISH, backend=backend, runs=3, mode="deep")
    assert result.has("numerics", "CRITICAL")
    finding = next(f for f in result.findings if f.category == "numerics")
    assert finding.recurrence == 1
    # No confidence bump for a single-run finding -- it isn't demoted either.
    assert finding.confidence == 6


def test_recurrence_raises_confidence_proportionally_to_agreement() -> None:
    def _confidence_for(hits: int) -> int:
        backend = _FlakyBackend(hits=hits, reply=_finding_json(confidence=6))
        result = review_diff(MLX_DIFF, SQUISH, backend=backend, runs=3, mode="deep")
        return next(f for f in result.findings if f.category == "numerics").confidence

    once, majority, unanimous = _confidence_for(1), _confidence_for(2), _confidence_for(3)
    # A finding caught every run is marked more confident than one caught on a
    # majority, which in turn beats one caught on a single run -- none are dropped.
    assert unanimous > majority > once == 6


def test_malformed_reply_is_zero_findings_not_crash() -> None:
    backend = ScriptedBackend({"numerics": "[ {bad json"})
    result = review_diff(MLX_DIFF, SQUISH, backend=backend, mode="deep")
    # numerics dispatched but contributed nothing; no crash.
    rep = {r.name: r for r in result.specialist_reports}
    assert rep["numerics"].dispatched
    assert all(f.specialist != "numerics" for f in result.findings)
    # Malformed content is a completed dispatch, not a failure -- distinct from a
    # backend that never returned anything at all.
    assert rep["numerics"].completed
    assert not result.incomplete


def test_cli_backend_timeout_returns_none_not_empty_text(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_a: object, **_kw: object) -> None:
        raise subprocess.TimeoutExpired(cmd=["claude"], timeout=1)

    monkeypatch.setattr(subprocess, "run", _raise)
    backend = ClaudeCLIBackend(timeout=1)
    assert backend.dispatch("numerics", "sys", "usr") is None


def test_cli_backend_oserror_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_a: object, **_kw: object) -> None:
        raise OSError("claude binary not found")

    monkeypatch.setattr(subprocess, "run", _raise)
    backend = ClaudeCLIBackend()
    assert backend.dispatch("numerics", "sys", "usr") is None


def test_cli_backend_nonzero_exit_returns_none_even_with_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A non-zero exit is a failure, not a warning: today's bug is that partial stdout
    # is returned anyway (and read as valid findings). It must not be.
    class _FakeProc:
        returncode = 1
        stdout = _finding_json()

    monkeypatch.setattr(subprocess, "run", lambda *_a, **_kw: _FakeProc())
    backend = ClaudeCLIBackend()
    assert backend.dispatch("numerics", "sys", "usr") is None


def test_cli_backend_clean_exit_returns_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeProc:
        returncode = 0
        stdout = "NO FINDINGS"

    monkeypatch.setattr(subprocess, "run", lambda *_a, **_kw: _FakeProc())
    backend = ClaudeCLIBackend()
    assert backend.dispatch("numerics", "sys", "usr") == "NO FINDINGS"


def test_failed_specialist_marks_incomplete_not_clean() -> None:
    # numerics never completes (even the retry fails): the report must say so, and
    # the result must be INCOMPLETE, not a clean zero-findings pass.
    backend = ScriptedBackend({}, fail_always={"numerics"})
    result = review_diff(MLX_DIFF, SQUISH, backend=backend, mode="deep")
    rep = {r.name: r for r in result.specialist_reports}
    assert rep["numerics"].dispatched  # an attempt was made
    assert not rep["numerics"].completed
    assert rep["numerics"].failed
    assert result.incomplete
    assert result.findings == []


def test_transient_failure_retries_and_recovers() -> None:
    # numerics fails once (a transient timeout) then succeeds on retry: the result
    # must be a normal verdict, not INCOMPLETE, and the retry's finding must count.
    # Pinned to runs=1: this test is about retry-then-recover semantics within a
    # single pass, independent of the multi-run default.
    backend = ScriptedBackend({"numerics": _finding_json()}, fail_once={"numerics"})
    result = review_diff(MLX_DIFF, SQUISH, backend=backend, runs=1, mode="deep")
    rep = {r.name: r for r in result.specialist_reports}
    assert rep["numerics"].dispatches == 2  # the failed attempt plus the retry
    assert rep["numerics"].completed
    assert not rep["numerics"].failed
    assert not result.incomplete
    assert result.has("numerics", "CRITICAL")


def test_clean_review_with_zero_findings_is_not_incomplete() -> None:
    # A specialist that completes and genuinely finds nothing must stay exactly as
    # easy to pass as before -- INCOMPLETE is reserved for a failed dispatch.
    backend = ScriptedBackend({})
    result = review_diff(MLX_DIFF, SQUISH, backend=backend, mode="deep")
    assert not result.incomplete
    assert result.findings == []


def test_finding_fingerprint_ignores_line() -> None:
    # Same path and issue on different lines (and different summary whitespace/case)
    # collapse to one fingerprint; the line number is deliberately not part of it.
    a = Finding("HIGH", 8, "squish/x.py", 10, "numerics", "same issue here", "fix", "numerics")
    b = Finding("HIGH", 8, "squish/x.py", 999, "numerics", "Same  issue   here.", "fix", "numerics")
    assert a.fingerprint == b.fingerprint
    # A different path is a different finding.
    c = Finding("HIGH", 8, "squish/y.py", 10, "numerics", "same issue here", "fix", "numerics")
    assert a.fingerprint != c.fingerprint
