# Changelog

All notable changes to kiban are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.11.1] - 2026-06-30

Completes the craft skill against Karpathy's full field notes. Phase 10 adopted four of the
ten sections (think before coding, simplicity, surgical changes, goal-driven execution) plus
verification; the other five were evaluated and added so the skill carries the whole set.

### Changed

- `plugins/konjo/skills/craft/SKILL.md` now covers all ten build behaviors, in source order:
  read before you write (new), think before coding, simplicity first, surgical changes,
  verification (the verify-loop), goal-driven execution, debugging (new), dependencies (new,
  pointing at the supply-chain gates as the mechanical half), communication (new), and the
  common failure modes (new: Kitchen Sink, Wrong Abstraction, Optimistic Path, Runaway
  Refactor). The skill is opt-in, so the added prose does not count against the always-on
  context budget (Phase 12).
- The `konjo` umbrella skill's one-line description of `craft` updated to match.
- Templates pinned to v0.11.1.

### Kill-test (measured)

- No behavior change: 126 pytest pass; all kill-tests (konjo-gates, oneway, prove, learnings,
  longrun, hooks) green; Squish replay deterministic with no re-record. The craft skill and
  umbrella pass konjo-prose.

## [0.11.0] - 2026-06-30

Phase 11: lifecycle hooks and the headless host helper. Two narrow, opt-in hooks both tied to
verification, plus one place that builds the fast, structured `claude -p` invocation. Hooks
and preamble logic are where bloat accumulates, so two hooks is the ceiling.

### Added

- `lib/headless.py` + `bin/konjo-headless`: the headless invocation helper. `headless_argv`
  bakes `--bare` (skip discovery, ~10x faster start) and `--output-format stream-json` (a
  realtime event stream). The CLI requires `--verbose` alongside stream-json in print mode
  (verified against the installed `claude`, not assumed), so the helper adds it automatically,
  which closes the lopi `claude_stream.rs` gap by construction. `--dry-run` prints the argv a
  host should exec.
- `templates/hooks/`: opt-in lifecycle hook templates.
  - `stop-verify.sh` (Stop hook): runs the repo's `verify_cmd` when a turn ends, blocking a
    red end-of-turn (exit 2) so a long autonomous run cannot end on a red state silently.
  - `posttooluse-format.sh` (PostToolUse hook): runs the repo's `format_cmd` after an edit;
    formatting is convenience, so it never blocks (always exit 0).
  - `settings.snippet.json` + `README.md`: how to wire them into `.claude/settings.json`.
- `bin/konjo-profile-get`: reads a profile field (used by the hooks), printing nothing for an
  absent field or an honest TODO/UNVERIFIED placeholder, so a hook no-ops safely.
- `format_cmd` profile field (the repo's formatter), documented in `profiles/_schema.yml`.

### Changed

- Templates pinned to v0.11.0.

### Kill-test (measured)

- Hooks kill-test green with no model and no network: the Stop hook lets a green turn end,
  blocks a red one (exit 2), and no-ops with no `verify_cmd`; the format hook runs `format_cmd`
  and never blocks; `konjo-headless` bakes `--bare`, stream-json, and the required `--verbose`.
- All prior invariants hold: Squish six-cassette replay deterministic with no re-record; Rust
  replay green; konjo-gates, oneway, prove, learnings, and longrun kill-tests green.
- Full pytest: 126 passed (121 + 5 new). New shell scripts pass shellcheck.

## [0.10.0] - 2026-06-30

Phase 10: the craft skill. One small, opt-in skill carrying how to build the Konjo way, plus
the verify-loop made a per-repo contract. Prose, not machinery, and deliberately short, so it
carries the rules and nothing else.

### Added

- `plugins/konjo/skills/craft/SKILL.md`: the four behaviors (think before coding, simplicity
  first, surgical changes, goal-driven execution) plus the verify-loop. Routed from the
  `konjo` umbrella skill. Kept short on purpose; the context-budget gate that enforces this
  lands in Phase 12.
- `verify_cmd` profile field: how the agent verifies its own work (the test/bench/browser
  path to run before claiming done), documented in `profiles/_schema.yml`.
- `gate_verify_cmd` in the orchestrator: report-only. A repo that declares `verify_cmd`
  passes; a repo with none (or an honest TODO/UNVERIFIED placeholder) gets a WARN, a surfaced
  gap, never a hard block, the way a missing prove threshold is surfaced.

### Changed

- `profiles/squish.yml` declares `verify_cmd: pytest` (derived from its confirmed pytest
  coverage gate).
- `profiles/vectro.yml` declares `verify_cmd` as an UNVERIFIED TODO (VECTRO is parked; the
  gate honestly warns until it is confirmed against the repo).
- Templates pinned to v0.10.0.

### Kill-test (measured)

- `konjo-gates` no-model, no-network kill-test green, now reporting the `verify_cmd` gate
  (squish PASS, a missing one WARN). All prior invariants hold: Squish six-cassette replay
  deterministic with no re-record; Rust replay green; oneway, prove, learnings, and longrun
  kill-tests green.
- Full pytest: 121 passed (117 + 4 new).

## [0.9.0] - 2026-06-30

Phase 9: the long-run gate. The benchmark resume pain, generalized: any run long enough to
be interrupted must resume from a checkpoint with minimal loss. A checkpoint helper, a static
gate that enforces the contract, and a skill, on the same substrate the Ledger uses.

### Added

- `lib/packs/longrun/konjo_longrun.py`: the checkpoint/resume helper. `Checkpoint`
  (`done` / `mark` / `completed` / `results`) writes one append per completed unit to a
  progress JSONL on `jsonl_store` (atomic, redact-scanned, tolerant on read), folded
  latest-wins for unit-level idempotency. `add_resume_args` adds a mutually exclusive
  `--resume` / `--fresh` pair; `is_fresh` resolves the run mode (explicit flag wins, else the
  script's declared default). A benchmark adopts resume in about five lines.
- `gate_longrun` in the orchestrator: a static, diff-only check that a changed long-run
  script wires the resume contract (a `--resume` affordance or the helper, and a checkpoint
  write). It fires only on runnable scripts (a `__main__` guard, or a path under
  `benchmarks/` or `scripts/`), so a bench-named library is exempt. It reads files; it never
  runs the benchmark.
- `longrun_globs` profile field (default: `benchmarks/**`, `**/bench_*.py`,
  `scripts/train_*.py`), documented in `profiles/_schema.yml`.
- `longrun` skill (`plugins/konjo/skills/longrun`): the contract and how to adopt the helper;
  routed from the `konjo` umbrella.
- Tests: `tests/test_longrun.py` (the helper), `tests/test_longrun_killtest.sh` (kill at unit
  3 of 5, resume, skip 1-3, complete 4-5, match a clean `--fresh` run, and survive a corrupt
  progress line), and gate-routing tests in `tests/test_konjo_gates.py`.

### Changed

- `pyproject.toml` packages: added `lib.packs.longrun`.
- Templates pinned to v0.9.0.

### Kill-test (measured)

- Long-run kill-test green with no model and no network: an interrupted run resumes, skips
  finished units, completes the rest, equals a fresh run, and survives a corrupt progress
  line (the tolerant-read property).
- All prior invariants still hold: Squish six-cassette replay deterministic with no
  re-record; Rust replay green; `konjo-gates`, oneway, prove, and learnings kill-tests green.
- Full pytest: 117 passed (103 + 14 new).

## [0.8.0] - 2026-06-30

Phase 8: the compounding loop. The Ledger recorded decisions; kiban ported only that half.
This adds the other half the loop needs, the learnings log, so a caught mistake becomes a
durable rule instead of a one-run patch. A correction that only fixes this run is a patch; a
correction that edits the rules is a fix.

### Added

- `lib/learnings.py`: the learnings log, a sibling stream of the decision Ledger on the same
  substrate (`ledger/learnings.jsonl`). Append-only, event-sourced, redact-scanned. A
  learning is four things: the one-line mistake, the rule that prevents it, the enforcement
  target (where the rule now lives), and the scope. `redact` retires a learning without
  rewriting history.
- The guardrail: a learning MUST name an enforcement target. A learning with no target is
  not a learning, it is a note, and `LearningsLog.learn` refuses it (`MissingEnforcement`).
  This keeps the loop tied to mechanism instead of becoming a diary.
- `bin/konjo-learn`: the learnings CLI (`add`, `search`, `redact`), mirroring
  `konjo-decision`. `add` exits 4 when the enforcement target is blank.
- `correct` skill (`plugins/konjo/skills/correct`): the compounding loop, in three steps,
  recall first, write the learning (with its enforcement target), then propose the smallest
  durable fix (a CLAUDE.md line, a prose-lint word, a new lane, or a gate) and apply it on
  confirmation.
- `tests/test_learnings.py` and `tests/test_learnings_killtest.sh`: a correction writes a
  learning; a learning names an enforcement target; a learning with no target is refused and
  not stored; the recall path finds it; redact retires it. No model, no network.

### Changed

- `recall` skill extended to search the learnings log, not just decisions, so the agent
  checks "have we already learned this" before repeating a class of mistake.
- The `konjo` umbrella skill routes to `correct` and names the learnings log.
- `ledger/schema.md` documents the learnings stream and the enforcement guardrail.
- Templates pinned to v0.8.0.

### Kill-test (measured)

- Learnings kill-test green with no model and no network: a no-target learning is refused
  (exit 4) and not stored; a learning with a target is logged, found via `konjo-learn
  search`, and retired by `redact`.
- The Phase 7 invariants still hold: Squish six-cassette replay deterministic with no
  re-record; `konjo-gates`, oneway, and prove kill-tests green.
- Full pytest: 103 passed (95 + 8 new).

## [0.7.0] - 2026-06-29

Phase 7: split the review engine into an invariant core and opt-in language packs, then
ship the first new language pack (Rust) behind a second repo profile. A behavior-preserving
refactor plus one additive pack. The acceptance bar held: the six Squish cassettes still
replay deterministically with no re-record.

### Added

- The pack seam. `lib/packs/lang/_base` holds the language-agnostic specialist machinery
  (`Specialist`, `_OUTPUT_CONTRACT`, `_prompt`, `select`, the new `load_registry`) and the
  shared lanes (`concurrency`, `api-surface`, `red-team`). Each language pack exposes a
  `SPECIALISTS` tuple; `load_registry(packs)` assembles a registry from `_base` plus the
  named packs.
- `lib/packs/lang/mlx`: the `numerics` and `memory-bandwidth` lanes, moved verbatim.
- `lib/packs/lang/python`: a placeholder pack (empty `SPECIALISTS`; the Python lanes are
  deferred) with a `TOOLS` fragment naming the Python tool set.
- `lib/packs/lang/rust`: three new lanes (`ownership-lifetimes`, `error-handling`,
  `perf-alloc`) plus a `TOOLS` fragment. The shared `concurrency` and `api-surface` lanes
  from `_base` cover Rust and are reused, not redefined.
- Rust tools wired into `konjo_gates_py.cli`: `clippy` (`cargo clippy -- -D warnings`),
  `fmt-check` (`cargo fmt --check`), `cargo-deny` (`cargo deny check`), `cargo-mutants`
  (`cargo mutants`), each through konjo-newonly, and the kiban-native `unsafe-budget` gate
  (`lib/unsafe_budget.py`): a diff-only count of net-new `unsafe` blocks with no adjacent
  safety comment; a net increase fails. It reads the diff, it never builds the crate.
- `SCOPE_TS` in `diff_scope` (`.ts`, `.tsx`, `.mts`; in `CODE_SCOPES`). No TS lanes this
  sprint; the TS pack is Phase 12.
- Second repo profile `profiles/vectro.yml` (stack `[rust]`, packs `[lang/rust]`, the Rust
  specialists and contract gates, `killtest: true`). VECTRO was NOT reachable from the build
  environment, so it is SEEDED: every field not confirmed against the real repo is marked
  UNVERIFIED, and the prove block is PENDING (`min_effect_pct: null`, `bench_cmd`/`metric`
  left as TODO, with an activation checklist), exactly as squish.yml was originally seeded.
- Rust eval corpus under `evals/fixtures/rust/`: five planted bugs
  (`ownership_unsound_unsafe` -> ownership-lifetimes/CRITICAL, `unwrap_on_prod_path` ->
  error-handling/HIGH, `mutex_across_await` -> concurrency/CRITICAL, `pub_signature_break`
  -> api-surface/CRITICAL, `clone_in_hot_loop` -> perf-alloc/HIGH) plus `_clean_control_rust`
  (must be silent). Cassettes were recorded against a live model and ACTIVATED: the replay
  is deterministic across three runs (each bug detected in the right lane, the control
  silent). The reference model routed every bug to the lane the sprint specified; for two
  fixtures it assigned a higher severity than the sprint's initial guess (`pub_signature_break`
  CRITICAL not HIGH, `clone_in_hot_loop` HIGH not MEDIUM), and the expectations were set to
  the model's honest output rather than contorting the fixtures, per the plan's "refine
  against real diffs" discipline.
- New tests: `tests/test_packs.py` (registry composition + byte-stable prompt hashes),
  `tests/test_unsafe_budget.py` (the diff scanner), and Rust tool-routing / `SCOPE_TS`
  coverage in `tests/test_konjo_gates.py`.

### Changed

- `review_diff` builds the specialist registry from the profile's `packs`, deriving the
  pack list from `stack` when `packs` is absent (python -> lang/python, mlx -> lang/mlx,
  rust -> lang/rust). `profiles/squish.yml` keeps working unchanged.
- The eval corpus is now profile-scoped via an `eval_corpus` field, so each repo evaluates
  only its own fixtures. `profiles/squish.yml` gains `eval_corpus: [squish, _clean_control,
  _clean_control_mlx]`; `profiles/vectro.yml` uses `[rust]`. Without this scoping the Squish
  self-test would try to review a Rust fixture it has no cassette for.
- `pyproject.toml` packages: added the `lib.packs.*` subpackages, dropped `lib.specialists`.
- Templates pinned to v0.7.0.

### Kill-test (measured)

- Squish six-cassette replay: deterministic across 3 runs, no re-record (4 must-flag at the
  right lane/severity, 2 controls silent). Invariant 1 held.
- `konjo-gates` no-model, no-network kill-test: green (clean diff passes, prose violation
  blocks, HIGH secret blocks, self_test replay runs as a gate). Invariant 2 held.
- Rust corpus: all six fixtures ACTIVATED and green through the replay backend,
  deterministic across three runs (five must-flag at the right lane and severity, one
  control silent). Invariant 6 satisfied with a reachable model.
- Full pytest: 95 passed (77 pre-flight + 18 new: pack registry, unsafe-budget, Rust
  tool-routing, SCOPE_TS). The oneway and prove kill-tests also stay green.

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
