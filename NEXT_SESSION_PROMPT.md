# Next session: Phase 10 (the craft skill)

## What Phase 9 built (0.9.0)

The long-run gate: the benchmark resume pain, generalized. Any run long enough to be
interrupted now has a contract, a helper, and a gate.

- `lib/packs/longrun/konjo_longrun.py`: `Checkpoint` (done / mark / completed / results) on a
  progress JSONL on `jsonl_store`, folded latest-wins for unit-level idempotency, plus the
  `add_resume_args` / `is_fresh` argparse mixin (`--resume` / `--fresh`). A benchmark adopts
  resume in about five lines.
- `gate_longrun`: a static, diff-only check that a changed long-run script wires the resume
  contract. It fires only on runnable scripts (a `__main__` guard, or under `benchmarks/` /
  `scripts/`), so a bench-named library is exempt. Never runs the benchmark.
- `longrun_globs` profile field; the `longrun` skill.
- Kill-test green with no model and no network (kill at unit 3 of 5, resume, match a fresh
  run, survive a corrupt progress line).

## Carried activation steps (unchanged, still parked)

1. **Rust cassettes** (Phase 7): ACTIVATED; no carried step.
2. **VECTRO reconciliation** (Phase 7): reconcile `profiles/vectro.yml` and clear every
   UNVERIFIED field when VECTRO unparks.
3. **Squish prove gate** (Phase 5): still PENDING on the M3 bench hardware.

## Phase 10 tasks (the craft skill)

One small skill, opt-in per repo, carrying the four Karpathy behaviors plus the verify-loop.
It is prose, not code. Evolution plan section 7. Keep it short (section 8 caps its token
cost; the craft skill is the most likely place for bloat, so resist it).

1. `plugins/konjo/skills/craft/SKILL.md` (or a `lib/packs/craft` fragment if a pack shape
   fits better), covering:
   - **Think before coding**: state assumptions; present differing interpretations rather
     than pick silently; name a simpler path; stop and name what is unclear.
   - **Simplicity first**: the minimum that solves the problem, nothing speculative; no
     configurability that was not asked for; if it is 200 lines and could be 50, rewrite it.
   - **Surgical changes**: touch only what the task requires; match the existing style; do
     not refactor unbroken code; remove only the orphans your own change created; mention
     unrelated dead code, do not delete it.
   - **Goal-driven execution**: turn the task into a verifiable success criterion before
     starting, and loop until it is met.
   - **Verify-loop**: run the repo's declared verify command before claiming done.
2. A `verify_cmd` profile field (the per-repo verify command/path). A repo with no
   `verify_cmd` is a surfaced finding, the way a missing prove threshold is, not a hard
   block at first.
3. Route `craft` from the `konjo` umbrella skill.

Stay honest about scope: the craft skill is opt-in and short. Do not let it grow into the
gstack-style multi-hundred-line preamble the evolution plan explicitly rejects (section 1,
"Contradicted"). The context-budget gate that enforces this lands in Phase 12.

## Tag and release discipline (in force)

`release.yml` cuts the release and tag server-side on a VERSION change on main. Every VERSION
bump is a one-way door: classify and confirm it. The build environment cannot push tag refs.

## Still out, permanently

The Machine Room hub, cross-model review as a default, web/design/iOS/browser tooling,
psychographic/profile-tuning behavior, completeness-toward-10 defaults, the plugin
marketplace, and "boil the ocean" completeness.
