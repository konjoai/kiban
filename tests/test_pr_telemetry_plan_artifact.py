"""Tests for PrTelemetryRecord.apply_plan_artifact (Sprint P1 section 4).

Populates the plan-artifact-derived telemetry fields (predicted_tier, planner_scope,
planner_model, planner_commit) from a real PlanArtifact-shaped dict, reusing the same
validator `test_plan_artifact_schema.py` exercises directly -- a telemetry record must
never carry a scope value that didn't pass schema validation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledger.pr_telemetry import PrTelemetry, PrTelemetryRecord
from lib.plan_artifact_schema import PlanArtifactError

# Real values from Sprint P1's live end-to-end Planner -> Executor kill-test (see
# LEDGER.md's Review-Pipeline-Phase-1 entry): a readonly Planner spawned against a
# throwaway repo, asked to add a `subtract` function, and this is its actual
# schema-valid plan artifact output, field-for-field.
LIVE_PLAN_ARTIFACT = {
    "goal": (
        "Add a `subtract(a, b)` function to add.py that mirrors the existing "
        "`add(a, b)` function's style (same signature pattern, plain `return` "
        "expression, no type hints) and includes a docstring describing what it does."
    ),
    "scope": ["add.py"],
    "invariants": [
        "Do not modify or remove the existing `add(a, b)` function or its behavior",
        "New function must be named `subtract` and accept exactly two positional "
        "parameters `a, b`",
    ],
    "test_strategy": (
        "Manually verify by importing/running the module: run "
        "`python3 -c \"from add import add, subtract; assert subtract(5,3)==2\"`"
    ),
    "non_goals": [
        "Adding type hints or input validation beyond what add() has",
        "Creating tests files or a test suite",
    ],
    "predicted_tier": "low",
    "planner_model": "claude-sonnet-5",
    "planner_commit": "6b57438",
}


def test_apply_plan_artifact_populates_all_four_fields() -> None:
    rec = PrTelemetryRecord(repo="lopi", sha="6b57438abc")
    rec.apply_plan_artifact(LIVE_PLAN_ARTIFACT)
    assert rec.predicted_tier == "low"
    assert rec.planner_scope == ["add.py"]
    assert rec.planner_model == "claude-sonnet-5"
    assert rec.planner_commit == "6b57438"


def test_apply_plan_artifact_rejects_empty_scope() -> None:
    plan = dict(LIVE_PLAN_ARTIFACT)
    plan["scope"] = []
    rec = PrTelemetryRecord(repo="lopi", sha="deadbeef")
    with pytest.raises(PlanArtifactError):
        rec.apply_plan_artifact(plan)


def test_planner_scope_does_not_collide_with_ledger_scope_field() -> None:
    """The record's own top-level `scope` (org/repo ledger scope) and the plan
    artifact's `planner_scope` (file/glob list) must never be conflated.
    """
    rec = PrTelemetryRecord(repo="lopi", sha="6b57438abc", scope="repo:lopi")
    rec.apply_plan_artifact(LIVE_PLAN_ARTIFACT)
    assert rec.scope == "repo:lopi"
    assert rec.planner_scope == ["add.py"]


def test_one_real_end_to_end_record_has_all_four_fields_non_null(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Section 4's verify criterion: one real end-to-end task produces a telemetry
    record with predicted_tier/planner_scope/planner_model/planner_commit non-null.
    """
    monkeypatch.setenv("KONJO_STATE_DIR", str(tmp_path))
    telemetry = PrTelemetry("ledger/pr_telemetry.jsonl")
    rec = PrTelemetryRecord(
        repo="lopi",
        source="live",
        sha="6b57438abc123",
    )
    rec.apply_plan_artifact(LIVE_PLAN_ARTIFACT)
    telemetry.append(rec)

    stored = telemetry.for_sha("6b57438abc123", repo="lopi")
    assert stored is not None
    assert stored["predicted_tier"] is not None
    assert stored["planner_scope"] is not None
    assert stored["planner_model"] is not None
    assert stored["planner_commit"] is not None
    # Critic fields stay null -- Phase 3, not this sprint.
    assert stored["findings_raised"] is None
