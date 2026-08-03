"""Validator for the Konjo plan artifact (schemas/plan_artifact.schema.json).

Phase 1 of the review-pipeline plan (KONJO_REVIEW_PIPELINE_PLAN.md section 4, section 2
"Sprint P1" companion doc). The plan artifact is emitted by a readonly Planner in lopi and
consumed by the Executor as its system prompt.

This is a hand-written validator, not a generic JSON Schema engine -- the schema uses a
small, fixed subset of keywords (type, required, properties, items, minItems, minLength,
additionalProperties) and a full engine would be premature machinery for one schema. The
constraints below are read from the schema file at import time rather than duplicated as
inline literals, so `scope`'s minItems can only drift from its schema declaration if the
schema file itself changes -- `test_plan_artifact_schema.py` additionally asserts the
schema's own declared minItems is still 1, so a silent schema edit cannot loosen this
without a visible test failure.

Fixture-level checking (section 7.3's second level, "schema catches malformed, fixtures
catch wrong") is Phase 3 scope, once the router exists to fixture-check against.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "plan_artifact.schema.json"


def _load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


SCHEMA = _load_schema()
_REQUIRED: list[str] = SCHEMA["required"]
_SCOPE_MIN_ITEMS: int = SCHEMA["properties"]["scope"]["minItems"]
_ALLOWED_FIELDS: set[str] = set(SCHEMA["properties"].keys())


class PlanArtifactError(ValueError):
    """Raised by `validate` in strict mode; carries every error found, not just the first."""


def validate(plan: Any) -> list[str]:
    """Return a list of validation errors; empty means the plan artifact is schema-valid.

    Never raises on malformed input -- a non-dict `plan` is itself reported as an error,
    same as any other schema violation, so a caller can always treat an empty return as
    "safe to proceed" without a separate type check first.
    """
    errors: list[str] = []

    if not isinstance(plan, dict):
        return [f"plan artifact must be an object, got {type(plan).__name__}"]

    for field in _REQUIRED:
        if field not in plan:
            errors.append(f"missing required field: {field!r}")

    extra = set(plan.keys()) - _ALLOWED_FIELDS
    if extra:
        errors.append(f"unknown field(s) not in schema: {sorted(extra)!r}")

    if "scope" in plan:
        scope = plan["scope"]
        if not isinstance(scope, list):
            errors.append(f"scope must be an array, got {type(scope).__name__}")
        else:
            if len(scope) < _SCOPE_MIN_ITEMS:
                errors.append(
                    f"scope must have at least {_SCOPE_MIN_ITEMS} item(s) -- an empty "
                    "scope is schema-invalid, not a valid 'no scope escape possible' "
                    "declaration (section 2.4's fail-open fix)"
                )
            for i, item in enumerate(scope):
                if not isinstance(item, str) or not item:
                    errors.append(f"scope[{i}] must be a non-empty string")

    for field in ("goal", "test_strategy", "planner_model", "planner_commit"):
        if field in plan:
            value = plan[field]
            if not isinstance(value, str) or not value:
                errors.append(f"{field} must be a non-empty string")

    for field in ("invariants", "non_goals"):
        if field in plan:
            value = plan[field]
            if not isinstance(value, list):
                errors.append(f"{field} must be an array, got {type(value).__name__}")
            elif any(not isinstance(item, str) or not item for item in value):
                errors.append(f"{field} items must all be non-empty strings")

    if "predicted_tier" in plan and plan["predicted_tier"] is not None:
        if not isinstance(plan["predicted_tier"], str):
            errors.append("predicted_tier must be a string or null")

    return errors


def is_valid(plan: Any) -> bool:
    """Convenience wrapper: True iff `validate` finds no errors."""
    return not validate(plan)


def validate_strict(plan: Any) -> None:
    """Raise `PlanArtifactError` with every error joined, or return silently if valid."""
    errors = validate(plan)
    if errors:
        raise PlanArtifactError("; ".join(errors))
