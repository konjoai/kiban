# Next session: Phase 2 of the review-pipeline plan (test loop, in kiban)

Sprint P1 (`CHANGELOG.md` [1.11.0], full reasoning in `LEDGER.md`'s
`Review-Pipeline-Phase-1`, primary detail in lopi's own `LEDGER.md` entry of the same
name) shipped the Planner/Executor split in lopi and the plan-artifact schema plus
telemetry wiring here. Nothing below is a critic, a gate, or a router; those stay out
of scope until Phase 3.

## What P1 actually shipped, corrected against measurement

1. **`ToolProfile` is centrally enforced, live-confirmed twice.** lopi's PF-1
   entry-point audit found 12 Task-construction paths, 6 live in the deployed binary,
   all 6 funneling through one `ClaudeCode` construction site
   (`crates/lopi-agent/src/runner/run_loop.rs`). `permission_mode` was already
   centralized there; `ToolProfile::Readonly` (forces `DontAsk` plus a fixed read-only
   allow-list) extends that same choke point, not a new one. Confirmed live: a raw
   `claude -p` spawn and a spawn through lopi's own `ClaudeCode` wrapper, both under
   this profile, both had the `Write` tool call denied and terminated cleanly.
2. **`RepoProfile` (directory scope) is a separate, still-inconsistent mechanism, not
   fixed this sprint.** MCP `lopi_submit_task` and the web `POST /api/tasks` handler
   both skip it and both default `task.source` to `Cli`. `allowed_dirs`/
   `forbidden_dirs` were never a hard boundary anywhere regardless (advisory prompt
   text plus a post-hoc, detect-not-block diff-scope check), so closing the
   `RepoProfile` gap alone would not make directory scope enforced. Recorded as a real
   gap, not silently assumed fixed.
3. **`allow_self_modify` is enforced at exactly 2 of ~12 entry points** (`lopi run`,
   `lopi bypass`), `pub(crate)` to lopi's `src/` binary so no library crate can call it
   even if it tried. A future decision needed: library-crate-visible check, or stay a
   documented binary-only convention.
4. **The plan artifact has a real schema, structurally validated on both sides.**
   `schemas/plan_artifact.schema.json` here; `lopi_core::PlanArtifact` there, a
   `#[serde(try_from = ...)]`-validated type that cannot be constructed with an empty
   `scope` by any path. TOON round-trip confirmed to preserve every field.
   `PrTelemetryRecord` gained `predicted_tier`/`planner_scope`/`planner_model`/
   `planner_commit`, verified with one real end-to-end record from a live Planner run.
5. **The Planner/Executor handoff is live-confirmed end to end but not wired into the
   default loop.** `lopi_agent::planner_executor` is new, additive, independently
   tested (including a real live run: a readonly Planner produced a valid plan, the
   raw goal never reached the Executor's prompt, the Executor correctly implemented
   exactly the plan's scope). It does not replace `AgentRunner::run()`'s existing
   plan/implement/test/score/retry loop; that integration is unscoped, deliberately
   left for a future sprint given how much machinery that loop already carries
   (progress gates, stability harness, verifier, adaptive retry, successor tasks).

## Before starting Phase 2, read

`lopi/LEDGER.md`'s `Review-Pipeline-Phase-1` entry in full (the PF-1 table is the
complete per-entry-point audit) and `lopi/crates/lopi-agent/src/planner_executor.rs`'s
module doc comment (states exactly why it is additive, not wired in, this sprint).

## Phase 2 itself: test loop in kiban

Per the plan (section 4, Phase 2): Executor writes tests, each repo's own coverage
tool measures the gap (`cargo llvm-cov nextest` for lopi, `pytest --cov` for squish,
never a third tool that would disagree with the gate already enforcing it), uncovered
lines map to enclosing items via a `syn` walk, feed back only uncovered item bodies,
and on a coverage plateau run `cargo mutants --in-diff` and feed surviving mutants
back with the specific mutation shown. Gate: zero surviving mutants on changed lines,
or an explicit kledger waiver with a reason. New skill: `konjo/mutation-hunt`.

**Before Phase 2's exit gate means anything**, the full-workspace mutation baseline
still needs to complete (Sprint P0's 35-minute capped run reached 109 of an estimated
1,500 to 2,000 mutants; this is an order-of-magnitude sample, not a control, per P0's
own `NEXT_SESSION_PROMPT.md`). Run `cargo mutants --workspace --jobs 4` (or higher)
to completion, detached, likely overnight or via a dedicated long-running job, not
inside a single interactive session, before KT-D can conclude anything.

## Do not build yet (still Phase 3+ per the plan)

The router, `routing.toml`, any critic, any new/blocking gate, Kani harnesses, or any
change to a coverage threshold anywhere. Wiring `planner_executor` into lopi's default
retry loop is Phase 1 follow-up work, not Phase 2 scope either; a future session should
scope it deliberately rather than bundling it into the test-loop sprint.
