# Next session: Phase 2

## What Phase 1 built (0.2.0)

The meta-gate: a parallel specialist review engine plus the eval harness that
regression-tests it.

- `lib/review.py`: the keystone `review_diff(diff, profile, specialists=None, *, runs=1)`.
  One path for the live gate and the eval. Stable fingerprint, dedup, confidence gate
  (daily 8 / deep 2), pluggable backend (Claude CLI in production, scripted in tests).
- `lib/specialists/`: numerics, memory-bandwidth, concurrency, api-surface, red-team.
  Parallel; red-team last with the others' findings.
- `lib/diff_scope.py`, `lib/review_log.py`, `lib/specialist_stats.py`.
- `evals/runner.py`, `bin/konjo-eval`, `bin/konjo-review`, `bin/konjo-stats`.
- Phase 0 corrections C1 through C4 (squish re-check, self_update detached-HEAD reattach,
  konjo-newonly worktree, narrowed fetch).

Kill-test passes: konjo-eval flags squish/dtype_promotion at numerics/CRITICAL on every
run and stays silent on _clean_control on every run.

## Immediate Phase 2 tasks

1. **One-way-door confirm flow** (`bin/konjo-oneway`, still a stub). Classify
   hard-to-reverse changes (schema migrations, public API breaks, data deletes, key
   rotation) and add the interactive confirm. Two-way doors pass straight through.
2. **MEDIUM-secret interactive confirm**. Build the confirm flow on top of
   `lib/redact.py` for MEDIUM-tier findings (HIGH already blocks, LOW already surfaces).
3. **CI packages** (`packages/konjo-gates-py`/`-rs`/`-js`, still stubs). Make
   `konjo-gates-py` load a profile, select gates via `lib/diff_scope.py`, run the review
   gate and the eval self-test, and fail on regression. Wire `templates/repo-ci.yml` to
   run `konjo-eval` when SCOPE_PROMPTS is true.
4. **The prove gate: 30-run paired Wilcoxon (p<0.05)**. Add the statistical baseline
   comparison the eval metrics feed. This is where detection-rate deltas become a
   pass/fail signal against a stored baseline, not a single-run read.
5. **Grow the eval corpus**. One fixture per real bug class per specialist (memory,
   concurrency, api-surface), each with a clean control, so detection and false-positive
   rates are measured per lane.

## Carried risks

- LLM specialist non-determinism. Mitigated by `runs` repetition and the stable
  fingerprint, but watch the eval for flaky fixtures and record honest negative results
  rather than tuning a fixture to flatter the gate.
- squish is still not reachable on disk; `profiles/squish.yml` keeps its UNVERIFIED
  markers until squish is checked out alongside kiban.

## Still out, permanently

The Machine Room hub, cross-model review, web/design/iOS/browser tooling, profiles for
the other eight repos, psychographic/profile-tuning behavior, completeness-toward-10
defaults, and the plugin marketplace.
