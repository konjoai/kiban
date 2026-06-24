# Next session: Phase 6 (first propagation)

## What Phase 5 built (0.6.0)

The squish pilot is complete and verified.

- Eval corpus covers all four squish specialists (numerics, memory-bandwidth,
  concurrency, api-surface), each with a planted bug caught at CRITICAL on the first try,
  plus silence controls. Cassettes re-recorded; `--replay` is deterministic over six
  fixtures.
- The squish prove gate is wired against the real bench (`bench_cmd`, metric
  `e2e_200tok_s`, `lib/bench_squish.py` adapter, `konjo-prove adapt`). It is honestly
  inert: `min_effect_pct` is PENDING, so `konjo-prove run` reports NOT ACTIVATED (exit 3)
  and the CI prove gate keeps blocking perf changes; it never passes silently.

## Carried activation step (needs the M3 bench hardware)

Activate the squish prove gate by working the checklist in `profiles/squish.yml`:
capture >= 30 paired baseline runs (RUNS=5 per bench file, so >= 6 runs), measure the
run-to-run jitter (CoV or MAD% of `total_s`), set `min_effect_pct` above that noise floor,
confirm it, and capture the golden baseline tag `benchmarks_v5_1_1`. Until then the gate
stays NOT ACTIVATED by design.

## Phase 6 tasks (first propagation, behind pins)

1. `konjo-gates-rs`: the Rust CI-plane runner, mirroring konjo-gates-py. Profile in, scope
   routing, repo-native gates (clippy, cargo-mutants) wrapped in net-new, the
   record-and-check gates (one_way_door, prove) checked the same way. Build the pattern
   once on the verified squish shape.
2. The second repo profile: pick one Konjo repo, add its profile behind a version pin, and
   confirm the profile schema generalizes past squish (a different stack, a different
   specialist set). This is the real test of the pattern.
3. Keep konjo-gates-js a stub until a JS repo is the third pilot.

## Later

- `konjo-gates-js` (eslint + tsc + stryker) when a JS repo is picked.
- The supply_chain universal gate (lockfile integrity, advisory scan), still stubbed.

## Tag and release discipline (in force)

`release.yml` cuts the release and tag server-side on a VERSION change on main. Every
VERSION bump is a one-way door: classify and confirm it. Historical tags v0.1.0..v0.5.0
exist locally; the build environment cannot push tag refs.

## Still out, permanently

The Machine Room hub, cross-model review, web/design/iOS/browser tooling,
psychographic/profile-tuning behavior, completeness-toward-10 defaults, and the plugin
marketplace.
