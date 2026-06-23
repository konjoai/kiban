# Next session: Phase 3

## What Phase 2 built (0.3.0)

The CI plane enforces. `konjo-gates` blocks a pull request, and the eval runs
deterministically offline so it can be a CI gate.

- `packages/konjo-gates-py`: the orchestrator. Profile in, changed files routed through
  `diff_scope`, kiban-native gates (prose net-new, secrets, self_test replay,
  report-only specialist stats) plus repo-native gates wrapped in `konjo-newonly`. Imports
  the real engine; reimplements nothing.
- `evals/cassettes.py` + `konjo-eval record` / `run --replay`: deterministic offline eval.
- `lib.redact.scan_paths` / `scan_diff`; root `pyproject.toml` ships the engine with the
  entry point; `templates/repo-ci.yml` pinned to v0.3.0 with the replay eval.
- C-B: `profiles/squish.yml` reconciled against the real repo, all UNVERIFIED markers gone.

Kill-test passes with no model and no network: clean diff passes; net-new prose and a
HIGH secret block; self_test runs via replay.

## Immediate Phase 3 tasks

1. **One-way-door confirm** (`bin/konjo-oneway`, still a stub). Classify hard-to-reverse
   changes (schema migrations, public API breaks, data deletes, key rotation) and add the
   interactive confirm. Wire it as a konjo-gates gate that requires confirmation, not just
   a pass/fail.
2. **MEDIUM-secret interactive confirm**. The secrets gate already surfaces MEDIUM
   findings as a warn; add the human confirm flow on top of `lib.redact` (HIGH still
   blocks outright).
3. **The prove gate: 30-run paired Wilcoxon (p<0.05)**. With real benchmark data from a
   consuming repo (squish has `benchmarks_v5_1_1` and `bench_thermal_h2h.py`), add the
   statistical baseline comparison. This is perf regression, separate from the detection
   self_test.
4. **Grow the eval corpus and re-record cassettes**. One fixture per real bug class per
   specialist (memory, concurrency, api-surface), each with a clean control. Re-run
   `konjo-eval record` so the replay gate covers them.
5. **Propagate, repo by repo**. Build `konjo-gates-rs` (clippy + cargo-mutants) and
   `konjo-gates-js` (eslint + tsc + stryker), then add profiles for the other repos one at
   a time behind version pins. Never all at once.

## Carried notes

- The eval cassettes must be re-recorded (`konjo-eval record`, needs a model) whenever a
  specialist prompt or a fixture changes, or `--replay` will hard-error on the stale key.
  That hard error is intentional: a drifted prompt must not pass as zero findings.
- squish reconcile was read-only against a clone; if squish's gates change, re-run C-B.

## Still out, permanently

The Machine Room hub, cross-model review, web/design/iOS/browser tooling,
psychographic/profile-tuning behavior, completeness-toward-10 defaults, and the plugin
marketplace.
