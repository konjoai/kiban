# Next session: Phase 9 (the long-run gate)

## What Phase 8 built (0.8.0)

The compounding loop. The Ledger recorded decisions; kiban now records the other half too,
so a caught mistake becomes a durable rule instead of a one-run patch.

- `lib/learnings.py`: the learnings log, a sibling stream of the decision Ledger on the same
  substrate (`ledger/learnings.jsonl`). Append-only, event-sourced, redact-scanned. A
  learning is the one-line mistake, the rule that prevents it, the enforcement target (where
  the rule now lives), and the scope. `redact` retires one.
- The guardrail: a learning MUST name an enforcement target, or `konjo-learn add` refuses it
  (exit 4). A learning with no target is a note, not a learning, and notes do not go in the
  log.
- `bin/konjo-learn` (add / search / redact), the `correct` skill (recall, write the
  learning, propose and apply the smallest durable fix), and `recall` extended to search
  learnings.
- Kill-test green with no model and no network: a no-target learning is refused and not
  stored; a valid learning is logged, found, and retired.

## Carried activation steps (unchanged, still parked)

1. **Rust cassettes** (Phase 7): ACTIVATED; no carried step.
2. **VECTRO reconciliation** (Phase 7): when VECTRO unparks, reconcile `profiles/vectro.yml`
   and clear every UNVERIFIED field, including the load-bearing prove fields.
3. **Squish prove gate** (Phase 5): still PENDING on the M3 bench hardware.

## Phase 9 tasks (the long-run gate)

The resume-flag pain, generalized: any run long enough to be interrupted must resume from a
checkpoint with minimal loss. Evolution plan section 6.

1. `packs/longrun/konjo_longrun.py` (mirror the pack layout under `lib/packs`): a `Checkpoint`
   helper (open a progress JSONL on `jsonl_store`, `done(unit_key)`, `mark(unit_key, result)`,
   `completed()`) and an argparse mixin that adds `--resume` / `--fresh`. A benchmark adopts
   resume in about five lines.
2. `gate_longrun` in the orchestrator: a static check that a change touching a
   `longrun_globs` path has the resume contract (an argparse `--resume` flag or the documented
   helper imported, and a checkpoint-write call in the main loop). It reads the diff; it never
   runs the benchmark. In the spirit of the existing `oneway` and `prove` gates.
3. `longrun_globs` profile field (default: `benchmarks/**`, `**/bench_*.py`,
   `scripts/train_*.py`, eval-matrix runners).
4. Kill-test (`tests/test_longrun_killtest.sh`): run a synthetic long-run to unit 3 of 5,
   kill it, resume, and assert units 1-3 are skipped, 4-5 complete, and the final result set
   equals a clean `--fresh` run. Plus a corruption case: append a garbage line to the progress
   file and assert resume still works (the tolerant-read property of `jsonl_store.iter_read`).

Scope discipline (stay honest about section 2's conflict): resume is the operational floor
for any run that costs more than a few minutes, not gold-plating. The gate fires only on
long-run scripts, never on ordinary code, so "simplicity first" still governs everything else.

## Tag and release discipline (in force)

`release.yml` cuts the release and tag server-side on a VERSION change on main. Every VERSION
bump is a one-way door: classify and confirm it. The build environment cannot push tag refs.

## Still out, permanently

The Machine Room hub, cross-model review as a default, web/design/iOS/browser tooling,
psychographic/profile-tuning behavior, completeness-toward-10 defaults, the plugin
marketplace, and "boil the ocean" completeness.
