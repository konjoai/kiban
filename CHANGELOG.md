# Changelog

All notable changes to kiban are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-06-23

Phase 1: the meta-gate. A parallel specialist review engine plus the eval harness that
regression-tests it against the planted-bug corpus. Scoped to the review-gate-plus-self-
test core and the squish pilot.

### Added

- `lib/review.py`: the keystone interface `review_diff(diff, profile, specialists=None,
  *, runs=1) -> ReviewResult`. One path, two callers (live gate and eval). Stable
  fingerprint (path + category + normalized summary, never the line number), dedup that
  keeps the highest-confidence finding and records every specialist that raised it, and a
  confidence gate (daily 8, deep 2). Pluggable backend: `ClaudeCLIBackend` for production,
  `ScriptedBackend` for deterministic tests.
- `lib/specialists/`: prompt-driven reviewers for the squish profile (numerics,
  memory-bandwidth, concurrency, api-surface, red-team). Run in parallel; red-team runs
  last and sees the others' findings. Selection comes from the profile and diff_scope.
- `lib/diff_scope.py` (was a stub): maps a changed-file list to scope booleans
  (SCOPE_RUST/MLX/MOJO/SWIFT/PYTHON/PROMPTS/BENCH/DEPS/DOCS), with an MLX content sniff.
- `lib/review_log.py`: one structured record per review run on the jsonl store
  (review/<branch>-reviews.jsonl), inheriting injection-reject and HIGH-secret block.
- `lib/specialist_stats.py` (was a stub): folds the review log into per-specialist
  dispatches, findings, hit rate, and a tag (ACTIVE, GATE_CANDIDATE, NEVER_GATE insurance
  set, INSUFFICIENT_DATA below the sample-size floor of 10).
- `evals/runner.py` and `bin/konjo-eval` (were stubs): the meta-gate harness. Runs the
  real `review_diff` over the corpus `runs` times (default 3), records per-run detection
  plus the aggregate, exits nonzero on a missed CRITICAL bug or a control that fired.
- `bin/konjo-review`: the live review CLI. `bin/konjo-stats`: the specialist-stats table.

### Changed (Phase 0 corrections from the validation)

- C1: re-checked squish against disk; it was again unreachable, so the UNVERIFIED markers
  in `profiles/squish.yml` remain rather than being fabricated.
- C2: `lib/self_update.sh` now reattaches a detached HEAD to the default branch when the
  pin is removed, so an unpinned update no longer silently no-ops forever. New bash test.
- C3: `bin/konjo-newonly` scans the base ref in a `git worktree` so the working tree is
  never touched, with a clean-tree refusal as the fallback. New dirty-tree test.
- C4: `lib/self_update.sh` fetches only the tracking remote, not `--all`.

### Honest results

- Kill-test passes: `konjo-eval` flags squish/dtype_promotion at numerics/CRITICAL on
  every run (3/3) and stays silent on _clean_control on every run (3/3). The clean control
  held silent across all specialists, including api-surface on a purely additive optional
  parameter.

### Still stubbed (Phase 2)

- `bin/konjo-oneway` (one-way-door confirm), the MEDIUM-secret interactive confirm, and
  the CI packages (`konjo-gates-py`/`-rs`/`-js`). The 30-run paired Wilcoxon prove-baseline
  comparison is referenced as the next step; this sprint records the detection metrics it
  will consume.

## [0.1.0] - 2026-06-23

Phase 0: the foundation substrate plus the squish pilot, with specified Phase 1+ stubs.

### Added

- Shared substrate:
  - `lib/jsonl_store.py`: atomic append-only JSONL store, injection-rejected,
    redact-scanned, tolerant read.
  - `lib/redact.py`: three-tier secret scanner (HIGH blocks, MEDIUM confirms, LOW
    surfaces), no MEDIUM-to-HIGH promotion.
  - `lib/prose_lint.py`: editorial lint (em dashes and the AI-tell wordlist).
- Konjo Ledger:
  - `ledger/engine.py`: event-sourced decide/supersede/redact with computed "active".
  - `ledger/schema.md`: the event schema and org/repo scoping.
  - `bin/konjo-decision`: the Ledger CLI.
- CLIs:
  - `bin/konjo-prose`: prose lint over files and globs, blocking and `--warn` modes.
  - `bin/konjo-newonly`: net-new-findings-only wrapper for strict gates on existing code.
- Distribution:
  - `install.sh`: clone-or-update to `~/.konjo/kiban`, create `~/.konjo/state`.
  - `lib/self_update.sh`: throttled, failure-safe, pin-aware fast-forward self-update.
  - `plugins/konjo/hooks/preamble_update.sh`: the skill-preamble update hook.
- Session plane skills: `konjo` (umbrella), `decide`, `recall`.
- Profiles: `_schema.yml`, `squish.yml` (seeded, unverifiable fields marked UNVERIFIED),
  `_template.yml`.
- Org defaults (`defaults.yml`) and consuming-repo templates (`templates/`).
- Eval corpus: `evals/README.md`, the `dtype_promotion` and `_clean_control` fixtures.
- Docs: `README.md`, `docs/DISTRIBUTION.md`, `docs/design/`.
- Tests for the substrate, Ledger, prose lint, and self-update.

### Stubbed (Phase 1+, contract specified, no logic)

- `bin/konjo-eval`, `bin/konjo-oneway`.
- `lib/diff_scope.py`, `lib/specialist_stats.py`.
- `evals/runner.py`.
- `packages/konjo-gates-py`, `-rs`, `-js`.

[0.2.0]: https://github.com/konjoai/kiban/releases/tag/v0.2.0
[0.1.0]: https://github.com/konjoai/kiban/releases/tag/v0.1.0
