# Changelog

All notable changes to kiban are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.11.0] - 2026-08-03

Sprint P1, Phase 1 of the review-pipeline plan, kiban's half: the plan-artifact schema
and the telemetry fields it feeds. The Planner/Executor split itself (tool profiles,
the Rust `PlanArtifact` type, the handoff) lives in lopi; see lopi's `CHANGELOG.md`
`[0.41.0]` and `LEDGER.md`'s `Review-Pipeline-Phase-1` entry for the full PF-1 through
PF-4 pre-flight and the live kill-test results. No critic, router, or gate shipped
here, per the plan's own Phase 3 boundary.

### Added

- **`schemas/plan_artifact.schema.json`** - JSON Schema (draft 2020-12) for the plan
  artifact a readonly Planner emits: `goal`, `scope`, `invariants`, `test_strategy`,
  `non_goals`, `predicted_tier`, `planner_model`, `planner_commit`, all required.
  `scope.minItems: 1` is the load-bearing constraint (section 2.4's fail-open fix): an
  absent, empty, or schema-invalid scope must fail this schema, not read as "no scope
  escape possible" to a future router. `predicted_tier` documented at the field
  definition as granting zero routing authority (section 7.4).
- **`lib/plan_artifact_schema.py`** - hand-written validator (not a generic JSON
  Schema engine; that would be premature machinery for one schema), reading the
  schema file's own declared `required`/`minItems` at import time rather than
  duplicating them as literals, so a schema edit that loosened the scope constraint
  would be caught by `test_schema_still_declares_scope_min_items_one` going red, not
  silently accepted. `validate`/`is_valid`/`validate_strict`, 9 tests: rejects empty
  scope, missing scope, and schema-invalid scope as three distinct cases, plus
  round-trip and unknown-field checks.
- **`ledger/pr_telemetry.py`: `PrTelemetryRecord.predicted_tier`/`planner_scope`/
  `planner_model`/`planner_commit`**, plus `apply_plan_artifact()` (reuses
  `lib.plan_artifact_schema.validate` rather than re-validating by hand, so a record
  can never carry an unvalidated scope). Named `planner_scope`, not `scope`: the
  record's existing `scope` field already means ledger scope (`org` versus
  `repo:<name>`); reusing that name would have silently collided two meanings.
  Verified with one real end-to-end record (the live Planner run's actual output,
  built in lopi this sprint), round-tripped through the JSONL store with all four
  fields non-null and every critic field still null.

## [1.10.0] - 2026-08-03

Sprint P0, Phase 0 of the review-pipeline plan (`KONJO_REVIEW_PIPELINE_PLAN.md`). Builds
the measurement instrumentation the plan needs before any gate, critic, or router is
justified — no gate, critic, or router shipped, per the sprint's own non-goals. Full
reasoning, the two tooling corrections to the plan, and the honest partial/null results:
`LEDGER.md`'s `Review-Pipeline-Phase-0-1`.

### Added

- **`kiban bench` (`bin/kiban-bench`, `lib/bench.py`)** — one-shot coverage/mutation/test/
  build-timing baseline, per repo, using each repo's own tools (`cargo llvm-cov nextest` +
  `cargo mutants` for Rust, `pytest --cov` + `mutmut` for Python — not tarpaulin, which
  neither target repo uses). Full-repo mutation scope, distinct from the diff-scoped
  `cargo-mutants --in-diff` gate already wired into `konjo_gates_py.cli` and lopi's own
  CI. Writes a dated JSON artifact plus a compact record to `bench/<repo>-bench.jsonl`.
- **Per-PR telemetry schema (`ledger/pr_telemetry.py`, documented in `ledger/schema.md`)**
  — a third sibling stream on the jsonl_store substrate (append-only, injection-rejected,
  secret-scanned), not a Decision Ledger event. All 23 Phase-0 fields defined now (11
  git-derivable, 12 live-capture-only including the critic fields, null until Phase 3).
- **`kiban-backfill` (`bin/kiban-backfill`, `lib/backfill.py`)** — walks a repo's merge
  history and populates the git-derivable telemetry fields. `trigger_surface_hits` and
  `weakening_markers` use real `syn`-based detectors, not regex, per the plan's explicit
  instruction; grep is used only for the one case the plan permits it (`continue-on-error:
  true` in workflow YAML).
- **`packages/konjo-ast-diff-rs`** — new `syn`-based Rust binary, before/after AST delta
  for one file: identical/body-changed/signature-changed classification by qualified
  function name, plus net-new `unsafe`, `.unwrap()`/`.expect()`, `#[allow(...)]`,
  `#[ignore]`, removed asserts, removed test functions, and a syn-matched subset of
  trigger-surface call paths (subprocess, deserialization, network egress, sql, ffi,
  concurrency, crypto). Not a repurposing of the phase-1 `konjo-gates-rs` stub.

### Fixed

- `bin/kiban-bench`'s subprocess timeout handling left orphaned worker processes (a
  killed `mutmut run` left ~1.8GB workers running); `_run` now kills the whole process
  group on timeout.
- `bin/kiban-bench`'s Python coverage/test-count parsing assumed a `"N passed"` summary
  line and a fixed-column `TOTAL` row; both assumptions broke on squish's real config
  (`--cov-fail-under=100` suppresses the summary line; branch coverage adds columns).
  Test count now comes from counting `-q` progress-line outcome characters.

## [1.9.0] - 2026-07-29

Phase 14, "The Measurement Harness." Phase 13 shipped the seam and the contract; it
did not ship the thing it was named for -- KT-13.1 found no task-to-diff loop existed
to run the empirical protocol Phase 2's six candidate invariants needed. This sprint
builds that loop, runs it for real against `konjoai/lopi`, closes the classifier gap
from 3 to 7 of 8 defect taxonomy classes, and runs a real (if small) slice of Phase 3
-- finding, along the way, two real bugs in its own measurement instrument, fixing
both before publishing any number. Verdict: no candidate ships this sprint either,
this time on real evidence of an honest null rather than an infeasible protocol. See
`.konjo/killtests/P14/`.

### Added

- **`lib/gen_runner.py` + `evals/gen_cassettes.py` + `konjo-eval genrun`** -- the
  task-to-diff loop KT-13.1 named as missing: an isolated `git worktree`, explicit
  context injection (`--append-system-prompt`), a spend ceiling, and a cassette
  record/replay pair matching `evals/cassettes.py`'s pattern for the review gate.
  Two real environment findings shaped its defaults: `--dangerously-skip-permissions`
  is refused under root by the installed CLI, and `--bare` mode's
  `ANTHROPIC_API_KEY`-only auth fails closed in this remote session (no key, only a
  host-managed provider token) -- confirmed directly, not assumed. Defaults to
  `--permission-mode acceptEdits` + an explicit tool allowlist, non-bare; both
  overridable for a caller with its own key. `.konjo/killtests/P14/KT-14.1.md`.
- **`lib/defect_shapes.py`** -- mechanical scans for `missing_timeout`,
  `untyped_error_boundary`, and `missing_test_failure_path`, growing
  `evals/genfixtures.py`'s mechanically-classified count from 3 to 7 of 8 (the eighth,
  `unbounded_queue`, is a zero-new-code reuse of `lib.threat.classify`'s existing
  `RESOURCE_LIMITS` reason). `raw_index_external_input` stays `None` -- recorded as
  genuinely not classifiable at diff-grep granularity, not merely undone. Four new
  hand-authored, real-defect-modeled fixtures (`evals/gen_fixtures/04`-`07`), each
  confirmed to actually fire its target classifier. `LEDGER.md`'s
  `Defect-Classifier-Gap-1`.
- **KT-14.2 fix**: `run_gen_corpus`'s `totals` dict initialized every class to `0` and
  only incremented the classified ones -- an unclassified class read as "0 defects,"
  indistinguishable from clean. Fixed to stay `None` until a fixture actually
  classifies it. `.konjo/killtests/P14/KT-14.2.md`.
- **A real slice of Phase 3**: 2 real feature-shaped lopi tasks (deliberately distinct
  from KT-14.1's defect-fix tasks, to avoid confounding "reduces incidental defects"
  with "followed an explicit instruction"), 3 conditions (baseline, candidate 3
  "bounded queues/timeouts/retries," candidate 5 "typed error boundaries"), 3 runs
  each -- 18 real sessions. The measurement caught a real bug in its own instrument:
  test-helper code (`mod tests { ... }`, `.unwrap()` in test setup) was scoring
  identically to production defects, contradicting the org's own real convention ("No
  unwrap()/expect() outside tests"). Fixed
  (`lib.defect_shapes.added_lines_excluding_test_scope`, and a narrowed
  `SUBPROCESS_EXEC` pattern in `lib/threat.py` that no longer matches
  `tokio::spawn`/`thread::spawn`) before either report was finalized. After the fix,
  every one of 20 successful sessions classified completely clean, on both tasks, in
  every condition -- an honest null: neither tested candidate had a non-zero baseline
  rate to measure a reduction against. `.konjo/killtests/P14/phase3-report.md`,
  `LEDGER.md`'s `Phase-3-Real-Measurement-1`.
- **`gate_claude_contract` flips to blocking for lopi** (`profiles/lopi.yml`) -- the
  real standing-violation count measured against lopi's current `CLAUDE.md` is zero
  (Sprint S13R already converted it). Stays advisory, explicitly and with the real
  count recorded, for squish and vectro (4 of 6 required sections missing on both).
  `docs/pilots/squish-claude-md.proposed.md` and `docs/pilots/vectro-claude-md.
  proposed.md` -- the prepared conversions, following the lopi Phase 13 precedent,
  each verified for real against `lib.claude_contract.check_contract` before being
  recorded. `LEDGER.md`'s `Claude-Contract-Ramp-1`.

### Fixed

- **`lib/threat.py`'s `RESOURCE_LIMITS` diff hint** had no `re.MULTILINE` on its `$`
  anchor, so it only ever matched a diff's last line regardless of where the risky
  call actually was -- silently near-inert since it shipped in Phase 13. Also grew to
  catch `unbounded_channel()`/`unbounded()` (tokio's and crossbeam's explicitly named
  unbounded constructors), not just bare `channel()`. Found while wiring
  `unbounded_queue`'s mechanical reuse; `gate_threat_model`'s live behavior benefits
  too, not just this harness's reuse of it.
- **`templates/repo-ci.yml`'s example `KIBAN_REF`** bumped from a stale `v1.1.0` to
  `1.9.0`, with a real, live consequence cited inline: `konjoai/vectro`'s actual copy
  of this file was still pinned at `v1.1.5`, ~7 minor kiban releases behind, meaning
  vectro's only genuinely-blocking kiban gate predates `gate_polarity`,
  `gate_can_fail`, the doc-integrity gate, and all of Phase 13. Found while
  reconciling squish/vectro's gates; the fix itself does not (cannot, from read-only
  access) touch vectro's own copy -- flagged in `NEXT_SESSION_PROMPT.md`.
- **`profiles/vectro.yml`**: `cargo-audit` promoted from `contract_gates`
  (documentation-only) to `format_lint` (real dispatch) -- the generic dispatcher
  support already existed (added for lopi, Phase 13), so this is a one-line
  reclassification.

### Found, not fixed here (real, deliberately out of scope)

- **Squish's and vectro's own "Wall 2" CI is almost entirely decorative.** Reading
  both repos' real `konjo-gate.yml` in full found nearly every check step wrapped in
  `continue-on-error: true`; squish's Wall 2 blocks a merge on exactly one condition
  (new-file size), vectro's blocks on none at all (its real enforcement is the
  separate, stale-pinned `konjo-gates.yml`). This is the same defect class
  `konjoai/lopi`'s own PR #182/#184 found for lopi's CLAUDE.md self-claims, found
  here independently for two more repos' CI YAML. Recorded, not fixed -- rewriting
  either repo's CI is a deliberate decision for that repo's own maintainers, out of
  this phase's "connect what exists" non-goal. `LEDGER.md`'s
  `Squish-Vectro-Gate-Reconciliation-1`.
- Squish has never connected `konjo-gates` to its CI at all (no equivalent of
  vectro's `konjo-gates.yml` / lopi's Sprint S13R Phase A). Flagged for squish's next
  sprint.
- Candidates 1, 2, 4, 6 of the six drafted invariants remain entirely unmeasured this
  sprint -- candidate 1 by the sprint brief's own stated low priority
  (`gate_polarity` already catches its shape deterministically), 2/4/6 simply not
  reached inside this session's real live-model budget.
- The full 12-20 task × 3 run × 6-candidate protocol (252-420 sessions at the brief's
  own floor) was not affordable inside this session on top of the harness, classifier,
  and gate-ramp work also required -- stated plainly per this project's own
  established precedent, not silently shrunk.

## [1.8.0] - 2026-07-29

Phase 13, "The Authoring Gate." Every quality mechanism in kiban ran against a diff that
already existed; the only artifacts shaping code *before* it was written (the umbrella
skill, `craft`) contained no invariant about code, and the pilot repo (`konjoai/lopi`)
was pinned to kiban but ran a parallel bespoke gate, importing nothing. This sprint
connects the pilot, makes the CLAUDE.md contract mechanical, adds a pre-implementation
trust-boundary seam, and builds the harness needed to measure whether authoring-context
changes work at all -- and, per its own pre-flight kill-test, does NOT add the six
candidate always-on invariants drafted for it, because the empirical protocol needed to
justify them (12-20 tasks, 3 runs each, against real closed work) proved infeasible to
run with integrity inside this sprint. See `.konjo/killtests/P13/KT-13.1.md`.

**Correcting the brief's own version target**: this sprint's brief named itself
"Phase 13 (1.2.0)"; kiban had already reached 1.7.0 by the time it was worked (six
sprints landed since the brief was drafted). Per the brief's own instruction to correct
baseline drift rather than carry it forward, this ships as 1.8.0 (minor: additive gates
and schema fields, no breaking change to the profile schema or gate contract), not 1.2.0.

### Added

- **`gate_claude_contract`** (`lib/claude_contract.py`) -- checks a changed root
  `CLAUDE.md` against a fixed section order (org rules, stack, commands, invariants,
  repo map, repo-specific rules) and requires every bullet under an invariants/hard-rules
  heading to name its enforcing gate or say `ADVISORY`. Also flags a changed
  `.claude/rules/*.md` file where a majority of lines carry a sprint/date citation (the
  incident-log shape, not the invariant shape). Ships `claude_contract.advisory: true` by
  default. Fixture pair: `tests/test_claude_contract.py`; kill-test:
  `.konjo/killtests/P13/KT-13.P1.md`.
- **`templates/repo-CLAUDE.md`** rewritten to carry the section contract, with
  per-section `decays:` stamps (`## Stack`, `## Commands`, `## Repo map`) via
  `lib/doc_staleness.py`'s new `parse_section_front_matter`/`check_sections`, extending
  the `decays:` convention from whole-document to section granularity.
- **`konjo-threat`** (`bin/konjo-threat`, `lib/threat.py`) -- brief-time classifier and
  record for an eight-class trust-boundary taxonomy (authn/authz, secret lifecycle,
  deserialization, subprocess/exec, path handling, network ingress, SQL construction,
  resource limits). `classify` gives a heuristic hint; `record` refuses an empty
  mitigation, an empty abuse case, or an unlisted boundary name, logs to the Ledger, and
  prints the `Konjo-Threat-Model: <fingerprint>` trailer (reusing
  `oneway.make_trailer`/`find_trailer`, no new override channel).
- **`gate_threat_model`** in `cli.py` -- checks a diff matching a profile's new
  `security_globs` for the recorded trailer; never re-classifies. Ships blocking (no
  advisory ramp -- opt-in via `security_globs`, no existing-repo baseline to clean up).
  Fixture pair: `tests/test_threat.py` + `tests/test_konjo_gates.py::test_threat_model_*`;
  kill-test: `.konjo/killtests/P13/KT-13.P3.md`.
- **`security_globs`** in `profiles/_schema.yml`, mirroring `longrun_globs`. Routing
  reuses a newly-generalized `_glob_match` helper (extracted from what was
  `_is_longrun_path`) so the `**`-handling fnmatch logic exists once, not three times.
- **`craft` skill**: a "Pre-implementation contract" section -- before code crossing a
  trust boundary, introducing a queue, spawning a process, or parsing external input:
  name the boundary, state the mitigation, name the abuse case, name the test.
- **`templates/sprint-brief.md`** -- originated (no file defined this shape before,
  though sprint briefs following it already existed), carrying `TRUST BOUNDARIES`/
  `ABUSE CASES` per-phase fields.
- **`evals/genfixtures.py` + `konjo-eval gen`** -- a new fixture shape distinct from the
  existing review-fixture corpus: a `task.json` + `candidate.diff` pair, classified
  against an eight-class defect taxonomy. Three classes are classified mechanically by
  reusing existing detectors (`lib.redact` for secrets, `lib.polarity` for permit
  branches, `lib.threat` for exec hints); five report `None` (unclassified), never
  silently zero. Seeded with three illustrative fixtures under `evals/gen_fixtures/`
  (hand-authored, not live-generated -- see `.konjo/killtests/P13/KT-13.1.md`). Wired as
  a report-only step in kiban's own `.github/workflows/ci.yml` (`continue-on-error: true`,
  the command itself always exits 0). Kill-test: `.konjo/killtests/P13/KT-13.P4.md`.
- **`profiles/lopi.yml`** -- the pilot repo's first kiban profile, reconciled against the
  real `konjoai/lopi` repo (read-only this session). `cargo-audit` genuinely promoted
  into `konjo-gates`' generic tool dispatcher; nine other real checks (coverage ratchet,
  mutation reporting, dead code, DRY, rustdoc, scope assertion, reachability,
  soft-gate-lint, adversarial review) kept repo-native by explicit decision, per Phase
  0's own non-goal ("improving any gate. This phase connects what exists."). Full
  decision table in `LEDGER.md`'s `Lopi-Gate-Reconciliation-1`.
- **`docs/pilots/lopi-claude-md.proposed.md`** -- the converted `lopi/CLAUDE.md`,
  prepared but not applied (this session holds no push access to `konjoai/lopi`); found,
  on applying the new contract to a real file, that 5 of lopi's 6 "Critical Constraints"
  have no mechanical enforcement today.
- Four of `lopi`'s sprint-cited `.claude/rules/security.md` lines converted through
  `konjo-learn` (all four found a home in this sprint's new `subprocess_exec`/
  `network_ingress` enforcement chain; see `LEDGER.md`'s `Learn-Loop-Seed-1`).

### Not done here, on purpose

Phase 2 (the always-on invariant set) does not ship. KT-13.1 found the specified
empirical protocol (12-20 real closed-work tasks, 3 runs each, classified against a
fixed taxonomy) infeasible to run with integrity inside this sprint -- the
implementation-task harness it depends on did not exist (`konjo-headless` is a thin
`claude -p` wrapper, not a task-to-diff loop), and building it under time pressure while
also running the full protocol would trade rigor for the appearance of rigor, which
KT-13.1's own FAIL condition ("the taxonomy cannot be applied consistently") exists to
catch. KT-13.2 (context budget headroom) passed on its own -- 1018 tokens of headroom
against a ~144-token candidate set -- but headroom alone does not justify shipping an
unmeasured invariant. The six candidates are recorded in `LEDGER.md` as drafted, not
measured, not added, for a future session with the harness this sprint built
(`evals/genfixtures.py`) and the resource budget to run it at the specified scale.

squish and vectro: Phase 0's gate-reconciliation and CLAUDE.md-conversion depth (done
for lopi this sprint) is explicitly deferred for both -- their `profiles/*.yml` were
already reconciled in earlier sprints; what's still open is recorded in `LEDGER.md`'s
`Lopi-Gate-Reconciliation-1` addendum.

## [1.7.0] - 2026-07-26

Sprint K1 ("Failure Semantics"), Family 0 of the birth-defect gate proposal derived
from lopi's F0/F1 findings. Every kiban gate, every lopi CI gate, coverage, and the
dead-code check were green while three lopi sites answered "I could not evaluate this"
with a bare pass -- `run_verifier_pass` returning `true` with no API client configured
gated L4 auto-merge to main with no human sign-off, for the verifier's entire
existence. Not a regression: wrong on the first commit, and every existing ratchet
(coverage floor, `newonly`, doc staleness) measures against a baseline, so none of them
could have caught it. This sprint builds the two gates that catch that shape.

### Added

- **`lib/polarity.py` (G-POLARITY engine)** -- detects a branch whose condition tests
  *absence or failure to evaluate* (`let ... else`, `.is_none()`, `.unwrap_or(...)`, a
  match/switch arm on the error or default case; Python's `except`/`is None`/`.get(k,
  default)`; TypeScript's `??`/`if (!x)`/`catch`) that returns a *permissive* value
  (bare `true`, `1.0`, `Ok(())`). Per-language packs under `lib/packs/lang/{rust,
  python,typescript}/polarity.py`. The separating signal is the condition's *shape*,
  not its content: a domain check (`until_satisfied`, a bare `if proceed`) never
  matches any pattern here, by construction, so it is never flagged -- confirmed by
  KT-K1.1 (`.konjo/killtests/K1/KT-K1.1.md`), which required this engine to correctly
  separate lopi's three real birth defects from two reference-correct shapes
  (`verifier_error_proceeds`, `zero_diff_is_success`) using the exact fixture set
  assembled *before* the engine was written. One deliberate restriction found while
  building the fixture set: a bare terminal `else` is only treated as a "default/
  unrecognised case" when preceded by at least one `else if` (a 3+-way dispatch) --
  this is what keeps `scorer.rs`'s legitimate `if skip_build_check { test_pass_rate =
  1.0 }` branch from being swept in alongside the real defect four branches later in
  the same function, both setting the identical constant.
- **`gate_polarity` in `cli.py`** -- the CI gate, net-new findings only (added lines
  score against the base version of the same file, the same pattern `gate_prose`
  already uses). A finding resolves via an explicit operator-override field in the
  returned expression (the `verifier_fail_open` precedent,
  `polarity.is_explicit_override`), the new `Konjo-Polarity-Waived: <fp> — <reason>`
  commit trailer (fingerprint-bound via the existing `oneway.fingerprint`/
  `find_trailer`/`make_trailer` -- no second override channel), or it fails, naming
  the file, line, condition, and returned value. `polarity.enabled`/`advisory`/
  `exempt_globs` in `profiles/_schema.yml`; ships `advisory: true` by default (WARN,
  not FAIL) so an adopting repo can clean its baseline before flipping to blocking --
  the same coverage-floor ratchet pattern used elsewhere. KT-K1.2
  (`.konjo/killtests/K1/KT-K1.2.md`) confirmed the waiver is bound to the exact
  changed-file fingerprint and does not survive a change to that file set.
- **`gate_can_fail` in `cli.py` (G-CAN-FAIL)** -- "a green run is not evidence a gate
  works, only a red one is." For each entry in the profile's new `gates:` list (name +
  `rejects_test` command), the gate actually runs the command and requires it to
  exist and pass. Cannot verify the test's *content* is adversarial (that it exercises
  the hard input, not the easy one) -- only that a rejecting test is declared, named,
  and green; this limit is stated in the gate's own doc comment and in
  `KONJO_FORWARD.md`. KT-K1.3 (`.konjo/killtests/K1/KT-K1.3.md`) surveyed lopi's and
  squish's real CI: both have enumerable, already-named gate sets (lopi's G0-G5,
  squish's `contract_gates`/`mutation`), so this ships as a real gate, not a
  convention-only checklist item.
- **`KONJO_FORWARD.md`** -- did not exist on disk before this sprint, despite being
  cited as an established doc by the birth-defect proposal and this sprint's own
  brief. Originated here rather than silently assuming a history it didn't have: the
  three pillars, "the thing that governs the work lives outside the work," the two
  rejections this sprint adds (permissive unknowns, tests as proof of wiring), and the
  residual limit ("gates can guarantee nothing ships unverified; they cannot guarantee
  the verification was adequate").
- `profiles/_schema.yml`: `polarity:` and `gates:` blocks.
- `tests/test_polarity.py`, `tests/test_polarity_killtest.sh`,
  `tests/test_can_fail_killtest.sh`.

### Changed

- `plugins/konjo/skills/konjo-ship/SKILL.md`: the self-graded checklist line "Zero
  debug artifacts, dead code, or leftover scaffolding" -- walked past on exactly the
  defect it existed to catch, because the agent that wrote the code was also the one
  checking the box -- is replaced by two commands: `konjo-gates polarity` clean (or
  waived on the record), and every quality gate this sprint touched has a rejecting
  test. Net +1 line over the prior cap-exact 80-line budget; carries a recorded
  `konjo-skill-size-ok:` justification (a one-way door, see `LEDGER.md`).
- `lib/oneway.py`: gains `POLARITY_WAIVED_TRAILER = "Konjo-Polarity-Waived"`, reusing
  `fingerprint`/`find_trailer`/`make_trailer` unchanged.

### Not done here, on purpose

G-WIRED, G-CLAIM, G-CLAIM-ARTIFACT, G-REACH, G-ADVERTISED (Families A-C of the
birth-defect proposal) -- K1 is Family 0 only. Fixing lopi's three real sites is
lopi's own F1, not this sprint's; K1 used lopi as the fixture source and stops there
(see `NEXT_SESSION_PROMPT.md` for the K2 handoff).

## [1.6.0] - 2026-07-25

Wall 3's live gate sampled its own noisiest, highest-stakes judgment -- is this diff
safe to merge -- exactly once. The reviewer is an LLM: a real defect a specialist
catches 60% of the time is missed 40% of the time, silently, on a single pass. The
eval harness already refused to trust one sample (`evals/runner.py`'s `DEFAULT_RUNS`
is 3, and has been since the eval harness shipped); this release brings the live gate
up to the same bar, and adds a small confidence refinement on top of the union/`per_run`
machinery `review_diff` already had.

### Changed

- `lib/review.py`: `review_diff`'s `runs` default changes from `1` to the new
  `DEFAULT_LIVE_RUNS = 3`, matching `evals/runner.py`'s `DEFAULT_RUNS` -- the blocking
  merge review must not sample the noisy reviewer process less than the eval that
  validates its detection rate. `bin/konjo-review`'s `--runs` default follows suit
  (was `1`, now `review.DEFAULT_LIVE_RUNS`). Both remain overridable: pass `runs=1` /
  `--runs 1` for a fast/daily manual check where a single pass is an acceptable
  tradeoff. **Cost**: each additional run is a full extra specialist dispatch per
  selected specialist -- a real model call in every consuming repo's CI -- so this is
  a considered ~3x cost multiplier on the blocking review, not a silent one. Cheap
  insurance on the merge path, which is the whole point: Wall 3 runs once per PR, not
  once per keystroke.
- `Finding` gains a `recurrence: int` field (default `1`): the number of the review's
  runs that independently produced this finding (post per-run confidence gate,
  pre-dedup). `review_diff` now bumps a merged finding's confidence based on
  recurrence across `per_run` -- unanimous agreement (+2, capped at 10), a majority
  of runs (+1), a single run (+0) -- via the new `_apply_recurrence` step run after
  the union/dedup. **Recall is unaffected**: a finding produced on only one of N runs
  is never dropped from the blocking review; recurrence only raises confidence for a
  finding that already cleared the per-run gate, it never gate-keeps existence. No
  change to the specialist set, lens set, or severity model.
- `Finding.to_record()` includes `recurrence` in its output (the CLI `--json` output
  and `review_log` entries now carry it). The prior-findings context embedded in the
  red-team specialist's prompt (`_user_prompt`) explicitly excludes `recurrence` when
  serializing prior findings -- that stat is only meaningful after all runs merge (it
  is always `1` mid-run) and including it would have shifted every recorded
  cassette's prompt hash for no reason. Cassettes recorded before this release remain
  valid.

## [1.5.0] - 2026-07-25

Wall 3 (the specialist review gate) is the last line of defense -- a different model
grading the diff, the one wall that catches what deterministic gates cannot -- but
`lib/review.py` documented its own hole: any dispatch failure (a CLI timeout, an
`OSError` launching the process, or a non-zero exit) returned empty text, which the
parser reads identically to "the specialist reviewed the diff and found nothing." A
network blip or a rate limit silently removed a reviewer with no signal, and
`SpecialistReport.dispatched` (true once an attempt was made, not once it succeeded)
gave a caller nothing to check instead. This release makes the gate fail closed, the
same posture lopi's verifier and `jsonl_store` already hold elsewhere in the framework.

### Changed

- `ReviewBackend.dispatch` now returns `str | None`: `None` means the specialist did
  not complete, distinct from `""` (which no backend now returns for a real failure).
  `ClaudeCLIBackend.dispatch` returns `None` on `TimeoutExpired`, `OSError`, *and* a
  non-zero CLI exit -- previously a non-zero exit only logged and still returned
  `stdout`, so partial output from a failed process could be parsed as valid findings.
- `SpecialistReport` gains `failed: bool` and a `completed` property
  (`dispatched and not failed`), set from the real call outcome rather than the
  attempt. `dispatched` is unchanged (an attempt was made) so existing readers of that
  field keep their current meaning.
- `ReviewResult` gains an `incomplete` property: true if any selected specialist
  failed to complete after its retry. **A caller gating a merge on the review must
  treat `incomplete` as block-or-retry, never as a pass** -- an INCOMPLETE result
  carries no information about whether the diff is actually clean, so it must never
  read the same as dispatched-with-zero-findings.
- `review_diff`'s per-specialist dispatch now retries once on a `None` reply before
  marking that specialist failed -- a single transient timeout or CLI blip no longer
  hard-blocks a merge; only a failure that survives the retry does. Mirrors the
  verifier's retry-then-fail-closed shape. A clean review (every specialist completes,
  zero findings) is unaffected: `incomplete` is false and the verdict is exactly as
  easy to pass as before.
- `bin/konjo-review` (the live CLI gate) now exits 1 on `result.incomplete`, printing
  which specialist(s) failed to complete, regardless of whether any finding was
  produced -- previously only a CRITICAL/HIGH finding blocked, so an incomplete review
  with zero findings passed silently.
- `evals/runner.py`'s `FixtureResult` carries the same `incomplete` state (the eval
  harness calls the identical `review_diff`, per the module's "one function, two
  callers" design): an incomplete fixture fails the run without being misreported as
  a missed bug or a fired control, both of which would point a session at the wrong
  fix. `packages/konjo-gates-py`'s `gate_self_test` surfaces `incomplete_fixtures` in
  its FAIL detail alongside `missed_bugs`/`false_positive_controls`.
- `evals/cassettes.py`'s `RecordingBackend` no longer caches a failed live dispatch as
  a cassette entry (which would make every future replay of that fixture silently pass
  as clean); it propagates `None` instead.
- `lib/review_log.py` records each specialist's `completed` flag and the review's
  overall `incomplete` state, so `konjo-stats` history shows a failed dispatch instead
  of folding it into a zero-finding dispatch count.

### Fixed

- The two failure paths from the sprint's kill-test were both live bugs: (1) a timed
  out or crashed specialist previously read as `dispatched=True` with zero findings,
  identical to a clean pass; (2) a non-zero CLI exit returned `stdout` anyway, so a
  process that errored out with partial output on stdout could have that output parsed
  as valid findings rather than discarded.

## [1.4.1] - 2026-07-25

Feedback on 1.4.0, in two rounds. First: `doc_staleness` gives the repo a way to
*detect* a stale `state` doc, but nothing made detection lead anywhere —
`konjo-ship`'s checklist only re-verified docs "touched by this sprint's changes," so a
doc nobody happens to touch can go stale from time alone, with no session ever
assigned to fix it. Second, on the first fix itself: requiring a sprint to clean up
*every* repo-wide FAIL before shipping just swaps one failure mode (silent rot) for
another (a small, unrelated task blocked behind someone else's pre-existing debt) —
exactly the "CI fails randomly and often" outcome to avoid. `doc_staleness` itself was
never wired into a blocking CI check (confirmed by grep of `konjo-gates-py` and every
workflow); the fix below is entirely at the skill-prose level.

### Fixed

- `plugins/konjo/skills/craft/SKILL.md`: added a "doc staleness check" step, run
  before any non-trivial build step (best-effort — skips silently if the CLI or the
  convention isn't present in a given repo yet). A `FAIL` on a doc the current task
  actually relates to is investigated and fixed: re-stamped if the claim still holds,
  rewritten if it does not, or reclassified `historical` with a superseded banner if
  abandoned — never re-stamped without being checked, which would recreate the exact
  dishonesty `decays:` exists to catch. A `FAIL` unrelated to the current task is
  noted, not fixed mid-build.
- `plugins/konjo/skills/konjo-ship/SKILL.md`: the checklist runs
  `konjo-doc-staleness scan` repo-wide (not just this sprint's changed files, closing
  the original gap), but only a FAIL this sprint's changes relate to blocks shipping.
  Unrelated pre-existing debt is surfaced in a new `DOC DEBT` line in the Session
  Handoff Template instead — visible every session, never silently forgotten, without
  taxing work that has nothing to do with it.

## [1.4.0] - 2026-07-24

A source-level audit of `konjoai/lopi` found a roadmap doc asserting four capability
gaps (no MCP, no real worktrees, no runtime skill engine, no maker/checker split) that
were all closed on `main`. The cause was structural: `konjo-ship`'s Sprint Completion
Checklist enumerates three filenames by name, so every doc created after the checklist
was written is born unmaintained. This release makes "what the docs claim about
current state" a gate a sprint can check instead of prose a sprint has to trust.

### Added

- The `decays:` front-matter convention (documented in
  `plugins/konjo/skills/craft/SKILL.md`): every doc that asserts current-state facts
  declares a class — `state` (decays every sprint, highest harm when stale),
  `reference` (moderate horizon), `intent` (long horizon), or `historical` (append-only,
  never decays, exempt by declaration). A worked example for each class, including the
  case for an expiry banner on an otherwise-honest dated snapshot.
- `lib/doc_staleness.py` + `bin/konjo-doc-staleness`: scans a repo for `decays: state`
  docs and fails the ones whose `verified-against` has fallen too far behind `HEAD`
  (default 20 commits / 14 days). A `state` doc with no `verified-against` stamp at all
  is a hard fail — the unstamped case that caused this whole sprint. `historical` docs
  are exempt but warn if they lack a visible dated banner; `intent`/`reference` warn
  only, regardless of age; a doc with no front matter at all is reported, not crashed
  on. 19 unit tests, plus a live integration check against a real `konjoai/lopi` clone:
  the repo currently has zero stamped docs (an honest finding, not a bug), and a
  scratch copy of its roadmap stamped as it would have been at the commit that
  introduced it fails loudly — 440 commits / 32 days behind `HEAD`.
- `Konjo-Doc-Verified` commit trailer, joining `Konjo-Acknowledged-Oneway`
  (`lib/oneway.py`) and `Konjo-Prove-Merge` (`lib/prove.py`) on the same
  record-and-check path (`oneway.make_trailer`/`find_trailer`,
  `oneway.fingerprint(doc_paths)`) rather than a fourth ad hoc format.
- `plugins/konjo/skills/konjo-ship/SKILL.md`: the sprint completion checklist and
  session handoff template, absorbed into the global plane (see `LEDGER.md`). It
  previously existed only as a hand-copied, byte-identical `.claude/skills/konjo-ship`
  in `konjoai/lopi` and `konjoai/miru`, with no canonical source and no distribution
  path. The checklist no longer names filenames: it requires `CHANGELOG.md`,
  `LEDGER.md`, and re-verifying every `decays: state` doc a sprint touched
  (`konjo-doc-staleness scan` is the discovery step, not memory), plus the property
  "no doc in the repo asserts a capability state that contradicts the code."
- Per-repo override path documented in `docs/DISTRIBUTION.md`: a repo-scoped
  `.claude/skills/<name>/SKILL.md` wins over an identically-named global skill, using
  Claude Code's existing most-specific-wins skill resolution — no new plumbing.

### Changed

- `plugins/konjo/skills/konjo/SKILL.md` (the always-on umbrella skill) now routes to
  `konjo-ship` alongside `craft`, `decide`, `recall`, `longrun`, and `konjo-prose`.

## [1.3.0] - 2026-07-13

The `repo:cargo-mutants` gate ran `cargo mutants` with no scoping, so every Rust PR
mutation-tested the *entire* crate -- the single most expensive gate, and (per the 1.2.0
heartbeat work) the classic ~20-minute silent CI block. The consuming repo's own CI already
solved this: `konjo-gate.yml`'s G3 gate runs `cargo mutants --in-diff`, mutating only the
changed lines. This release brings the kiban gate to G3 parity.

### Changed

- `repo:cargo-mutants` now runs `cargo mutants --in-diff <diff> --jobs N --timeout SECS`.
  `--in-diff` restricts mutation to the lines changed in the PR (the merge-base-to-working-tree
  diff, matching what the net-new scan already compares against), so the gate mutates a handful
  of lines instead of the whole crate. `--jobs` parallelizes the surviving mutants across cores;
  `--timeout` bounds each mutant's test run so a mutation that induces an infinite loop can't
  hang the gate forever. This is the same scoping `konjo-gate.yml` G3 already applies.
  - The diff is written to a temp file whose absolute path is handed to cargo-mutants and
    cleaned up when the gate returns; it resolves from both the HEAD checkout and the throwaway
    base worktree the net-new scan runs in. An empty diff (nothing changed) is passed through as
    a fast no-op rather than falling back to a whole-crate run. If git cannot produce a diff at
    all, the gate falls back to cargo-mutants' whole-crate default.
  - `--jobs` and `--timeout` default to `4` and `120` seconds and are overridable per-repo via
    `KONJO_MUTANTS_JOBS` / `KONJO_MUTANTS_TIMEOUT` (a non-numeric or non-positive value falls
    back to the default rather than breaking the gate), so a consuming repo can tune them in CI
    without a profile-schema change. No consuming-repo change is required otherwise -- bumping
    the pin is enough.

## [1.2.0] - 2026-07-10

A consuming repo (`konjoai/pdfree`) reported a `konjo-gates` CI job that ran for ~20
minutes producing no output at all and then failed, with no way to tell which gate was
responsible or where the wall-clock went. The cause was structural, not a bug: the
orchestrator runs ~a dozen gates back to back, several of which shell a scanner out
*twice* (once at HEAD, once at the base ref in a throwaway worktree) with the child's
output captured rather than streamed, and it prints the per-gate result table only once
every gate has finished. A slow compiling or mutation gate (`clippy`, `cargo-mutants`,
`mutmut`, `stryker`) therefore blocked in silence, and a failure surfaced only at the very
end. To an operator that reads as a hung job.

### Added

- `lib/progress.py`: the single source of truth for CI-plane heartbeat logging. Emits to
  stderr, flushed per line, with a `log()` always-on level and a `vlog()` verbose level,
  plus `fmt_elapsed` so a 20-minute gate renders as `20m04s` at a glance.
- `konjo-gates` now writes an **always-on** per-gate heartbeat to stderr: a
  `[i/total] <gate>: running...` line as each gate starts and a
  `[i/total] <gate>: <status> (<elapsed>)` line when it finishes, bracketed by a startup
  banner and a total-elapsed line. No consuming-repo change is required -- bumping the pin
  is enough. The CI log now shows which gate is in flight and where the time goes.
- `konjo-gates --verbose` (or `KONJO_GATES_VERBOSE=1`, which also reaches child modules and
  subprocesses) adds per-scanner detail from `lib/newonly.py`: the exact scanner argv and
  each of the two HEAD/base scan passes with its own duration and finding count -- the
  concrete answer to "why is *this one* gate slow" (it runs the scanner twice).

### Changed

- `konjo-gates` builds its gate list as an ordered plan of `(label, thunk)` pairs and runs
  them through a single timed, logged loop, so a gate's label is announced *before* it
  runs. Repo-native gate thunks bind their tool with `functools.partial` (not a late-bound
  loop closure), preserving correct per-tool dispatch.
- `templates/repo-ci.yml`: documents the heartbeat and how to enable `--verbose`.

## [1.1.5] - 2026-07-01

The `v1.1.4` fix closed the compile-duration and shared-cache false-positive modes, but
`repo:clippy` (and, to a lesser extent, `repo:cargo-mutants`) still failed on real PRs
after that release. Reproduced from a real `konjoai/vectro` CI run (PR #104): `gates`
reported 8 "net-new" `repo:clippy` findings on a PR whose own local `cargo clippy -- -D
warnings` was clean. Two independent, still-live bugs, both in `lib/newonly.py`:

1. **ANSI escape codes defeat line-number normalization.** `dtolnay/rust-toolchain`
   forces `CARGO_TERM_COLOR=always` whenever the caller hasn't already set it, so every
   `cargo clippy` diagnostic ships pretty-printed with color codes wrapped around the
   source-snippet line-number gutter (`"\x1b[94m221\x1b[0m | ..."`). `_NUM_RE` needs a
   `\b` word boundary on *both* sides of a digit run to normalize it away, but a digit
   glued to an escape code's trailing letter (`"94m"`, `"0m"`) is a word-to-word
   transition -- no boundary, no match. Two of the 8 "findings" were a single real,
   completely unmodified `if self.dim == 0` clippy diagnostic in `ivf.rs` that merely
   shifted line (221 at HEAD, a different line at the merge-base) because the PR added
   code earlier in the same file -- exactly the case `_NUM_RE` exists to normalize away,
   defeated by the surrounding color codes it was never taught to strip first.
2. **cargo's own build-progress noise gets diffed as if it were a lint finding.** The
   other 6 of the 8 "findings" were bare `"   Checking crossbeam-channel v0.8"` /
   `"   Compiling vectro_py v8.17 (rust/vectro_py)"` lines -- cargo's own right-justified
   status output, carrying no diagnostic at all. The HEAD scan runs in the real checkout
   (a warm, cache-restored `target/`); the base-ref scan runs in a throwaway `git
   worktree` with no cache, so it always starts colder. Which crates print a fresh
   "Compiling"/"Checking" line is a function of that incremental-build cache asymmetry,
   not of the diff being scanned, so for any tool that compiles this noise can differ
   between the two scans on genuinely unmodified source -- an unremovable false net-new
   that has nothing to do with line numbers or durations.

### Fixed

- `lib/newonly.py`: `_normalize` now strips ANSI CSI/SGR escape sequences
  (`\x1b\[[0-9;]*[A-Za-z]`) before any other normalization runs, so a colorized line
  number normalizes exactly like a plain one.
- `lib/newonly.py`: cargo/`Shell::status`-style build-progress lines (`Compiling`,
  `Checking`, `Downloading`, `Finished`, `Updating`, ... -- cargo's fixed, documented
  verb list) are filtered out of both the HEAD and base-ref finding sets entirely,
  rather than normalized, since they carry no diagnostic content to compare.
- Added regression tests in `tests/test_newonly.py`: one reproduces the exact
  ANSI-wrapped, line-shifted diagnostic from the `vectro` CI run and confirms it no
  longer looks net-new; another reproduces the asymmetric build-noise lines and
  confirms they're never treated as findings even when they differ between scans.

## [1.1.4] - 2026-07-01

Fixes the last piece of the `repo:*` net-new false-positive saga (`v1.1.1`-`v1.1.3`):
`repo:clippy` and `repo:cargo-mutants` -- the two `lang/rust` gates that actually
compile the crate -- kept reporting pre-existing, unmodified findings as net-new even
after the `v1.1.2` root-stripping fix, while `repo:fmt-check`/`repo:cargo-deny` (which
never compile anything) stayed clean. Reproduced from a real `konjoai/pdfree` CI run:
`repo:clippy` failed with a single "net-new finding" that was not a lint at all -- it
was `cargo`'s own build-status line, "Finished \`dev\` profile [...] target(s) in
12.94s", half-normalized to "... in N.94s".

### Fixed

- `lib/newonly.py`: `_NUM_RE` was `\b\d+\b`, which requires a word boundary on both
  sides of the digit run. A digit run immediately followed by a letter -- a unit
  suffix, as in every compile/test duration cargo prints ("12.94s", "1s build + 5s
  test", "12m") -- is a word-to-word transition, not a boundary, so the trailing `\b`
  never matched and the duration was left completely untouched (or, for a decimal like
  "12.94s", only the whole-number part before the "." was stripped). Since wall-clock
  duration is never identical between the HEAD scan and the base-ref scan, any line
  containing one produced a permanent false net-new -- and `cargo-mutants` prints one
  in nearly every `MISSED`/`CAUGHT` line, not just a build-summary footer, so this was
  effectively 100% false positives for that gate. `_NUM_RE` now consumes a recognized
  unit suffix (`ms`, `min`, `ns`, `s`, `m`, `h`) as part of the digit token before
  checking the trailing boundary, so the whole duration collapses to a single `N`
  regardless of its actual value.
- `lib/newonly.py`: `_run` now scrubs `CARGO_TARGET_DIR` from the scanner's environment
  before invoking it. Left inherited, a CI job that sets it globally (a common caching
  optimization) would point the HEAD scan (the real checkout) and the base-ref scan (a
  throwaway `git worktree` at an unrelated path) at the *same* build/incremental cache
  directory, scanned back-to-back -- letting one compilation's cached state leak into
  the other's for a compiling tool (`clippy`, `cargo-mutants`) and produce a spurious
  diff on genuinely unmodified source. Removing the var (rather than repointing it)
  lets each tool fall back to its own cwd-relative default, isolating the two scans
  regardless of the ambient environment.
- Added regression tests in `tests/test_newonly.py`: one reproduces the exact
  half-normalized duration string from the `pdfree` CI log and confirms it no longer
  looks net-new; another simulates a compiling tool leaking state through a shared
  `CARGO_TARGET_DIR` and confirms the two scans no longer contaminate each other.

## [1.1.3] - 2026-07-01

Fixes a robustness gap flagged while chasing the `v1.1.1`/`v1.1.2` `repo:*` gate bugs
from a consuming repo (`pdfree`): a PR that touches a binary-ish file without a
`.gitattributes` entry marking it binary can leak raw non-UTF-8 bytes into `git diff`
output. `konjo-gates`'s own diff/base-file readers decoded that output with Python's
default strict UTF-8 handling and crashed with `UnicodeDecodeError` before any gate
ran at all -- a crash that depends on the *consuming* repo's `.gitattributes`, not on
anything kiban controls, so `konjo-gates` should not depend on it either.

### Fixed

- `packages/konjo-gates-py/src/konjo_gates_py/cli.py`: `_git` and `_base_file` now
  decode subprocess output with `errors="replace"` instead of Python's default strict
  UTF-8 decoding, so a diff or `git show` containing non-UTF-8 bytes degrades to
  replacement characters instead of crashing the whole gate run.
  - Added a regression test in `tests/test_konjo_gates.py` that commits a file with
    non-UTF-8 bytes past git's binary-detection sniff window and confirms `_diff_text`
    returns instead of raising.

## [1.1.2] - 2026-07-01

Fixes a second, independent bug that `v1.1.1` unmasked: after fixing the packaging
defect that stopped the `repo:*` cargo gates from running at all, re-running `gates` on
a real VECTRO Rust PR still failed `fmt-check`, `clippy`, and `cargo-deny` -- this time
against the *entire* repo's pre-existing lint backlog (46 files), not the PR's own diff,
and `cargo-deny` again "failed" with no dependency change in the diff.

### Fixed

- `lib/newonly.py`: `cargo fmt --check`, `cargo clippy`, and `cargo deny check` all print
  **absolute** file paths, rooted at whatever directory the tool was invoked from. HEAD
  is scanned in the real checkout; the base ref is scanned in a throwaway `git worktree`
  under a fresh `tempfile.mkdtemp()` path -- a different absolute root on every run. A
  finding on a file the PR never touched, on the identical line, therefore never matched
  between the two scans: the leading absolute path differed, so `_normalize` (which only
  ever collapsed line/column numbers) left every one of those findings looking net-new
  forever. `_normalize` now also takes the root each scan actually ran from and strips
  it, so head/base findings for an untouched file compare equal regardless of which
  absolute directory each scan used.
  - `_findings_at_base`: a failed `git worktree add` used to return an empty set,
    silently treating "the scan didn't run" as "nothing was found" -- which would flag
    every HEAD-side finding as net-new for the same reason. It now returns `None`, and
    `net_new` reports a real ERROR instead of a false-positive net-new FAIL.
  - Added regression tests in `tests/test_newonly.py` and `tests/test_konjo_gates.py`: a
    scanner that prints an absolute path rooted at its own cwd (mirroring real `cargo
    fmt --check` output) confirms a pre-existing finding on an untouched file passes,
    while a genuinely new finding on a changed file still fails.

## [1.1.1] - 2026-07-01

Fixes a bug reported from the real VECTRO repo: the `repo:*` gates that shell out to
cargo (`fmt-check`, `clippy`, `cargo-deny`, `cargo-mutants`) reported `[FAIL] ...
net-new findings` on every Rust PR, unconditionally and independent of the real diff
(observed: `cargo-deny` "failing" on a diff with zero dependency changes; the full
~18-gate battery completing in ~0.4s, too fast for any real compile).

### Fixed

- `gate_repo_native` invoked `KIBAN_ROOT / "bin" / "konjo-newonly"` as a subprocess.
  That path only exists in a source checkout: the root distribution's
  `[tool.setuptools] packages` list never included `bin/`, so once kiban is
  pip-installed (the CI plane's actual install path, per `templates/repo-ci.yml`) the
  script is not on disk. `KIBAN_ROOT` itself also resolves to the install prefix, not
  the (nonexistent, post-build) source tree, once installed. The subprocess call
  failed instantly (`python: can't open file ...`, exit 2, empty stdout) before ever
  reaching cargo; `gate_repo_native`'s only fallback path for a nonzero exit with no
  stdout was the literal string `"net-new findings"`, so the failure looked identical
  to a real, blocking finding on every Rust-scoped PR, regardless of toolchain
  presence or diff content.
  - Moved the net-new diffing engine from `bin/konjo-newonly` into `lib/newonly.py`
    (`net_new(scanner, base) -> NetNewResult`), which ships with the installed
    distribution the same way `lib/unsafe_budget.py` already does. `gate_repo_native`
    now calls it in-process; `bin/konjo-newonly` is a thin CLI wrapper over the same
    function, kept for direct/manual use.
  - `gate_repo_native` now reports the tool's real net-new finding text on FAIL
    (previously a single hardcoded string), and a distinct ERROR when the comparison
    itself could not be established (no merge-base, dirty tree with no worktree
    support), instead of folding every failure mode into "net-new findings".
  - Added a probe (`cargo <subcommand> --version`) for `cargo-deny` / `cargo-mutants`:
    `cargo` being on PATH says nothing about whether the subcommand plugin is
    installed, and running the gate against a missing plugin produced the same
    generic-failure symptom. A missing plugin is now a distinct
    tool-unavailable ERROR.
  - `tests/test_konjo_gates.py`: a stub `cargo` drives the four Rust gates through a
    clean diff (PASS), a dirty diff (FAIL with the real finding text), a
    dependency-free diff for `cargo-deny` (PASS), a missing-subcommand case for
    `cargo-mutants` (ERROR, not a false FAIL), and a regression test that points
    `KIBAN_ROOT` at a directory with no `bin/` at all to prove the gate no longer
    depends on that path existing.

## [1.1.0] - 2026-06-30

The Mojo language pack. The fourth language pack (after python/mlx, rust, typescript),
prompted by the real VECTRO repo: it carries a substantial Mojo surface (38 `.mojo` files,
`src/vectro_mojo`, `experimental/mojo`, Mojo tests) that the rust/python/typescript profile
missed. `diff_scope` already emitted `SCOPE_MOJO`; this gives it review depth.

### Added

- `lib/packs/lang/mojo`: three Mojo-specific lanes for a SIMD quantization codebase:
  - `mojo-memory`: `UnsafePointer` out-of-bounds load/store, manual alloc with no free,
    aliasing, wrong `owned`/`borrowed`/`inout` convention, use-after-`^`-transfer.
  - `mojo-numerics`: `SIMD[dtype, width]` mismatches, unsafe `cast`/`bitcast`, fixed-width
    overflow, a dropped saturating clamp before an int8 cast, precision loss on the quant path.
  - `mojo-perf`: needless value-semantics copies of large buffers, a hot loop left scalar
    where `vectorize`/`parallelize` was meant, a missing `@always_inline`/`@parameter`,
    allocation in a hot loop.
  The shared `concurrency`, `api-surface`, and `red-team` lanes now cover `SCOPE_MOJO` and are
  reused (`api-surface` gained `SCOPE_MOJO`; scope metadata only, so existing prompts and
  cassettes are byte-unchanged).
- `mojo-format` / `mojo-test` tools wired into `konjo-gates-py` under `SCOPE_MOJO` (`mojo
  format --check`, `mojo test`), each through konjo-newonly. A repo wires them only if its CI
  has the Mojo toolchain.
- `_STACK_TO_PACK` maps `mojo` to `lang/mojo`; `pyproject.toml` ships the package.
- `profiles/mojo_example.yml` (seeded) and a Mojo eval corpus under `evals/fixtures/mojo/`:
  `oob_simd_store`, `quant_overflow`, `needless_copy`, `pub_signature_break_mojo`, plus
  `_clean_control_mojo`. Cassettes recorded against a live model and ACTIVATED: the replay is
  deterministic across three runs, each bug in the right lane (two at CRITICAL, the others at
  the model's honest severity, the control silent).

### Changed

- `profiles/vectro.yml`: added `mojo` to the stack, packs, specialists, and eval corpus. The
  specialist list keeps `api-surface` last and places the Mojo lanes after `concurrency` so
  each language's `diff_scope`-filtered worker order matches its recorded corpus order
  (the red-team cassette key depends on it; recorded as a learning in 1.0.1).
- Templates pinned to v1.1.0.

### Kill-test (measured)

- All prior invariants hold: Squish six-cassette replay deterministic with no re-record; Rust
  and TypeScript replays green; the frozen prompt-hash test green (api-surface byte-unchanged
  despite the new scope). Mojo corpus ACTIVATED and green over `mojo_example` and `vectro`
  (which now replays all 15 fixtures: 6 Rust, 4 TypeScript, 5 Mojo) deterministically, no
  re-record of the existing cassettes. Full pytest: 141 passed (+4 new).

## [1.0.1] - 2026-06-30

Post-1.0 activation: reconcile `profiles/vectro.yml` against the real VECTRO repo. The first
of the carried activation steps, done as the evolution plan intended (the squish.yml
precedent). No engine change.

### Changed

- `profiles/vectro.yml` reconciled against `konjoai/vectro` (added to the session read-only,
  not modified). Confirmed and UNVERIFIED marks cleared from its real state:
  - Stack `[rust, python, typescript]`: a Rust core (`rust/vectro_lib`) with Python bindings
    (`rust/vectro_py`, `python/`) and a JS binding (`js/`, TypeScript types). Packs derive to
    `lang/rust`, `lang/python`, `lang/typescript`.
  - `format_lint` and `contract_gates` taken from `.github/workflows/konjo-gate.yml`
    (cargo fmt/clippy with pedantic + unwrap/expect/panic denied, ruff, ruff-format, mypy,
    vulture; cargo-deny with `.konjo/deny.toml`, cargo-audit, 80% coverage via
    `cargo llvm-cov nextest`, complexity, the 500-line limit, `dry_check.py`, rustdoc
    missing_docs) plus the kiban-native `unsafe-budget`. `mutation: cargo-mutants`.
  - The prove gate wired to VECTRO's real bench: metric `qps` (queries per second at fixed
    recall@10, higher is better), `bench_cmd: ./reproduce_paper.sh --wave 1 --runs 3`. Per the
    house rule, `min_effect_pct` stays `null` PENDING (measured on the bench host, never
    invented); the gate stays NOT ACTIVATED and keeps blocking perf changes while inert.
  - `verify_cmd: cargo nextest run --workspace && python -m pytest tests/ -q` and
    `format_cmd: cargo fmt --all && ruff format .`, both confirmed from CI.
  - `eval_corpus: [rust, typescript]`, VECTRO's two reviewed binding surfaces. The specialist
    list is ordered so `api-surface` (shared) comes last, so each scope's filtered worker
    sequence matches its recorded corpus order; the Rust and TS cassettes replay
    deterministically across three runs with no re-record.
- Templates pinned to v1.0.1.

### Kill-test (measured)

- VECTRO replay green and deterministic across three runs over all ten fixtures (six Rust,
  four TypeScript), no re-record. Squish and ts_example replays unchanged. konjo-gates
  kill-test green. Full pytest: 137 passed.

## [1.0.0] - 2026-06-30

Phase 12: the context-budget guardrail, the skill-size limit, and the TypeScript pack. The
1.0.0 cut. The framework now holds itself to the token-efficiency it preaches, and the
generalization the pack seam promised reaches a third language. Cut only because the
context-budget gate is green on the core itself.

### Added

- `lib/context_budget.py` + two report-only gates in the orchestrator:
  - `gate_context_budget`: the always-on context (the umbrella skill, ethos included) must
    stay under a token ceiling (default 1500, profile `context_budget_tokens`). Tokens are a
    model-free estimate (chars/4) so the gate is deterministic offline. The core measures
    ~463 tokens, well under the ceiling. Packs and the on-demand skills are never always-on,
    so they do not count.
  - `gate_skill_size`: no single SKILL.md over a line cap (default 80, profile
    `skill_line_cap`) without a recorded `konjo-skill-size-ok:` justification. The craft skill
    carries that justification (it holds all ten field notes by design and is opt-in).
- The TypeScript pack (`lib/packs/lang/typescript`): `type-soundness` and `async-correctness`
  lanes; the shared `api-surface` and `red-team` lanes now cover `SCOPE_TS` (scope metadata
  only, so existing prompts and cassettes are byte-unchanged). `TOOLS`: `tsc`, `eslint`,
  `stryker`, `npm-audit`.
- TS tools wired into `konjo-gates-py` (`tsc --noEmit`, `eslint`, `stryker run`, `npm audit`),
  each through konjo-newonly, exactly as the Rust tools are. `npm-audit` is the JS realization
  of the supply_chain universal gate.
- `profiles/ts_example.yml`: a SEEDED TypeScript profile (no real JS repo was piloted, so
  every field is UNVERIFIED) driving the TS eval corpus.
- TS eval corpus under `evals/fixtures/typescript/`: `type_soundness_any_cast`,
  `floating_promise`, `pub_signature_break_ts`, plus `_clean_control_ts`. Cassettes recorded
  against a live model and ACTIVATED: the replay is deterministic across three runs, with each
  bug detected in the right lane and at the right severity on the first try (no expectation
  adjustment needed) and the control silent.
- `context_budget_tokens` and `skill_line_cap` profile fields, documented in
  `profiles/_schema.yml`.

### Changed

- `_STACK_TO_PACK` maps `ts` and `typescript` to `lang/typescript`.
- `pyproject.toml` packages: added `lib.packs.lang.typescript`.
- `konjo-gates-js` README updated: TypeScript is enforced through the single Python
  orchestrator (`konjo-gates`), exactly as Rust is; the Node-native runner stays a stub until
  a JS-first CI is piloted, keeping one source of truth for the gate logic.
- Templates pinned to v1.0.0.

### Kill-test (measured)

- Context-budget gate green on the core (~463 of 1500 tokens); skill-size gate green (craft
  justified). TS corpus ACTIVATED: all four fixtures green and deterministic across three runs
  (three must-flag at the right lane and severity, one control silent).
- All prior invariants hold: Squish six-cassette replay deterministic with no re-record; Rust
  replay green; konjo-gates, oneway, prove, learnings, longrun, and hooks kill-tests green.
- Full pytest: 137 passed (121 from 0.11 plus 16 new across context-budget and the TS pack).

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
