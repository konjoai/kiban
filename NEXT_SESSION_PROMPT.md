# Next session: Phase 5 (propagation)

## What Phase 4 built (0.5.0)

The prove gate: a 30-run paired Wilcoxon signed-rank perf test with the rule that
significance alone never merges.

- `lib/prove.py`: pure-Python paired Wilcoxon (tie/continuity corrections, zero-diff
  handling, n floor 30) and the MERGE / NOISE / REGRESSION verdict.
- `bin/konjo-prove`: runs locally, ingests a paired artifact, records the verdict
  (BENCHMARKS.md, prove.jsonl, Ledger ack, MERGE trailer). `baseline capture` for goldens.
- konjo-gates `prove` gate: checks the MERGE trailer on a perf change; runs no benchmark,
  imports no stats (reuses the Phase 3 record-and-check path).

Kill-test passes: MERGE / NOISE (sub-threshold) / NOISE (non-sig) / REGRESSION from
synthetic data; CI fails a perf change without a MERGE record and passes one with it.

## Carried debt: squish prove wiring (do this first when squish is reachable)

squish was unreachable this sprint (the build proxy scoped to kiban only). The squish
prove block has the metric/unit/direction from the Phase 2 read but leaves `min_effect_pct`
and `bench_cmd` as TODO. When squish is back in scope:
- Read `benchmarks/ollama_vs_squish/bench_thermal_h2h.py` for the exact output fields and
  confirm the metric name.
- Set `min_effect_pct` from the squish perf policy (the threshold below which a win is
  NOISE) and `bench_cmd` (the command that produces the paired artifact).
- Document the adapter from the bench output to the konjo-prove artifact schema.

## Phase 5 tasks (propagation, behind pins)

1. `konjo-gates-rs` (clippy + cargo-mutants) and `konjo-gates-js` (eslint + tsc + stryker),
   mirroring konjo-gates-py: profile in, scope routing, repo-native gates wrapped in
   net-new, the record-and-check gates (one_way_door, prove) checked the same way.
2. A second repo profile (one of the other Konjo repos), added behind a version pin, to
   prove the profile schema generalizes past squish.
3. Grow the eval corpus: one fixture per real bug class per specialist (memory,
   concurrency, api-surface), each with a clean control; re-run `konjo-eval record`.
4. The supply_chain universal gate (lockfile integrity, advisory scan), still stubbed.

## Tag and release discipline (in force)

`release.yml` cuts the release and tag server-side on a VERSION change on main. Every
VERSION bump is a one-way door: classify and confirm it with konjo-oneway and log it. The
historical tags v0.1.0..v0.4.0 exist locally; they could not be pushed from the build
environment (the proxy rejects tag-ref pushes).

## Still out, permanently

The Machine Room hub, cross-model review, web/design/iOS/browser tooling,
psychographic/profile-tuning behavior, completeness-toward-10 defaults, and the plugin
marketplace.
