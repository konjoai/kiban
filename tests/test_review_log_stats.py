"""Tests for the review-log writer and specialist-stats fold.

The log must exist before stats can read it; stats must respect the sample-size floor
and the NEVER_GATE insurance set; and a HIGH secret in a review record must be blocked
by the store (inherited behavior).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib import jsonl_store, review_log, specialist_stats
from lib.review import Finding, ReviewResult, SpecialistReport


def _result(findings: list[Finding], reports: list[SpecialistReport]) -> ReviewResult:
    return ReviewResult(
        findings=findings,
        per_run=[findings],
        specialist_reports=reports,
        runs=1,
        mode="daily",
        threshold=8,
        selected=[r.name for r in reports],
        scope_flags={"SCOPE_PYTHON": True},
    )


@pytest.fixture()
def state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("KONJO_STATE_DIR", str(tmp_path))
    return tmp_path


def test_log_written_then_stats_reads(state: Path) -> None:
    # 12 reviews where numerics finds nothing and concurrency finds one each.
    for _ in range(12):
        reports = [
            SpecialistReport(name="numerics", dispatches=1, n_findings=0),
            SpecialistReport(name="concurrency", dispatches=1, n_findings=1),
        ]
        path = review_log.record(_result([], reports), branch="feat/x")

    stats = specialist_stats.compute(path)
    assert stats["numerics"].dispatches == 12
    # zero findings across >= floor dispatches -> candidate for pruning.
    assert stats["numerics"].tag == specialist_stats.GATE_CANDIDATE
    # found things -> active.
    assert stats["concurrency"].tag == specialist_stats.ACTIVE


def test_insufficient_data_below_floor(state: Path) -> None:
    for _ in range(3):
        reports = [SpecialistReport(name="numerics", dispatches=1, n_findings=0)]
        path = review_log.record(_result([], reports), branch="feat/y")
    stats = specialist_stats.compute(path)
    assert stats["numerics"].tag == specialist_stats.INSUFFICIENT_DATA


def test_never_gate_insurance_set(state: Path) -> None:
    for _ in range(15):
        reports = [SpecialistReport(name="security", dispatches=1, n_findings=0)]
        path = review_log.record(_result([], reports), branch="feat/z")
    stats = specialist_stats.compute(path)
    # security is kept regardless of a zero-hit streak.
    assert stats["security"].tag == specialist_stats.NEVER_GATE


def test_high_secret_in_review_is_blocked(state: Path) -> None:
    secret = (
        "-----BEGIN PRIVATE KEY-----\nMIIBVgIBADANBgkqh\n-----END PRIVATE KEY-----"
    )
    bad = Finding("HIGH", 9, "a.py", 1, "numerics", secret, "rotate", "numerics")
    reports = [SpecialistReport(name="numerics", dispatches=1, n_findings=1)]
    with pytest.raises(jsonl_store.SecretRejected):
        review_log.record(_result([bad], reports), branch="feat/secret")
