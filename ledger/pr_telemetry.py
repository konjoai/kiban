"""Per-PR telemetry: one append-only record per merged PR, on the jsonl_store substrate.

This is Phase 0 of the review-pipeline plan (see KONJO_REVIEW_PIPELINE_PLAN.md section 4
and the Sprint P0 companion doc, section 2). It exists to make the plan's cost and
quality-yield claims falsifiable before any gate, critic, or router is built.

Not a Decision Ledger event: `ledger.engine.Ledger` models durable calls (decide /
supersede / redact); a PR telemetry record is a measurement, not a call, so it lives in
its own event stream (`ledger/pr_telemetry.jsonl`, sibling to `decisions.jsonl` and
`learnings.jsonl`) rather than going through `Ledger.decide()`. Same storage discipline
(append-only, atomic, injection-rejected, secret-scanned) via the shared `jsonl_store`.

Fields split by capture method, per the plan:

  Derivable from git (backfillable from history alone):
    sha, merged_at, files_touched, path_classes, lines_added, lines_removed,
    crates_touched, ast_delta, trigger_surface_hits, weakening_markers, new_dependencies

  Plan-artifact-derived (Phase 1, live capture only): predicted_tier, planner_scope,
    planner_model, planner_commit -- populated from the readonly Planner's PlanArtifact
    (see lopi's `lopi-core::PlanArtifact` and `schemas/plan_artifact.schema.json`) once a
    Phase 1 task runs through the Planner/Executor split. Named `planner_scope`, not
    `scope` -- this record's own top-level `scope` field already means "org vs. repo"
    ledger scope (see PrTelemetryRecord.scope above); reusing that name for the plan
    artifact's file/glob scope would silently collide. `predicted_tier` carries zero
    routing authority (plan section 7.4) -- it is recorded here only so a future
    prediction-vs-actual comparison can be measured; a router must never read it from
    this record to assign a tier.

  Live capture only (forward-going; cannot be recovered for a past PR):
    tokens_input, tokens_cache_read, tokens_cache_write, tokens_output, wall_clock,
    runner_minutes, coverage_delta, mutation_score_on_diff, review_rounds,
    findings_raised, findings_that_caused_a_change, findings_later_contradicted

The critic-related fields (review_rounds, findings_*) are defined now but stay null until
Phase 3 lands a critic panel to populate them -- defining them now means the schema does
not churn later, per the plan's explicit instruction. A record with every live-capture
field null is a legitimate, common case (every backfilled historical PR looks like this);
callers must not treat null-fields-present as a bug.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from lib import jsonl_store

PR_TELEMETRY_FILE = "ledger/pr_telemetry.jsonl"

Source = Literal["backfill", "live"]


@dataclass
class GateRunRecord:
    """One gate's outcome for one PR telemetry record -- Adoption-Ramp-1.

    The missing half of what the framework measured before this: kill-tests
    (`konjo-eval`, `specialist_stats`) already measure whether a gate catches a
    defect. Nothing measured what a gate *costs* -- `lib/gate_stats.py` is that
    missing half, fed by the `gate_results` list this record type populates.

    `overridden`/`waived` are the false-positive signal: a FAIL/WARN verdict a human
    later reversed (a `gate:override` label + `Konjo-Override:` trailer for a
    BLOCKING gate, or a `Konjo-*-Waived:` trailer for an advisory finding like
    polarity's) means the gate's own verdict was wrong for that run, not that the
    change was bad. `duration_s` is wall-clock cost, same unit `wall_clock` already
    uses for the whole PR.
    """

    name: str = ""
    verdict: str = ""  # PASS / WARN / FAIL / SKIP / ERROR -- konjo_gates_py.cli's own constants
    duration_s: float | None = None
    overridden: bool = False
    waived: bool = False


@dataclass
class AstDelta:
    """Per-file-or-item AST classification for one merge commit's diff.

    identical: comment/whitespace-only change (AST-identical before/after).
    bodies_changed: at least one function body changed, no public signature changed.
    signatures_changed: at least one public signature changed.
    A commit can have items in more than one bucket; counts, not booleans.
    """

    identical: int = 0
    bodies_changed: int = 0
    signatures_changed: int = 0


@dataclass
class PrTelemetryRecord:
    event: str = field(default="pr_telemetry", init=False)
    id: str = ""
    repo: str = ""
    scope: str = "org"
    source: Source = "backfill"
    recorded_at: str = ""
    recorded_by: str = "unknown"

    # -- derivable from git (backfillable) --------------------------------------------
    sha: str = ""
    merged_at: str | None = None
    files_touched: list[str] = field(default_factory=list)
    path_classes: list[str] = field(default_factory=list)
    lines_added: int | None = None
    lines_removed: int | None = None
    crates_touched: list[str] = field(default_factory=list)
    ast_delta: dict[str, int] | None = None
    trigger_surface_hits: list[str] = field(default_factory=list)
    weakening_markers: list[str] = field(default_factory=list)
    new_dependencies: list[str] = field(default_factory=list)

    # -- plan-artifact-derived (Phase 1, live capture only) ----------------------------
    predicted_tier: str | None = None
    planner_scope: list[str] | None = None
    planner_model: str | None = None
    planner_commit: str | None = None

    # -- live capture only (forward-going) ---------------------------------------------
    tokens_input: int | None = None
    tokens_cache_read: int | None = None
    tokens_cache_write: int | None = None
    tokens_output: int | None = None
    wall_clock: float | None = None
    runner_minutes: float | None = None
    coverage_delta: float | None = None
    mutation_score_on_diff: float | None = None
    review_rounds: int | None = None
    findings_raised: int | None = None
    findings_that_caused_a_change: int | None = None
    findings_later_contradicted: int | None = None
    gate_results: list[GateRunRecord] = field(default_factory=list)

    def add_gate_result(
        self,
        name: str,
        verdict: str,
        *,
        duration_s: float | None = None,
        overridden: bool = False,
        waived: bool = False,
    ) -> None:
        """Append one gate's outcome (`lib/gate_stats.py`'s input shape)."""
        self.gate_results.append(
            GateRunRecord(
                name=name, verdict=verdict, duration_s=duration_s,
                overridden=overridden, waived=waived,
            )
        )

    def apply_plan_artifact(self, plan: dict[str, Any]) -> None:
        """Populate the plan-artifact-derived fields from a schema-valid plan artifact
        dict (see `lib.plan_artifact_schema.validate`). Raises `PlanArtifactError` if
        `plan` is not schema-valid -- a telemetry record must never carry a scope value
        that could not have come from a real Planner run.
        """
        from lib.plan_artifact_schema import PlanArtifactError, validate

        errors = validate(plan)
        if errors:
            raise PlanArtifactError("; ".join(errors))
        self.predicted_tier = plan["predicted_tier"]
        self.planner_scope = list(plan["scope"])
        self.planner_model = plan["planner_model"]
        self.planner_commit = plan["planner_commit"]

    def to_event(self) -> dict[str, Any]:
        d = asdict(self)
        d["event"] = "pr_telemetry"
        return d


def _new_id(sha: str) -> str:
    # Deterministic on (repo omitted here, caller-namespaced) sha, not random: a re-run of
    # backfill for the same commit produces the same id, so re-running is idempotent at
    # the read layer (duplicate detection is the reader's job -- see `for_sha` below) even
    # though the store itself is pure-append and never deduplicates on write.
    return sha[:12] if sha else "unknown"


class PrTelemetry:
    def __init__(self, path: str | Path = PR_TELEMETRY_FILE) -> None:
        self.path = str(path)

    def append(self, rec: PrTelemetryRecord) -> str:
        if not rec.sha:
            raise ValueError("PrTelemetryRecord.sha is required")
        if not rec.id:
            rec.id = _new_id(rec.sha)
        if not rec.recorded_at:
            rec.recorded_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        jsonl_store.append(self.path, rec.to_event())
        return rec.id

    def _events(self) -> list[dict[str, Any]]:
        return jsonl_store.read(self.path)

    def all(self, repo: str | None = None) -> list[dict[str, Any]]:
        events = self._events()
        if repo is not None:
            events = [e for e in events if e.get("repo") == repo]
        return events

    def for_sha(self, sha: str, repo: str | None = None) -> dict[str, Any] | None:
        """Return the most recently appended record for this sha, if any.

        Because the store is append-only, re-running backfill over the same commit
        appends a second record rather than replacing the first; callers that want
        idempotent backfill should check `for_sha` first and skip commits already
        present, rather than relying on the store to dedupe.
        """
        matches = [
            e for e in self._events()
            if e.get("sha") == sha and (repo is None or e.get("repo") == repo)
        ]
        return matches[-1] if matches else None

    def count(self, repo: str | None = None) -> int:
        return len(self.all(repo=repo))
