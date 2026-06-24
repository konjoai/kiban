# Changelog

All notable changes to kiban are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2026-06-24

Phase 5: complete the squish pilot so it is trustworthy before any propagation. The eval
corpus now covers all four squish specialists, and the squish prove gate is wired against
the real benchmark and honestly inert until its threshold is confirmed.

### Added

- Eval corpus grown to all four squish specialists. New fixtures, each a planted bug with
  a clean control where useful:
  - `squish/memory_bandwidth_copy`: an MLX `mx.tile` that materializes a full value-cache
    copy every decode step, doubling bandwidth on the hot path (memory-bandwidth).
  - `squish/concurrency_race`: a removed lock leaving shared status/counter state raced
    across worker threads (concurrency).
  - `squish/api_contract_break`: renamed OpenAI-compatible response fields with no version
    bump (api-surface).
  - `_clean_control_mlx`: a comment-only MLX change, a silence control.
  All four specialists flagged their planted bug on the first try at CRITICAL; no prompt
  needed improving and no fixture was weakened. Cassettes re-recorded so `--replay` covers
  all six fixtures deterministically.
- `lib/bench_squish.py`: the adapter from squish's thermal bench JSON
  (`configs[id].phases[p4000].e2e_runs[].total_s`) to the konjo-prove artifact, with
  `konjo-prove adapt` to build an artifact from one or more bench files.

### Changed

- `profiles/squish.yml` prove block wired against the real bench (read over HTTPS from
  konjoai/squish): `bench_cmd`, metric `e2e_200tok_s`, the adapter, `run_floor` 30. The
  honest finding that `bench_v5_1.RUNS == 5` (below the floor) is documented in the
  activation checklist.
- `bin/konjo-prove`: a PENDING `min_effect_pct` now yields `NOT ACTIVATED` (exit 3)
  instead of a verdict, so the gate never passes a perf change silently while inert.
- Template pinned to v0.6.0.

### Pending (not invented)

- `min_effect_pct` for squish stays PENDING USER CONFIRMATION. It must be derived from
  run-to-run jitter measured on the M3 bench hardware (unavailable in the build
  environment). The activation checklist in `profiles/squish.yml` is the procedure.

### Kill-test

- `konjo-eval run --replay` flags all four bug classes at the right category and CRITICAL
  and stays silent on both controls, deterministic across three runs. The squish prove
  path produces a verdict when a threshold is supplied and reports NOT ACTIVATED while
  PENDING. See `tests/test_prove_killtest.sh`.

### Still deferred (Phase 6+)

- konjo-gates-rs / -js, the second repo profile (propagation behind pins), and the
  supply_chain universal gate.

## [0.5.0] - 2026-06-23

Phase 4: the prove gate. A 30-run paired Wilcoxon signed-rank perf test that turns a
perf claim into a MERGE / NOISE / REGRESSION verdict, with the house rule that
significance alone never merges. Scoped to the prove gate; squish profile wiring is
deferred (the repo was not reachable this sprint).

### Added

- `lib/prove.py`: a pure-Python paired Wilcoxon signed-rank test (normal approximation,
  tie and continuity corrections, zero-difference handling, an n floor defaulting to 30),
  and the verdict rule. MERGE requires p<0.05 AND a median improvement at or above
  min_effect in the correct direction. A significant but sub-threshold effect is NOISE; a
  significant wrong-direction effect beyond min_effect is REGRESSION. No scipy dependency,
  so no stats can leak toward CI.
- `bin/konjo-prove`: runs locally on the bench hardware. Ingests a paired measurement
  artifact (it does not run the benchmark), renders the verdict, appends to BENCHMARKS.md
  and prove.jsonl, logs a Ledger ack, and on MERGE emits the commit trailer CI checks.
  `konjo-prove baseline capture` records a tagged golden baseline.
- konjo-gates `prove` gate: on a perf-labeled change (SCOPE_BENCH or a profile perf glob)
  it checks the commit messages for the MERGE trailer, reusing the Phase 3 record-and-check
  path. No MERGE record FAILs with guidance; the gate imports no stats and runs no benchmark.
- The profile schema gains the prove fields (metric, unit, lower_is_better, min_effect /
  min_effect_pct, run_floor, perf_globs, bench_cmd).

### Changed

- `defaults.yml`: the prove universal gate is documented.
- `templates/repo-ci.yml`: pin bumped to v0.5.0.

### Deferred

- squish prove wiring: squish was unreachable this sprint (the proxy scoped to kiban
  only). The metric, unit, and direction in `profiles/squish.yml` are from the Phase 2
  read; the load-bearing min_effect and the bench command are left as TODO rather than
  guessed, to be confirmed against bench_thermal_h2h.py when squish is reachable.

### Kill-test

- konjo-prove renders MERGE / NOISE (sub-threshold) / NOISE (non-significant) / REGRESSION
  from synthetic paired data, emitting a MERGE trailer only on MERGE; the CI prove gate
  fails a perf change with no MERGE record and passes one with it. See
  `tests/test_prove_killtest.sh`.

### Still deferred (Phase 5)

- konjo-gates-rs / -js, other-repo profiles (propagation behind pins), eval corpus growth
  and cassette re-record, and the supply_chain universal gate.

## [0.4.0] - 2026-06-23

Phase 3: the safety layer for decisions a pass/fail gate should not make alone. A
one-way-door classifier, a reusable typed-confirm flow, the MEDIUM-secret confirm, and
the release-tag discipline. Scoped to the safety confirms plus the tags.

### Added

- `lib/oneway.py` + `bin/konjo-oneway` (was a stub): classify a change as one-way
  (schema/migration, public-API removal, data delete, key rotation, release actions) or
  two-way. Errs toward one-way on a sensitive surface. A stable fingerprint over the
  changed-file set ties a confirmation to the change.
- `lib/confirm.py`: a reusable interactive confirm that states what is irreversible,
  requires an exact typed token (never a bare yes), requires a justification, logs an
  acknowledgement to the Ledger, and returns the commit trailer CI reads.
- `bin/konjo-secrets`: the session secret gate. HIGH blocks; MEDIUM routes to the confirm.
- konjo-gates `one_way_door` gate: classifies the change and, for a one-way door, checks
  the commit messages in base..HEAD for `Konjo-Acknowledged-Oneway: <fingerprint>`.
  Absent, it FAILs with guidance; present, it PASSes. It reads git only, never stdin, so
  it is safe in CI.

### Changed

- `defaults.yml`: the one_way_door universal gate is no longer stubbed.
- `templates/repo-ci.yml`: pin bumped to v0.4.0.
- Release-tag discipline (C-A): annotated tags backfilled for v0.1.0, v0.2.0, v0.3.0 at
  the VERSION-bump commits, and v0.4.0 for this sprint. With the release.yml workflow now
  on main, a VERSION bump cuts the release and tag server-side; the historical tags are
  the backfill. Every VERSION bump is a one-way door: classify and confirm it, log the
  release to the Ledger.

### Kill-test

- konjo-oneway classifies a public-API break and a data delete as one-way and a comment
  change as two-way; the confirm refuses a vague reply and logs on a valid typed token;
  the CI gate fails an unacknowledged one-way change and passes the acknowledged one. See
  `tests/test_oneway_killtest.sh`.

### Still deferred

- The 30-run paired Wilcoxon prove gate (Phase 4), eval corpus growth and cassette
  re-record (Phase 4/5), `konjo-gates-rs`/`-js` and other-repo profiles (propagation,
  later), and the supply_chain universal gate (Phase 5 candidate).

## [0.3.0] - 2026-06-23

Phase 2: the CI plane enforces. A real konjo-gates orchestrator blocks a pull request,
and the eval gains a deterministic offline mode so it can be a CI gate. Scoped to the
CI-enforcement plane and the squish pilot.

### Added

- `packages/konjo-gates-py` (was a stub): the CI-plane orchestrator. Reads a repo
  profile, routes changed files through `lib.diff_scope`, and runs the kiban-native gates
  (prose net-new, secrets via `redact.scan_diff`, the self_test replay eval, report-only
  specialist stats) plus the profile's repo-native gates, each wrapped in `konjo-newonly`
  so only net-new findings block. Imports the real `lib`/`evals` engine; reimplements
  nothing. CLI `konjo-gates`, plus a `bin/konjo-gates` checkout launcher.
- Eval determinism (C-A): `evals/cassettes.py` with a `RecordingBackend` (captures the
  live replies once) and a `ReplayBackend` (serves them with no model and no network; a
  miss is a hard error). `konjo-eval record` writes cassettes; `konjo-eval run --replay`
  is the deterministic CI path and is the default when cassettes exist. Cassettes for the
  two fixtures are committed.
- `lib.redact.scan_paths` and `scan_diff` (C-D): path and added-line secret scans reusing
  `scan()`, for the CI secrets gate.
- Root `pyproject.toml`: the whole repo is now the installable distribution, shipping the
  engine and cassettes with the `konjo-gates` entry point (single source of truth).
- Tests: cassette record/replay determinism, the redact path/diff scans, orchestrator
  routing and net-new discipline, and a no-model/no-network kill-test bash script.

### Changed

- C-B: `profiles/squish.yml` reconciled against the real squish repo (cloned read-only).
  Confirmed stack (python, mlx; the Phase 0 "swift" was wrong), format_lint
  (ruff, ruff-format, mypy, vulture, bandit), contract gates (coverage-80, complexity,
  file-size-500, dry, docs-80), mutation (mutmut), and the prove baseline
  (benchmarks_v5_1_1). All nine UNVERIFIED markers dropped. squish was not modified.
- C-C: `templates/repo-ci.yml` installs the pinned `kiban` distribution at v0.3.0 and
  runs `konjo-gates` with the replay eval (no model in CI).
- C-D: relabeled the stale `phase-1` TODO markers in `bin/konjo-oneway` and `defaults.yml`
  to phase 3; silenced the git warnings in the self_update test fixture.

### Kill-test

- In a no-`~/.konjo`, no-`claude`, no-network environment, konjo-gates passes a clean
  diff, fails a net-new prose violation, fails a HIGH secret, and runs the self_test
  replay as a gate. See `tests/test_konjo_gates_killtest.sh`.

### Still stubbed (Phase 3)

- `bin/konjo-oneway` (one-way-door confirm), the MEDIUM-secret interactive confirm, the
  30-run paired Wilcoxon prove baseline, and `konjo-gates-rs`/`-js`.

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

[0.6.0]: https://github.com/konjoai/kiban/releases/tag/v0.6.0
[0.5.0]: https://github.com/konjoai/kiban/releases/tag/v0.5.0
[0.4.0]: https://github.com/konjoai/kiban/releases/tag/v0.4.0
[0.3.0]: https://github.com/konjoai/kiban/releases/tag/v0.3.0
[0.2.0]: https://github.com/konjoai/kiban/releases/tag/v0.2.0
[0.1.0]: https://github.com/konjoai/kiban/releases/tag/v0.1.0
