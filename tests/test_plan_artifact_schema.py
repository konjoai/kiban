"""Tests for the Konjo plan artifact schema (schemas/plan_artifact.schema.json) and its
validator (lib/plan_artifact_schema.py).

Per KONJO_REVIEW_PIPELINE_PLAN.md section 2.4's fail-open fix: a plan artifact whose
scope field is absent, empty, or schema-invalid must escalate review, not silently read
as "no scope escape possible". These three cases are tested separately below, plus a
guard that the schema's own declared minItems can't quietly loosen without a red test.
"""

from __future__ import annotations

import copy

from lib.plan_artifact_schema import SCHEMA, is_valid, validate

VALID_PLAN = {
    "goal": "Add a readonly Planner tool profile",
    "scope": ["crates/lopi-core/src/tool_profile.rs"],
    "invariants": ["Mutating stays the default when tool_profile is absent"],
    "test_strategy": "Live-spawn under Readonly, confirm write denial and clean exit",
    "non_goals": ["No critic, no router, no gate"],
    "predicted_tier": "1",
    "planner_model": "claude-sonnet-5",
    "planner_commit": "6b57438",
}


def test_valid_plan_passes() -> None:
    assert validate(VALID_PLAN) == []
    assert is_valid(VALID_PLAN)


def test_rejects_empty_scope() -> None:
    plan = copy.deepcopy(VALID_PLAN)
    plan["scope"] = []
    errors = validate(plan)
    assert not is_valid(plan)
    assert any("at least" in e for e in errors)


def test_rejects_missing_scope_field() -> None:
    plan = copy.deepcopy(VALID_PLAN)
    del plan["scope"]
    errors = validate(plan)
    assert not is_valid(plan)
    assert any("missing required field: 'scope'" in e for e in errors)


def test_rejects_schema_invalid_scope() -> None:
    plan = copy.deepcopy(VALID_PLAN)
    plan["scope"] = "not-a-list"
    errors = validate(plan)
    assert not is_valid(plan)
    assert any("scope must be an array" in e for e in errors)


def test_rejects_non_dict_input() -> None:
    assert not is_valid(None)
    assert not is_valid(["not", "a", "dict"])


def test_rejects_unknown_field() -> None:
    plan = copy.deepcopy(VALID_PLAN)
    plan["extra_field_not_in_schema"] = "x"
    errors = validate(plan)
    assert not is_valid(plan)
    assert any("unknown field" in e for e in errors)


def test_rejects_missing_required_fields_individually() -> None:
    for field in SCHEMA["required"]:
        plan = copy.deepcopy(VALID_PLAN)
        del plan[field]
        assert not is_valid(plan), f"expected rejection with {field!r} missing"


def test_predicted_tier_accepts_null() -> None:
    plan = copy.deepcopy(VALID_PLAN)
    plan["predicted_tier"] = None
    assert is_valid(plan)


def test_schema_still_declares_scope_min_items_one() -> None:
    """Guards against a silent schema edit loosening the load-bearing constraint
    (section 2.4: an empty scope must never become valid without this test going red).
    """
    assert SCHEMA["properties"]["scope"]["minItems"] == 1
    assert "scope" in SCHEMA["required"]
