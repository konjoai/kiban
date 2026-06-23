# Next session: Phase 4

## What Phase 3 built (0.4.0)

The safety layer for irreversible actions and credential-shaped findings, plus the
release-tag discipline.

- `lib/oneway.py` + `bin/konjo-oneway`: classify a change as one-way or two-way.
- `lib/confirm.py`: the typed-confirm flow (exact token, justification, Ledger ack, the
  commit trailer CI reads). `bin/konjo-secrets`: HIGH blocks, MEDIUM confirms.
- konjo-gates `one_way_door` gate: checks the commit-trailer acknowledgement; never prompts.
- Release tags backfilled (v0.1.0..v0.3.0) and v0.4.0 cut; the template pins v0.4.0.

Kill-test passes: classify one-way vs two-way; confirm refuses a vague reply and logs on
a valid one; CI fails an unacknowledged one-way change and passes the acknowledged one.

## Tag and release discipline (now in force)

- `release.yml` on main cuts a GitHub release and tag server-side whenever VERSION
  changes. So a merged VERSION bump produces the tag; no hand-pushed tag is needed going
  forward.
- Every VERSION bump is a one-way door. Classify and confirm it with `konjo-oneway`, log
  the release decision to the Ledger, and (for the repo's own history) the commit that
  bumps VERSION carries the acknowledgement trailer.
- Historical tags v0.1.0..v0.3.0 were backfilled locally this sprint. They could not be
  pushed from the build environment (the git proxy rejects tag-ref pushes) and release.yml
  does not backfill old versions, so they must be pushed or cut as releases by hand if the
  historical pins need to resolve.

## Immediate Phase 4 tasks

1. **The prove gate: 30-run paired Wilcoxon (p<0.05)**. Use squish's real benchmark data
   (`benchmarks_v5_1_1`, `bench_thermal_h2h.py`). Compare a change's runs against the
   stored baseline; block on a statistically significant regression. This is perf, separate
   from the detection self_test.
2. **Grow the eval corpus and re-record cassettes**. One fixture per real bug class per
   specialist (memory, concurrency, api-surface), each with a clean control. Re-run
   `konjo-eval record`.

## Later

- `konjo-gates-rs` (clippy + cargo-mutants) and `konjo-gates-js` (eslint + tsc + stryker),
  then profiles for the other repos one at a time behind version pins.
- The supply_chain universal gate (lockfile integrity, advisory scan) is a Phase 5
  candidate; it stays stubbed for now.

## Still out, permanently

The Machine Room hub, cross-model review, web/design/iOS/browser tooling,
psychographic/profile-tuning behavior, completeness-toward-10 defaults, and the plugin
marketplace.
