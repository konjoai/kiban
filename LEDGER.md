# Ledger

A running log of load-bearing design decisions — the ones that would be expensive to
silently re-litigate in a later sprint. One entry per sprint, newest first. Not a
changelog (that's `CHANGELOG.md`) — this is *why*, not *what*. (kiban's runtime
decision Ledger — `ledger/engine.py`, `bin/konjo-decision` — records the durable calls
a *consuming* repo makes during a session, scoped `org`/`repo:<name>`, in
`~/.konjo/state/ledger/decisions.jsonl`; this file is kiban's own project-level
record of its architecture, the way `lopi`'s `LEDGER.md` records lopi's.)

## Review-Pipeline-Phase-2-Addendum: bench.py bug fixes, a third PF-0 data point, a stronger PF-3 replication

**Same sprint as `Review-Pipeline-Phase-2` below (a parallel session ran concurrently
against the same lopi checkout state; this entry adds what that one didn't cover
rather than re-deriving it -- read that entry first**).

**Three real, now-fixed bugs in `lib/bench.py`, none touched by the parallel
session's work below.** Confirmed against this session's own real `outcomes.json` and
CI runs, not synthesized; all three covered by new regression tests
(`tests/test_bench_rust.py`, 3 tests, full 287-test suite green):
1. `_tests_rust`'s nextest-missing fallback checked `code == 127` (the shell's "not
   found" convention). Cargo 1.88.0 exits **101** for an unrecognized subcommand
   instead -- the fallback to `cargo test --workspace` never fired, and a missing
   `cargo-nextest` install was recorded as a genuine test failure. Now detects "no
   such command" in the output text.
2. `_mutation_rust`'s per-crate breakdown crashed (`'str' object has no attribute
   'get'`) on `outcomes.json`'s Baseline entry, whose `scenario` field is the bare
   string `"Baseline"`, not `{"Mutant": {...}}` like every real mutant entry. Now
   skips non-dict scenarios.
3. `_mutation_rust`'s `--jobs` was hardcoded to 2, leaving half a 4-core box idle on a
   run its own docstring calls "plausibly hours". Now `os.cpu_count()`.

**A third independent PF-0 attempt reached 926/5,315 mutants (17.4%) before dying
without writing a completion artifact -- further corroboration of the session-
lifecycle diagnosis below, not a contradiction of it.** Launched clean (no competing
jobs) at 22:04:23Z; last confirmed alive and progressing normally at 22:20Z (136
tested); found dead with no process, no `bench_results/lopi/` artifact, and no
completion line in its own log roughly 19 hours later. This is a *better* partial
result than either of the two attempts recorded below (544 mutants / 10.2%), which
strengthens rather than weakens the "background baseline runs do not reliably survive
this session's lifecycle" conclusion -- three independent launches, three different
stopping points, zero clean completions. Reinforces the handoff's own recommendation:
a runner that stays up unattended (dedicated CI, persistent infrastructure), not
another interactive-session background job.

**A second, independently-designed PF-3/KT-2B pilot replicated the result more
decisively: 10/10 vs 2/10** (versus 9/10 vs 7/10 below), a different sample (`lopi-
webhook`+`lopi-ratelimit` scoped run, 10 real survivors) and a different agent
topology (2 fresh-context agents, one per arm, each handling all 10 mutants, versus
15 agents below, one per mutant-arm pair). Verification was mechanical: each
candidate test had to pass against the real, unmutated crate first (voided
otherwise) before being run against the mutated source via `patch -p0` of
cargo-mutants' own diff output; FAIL-under-mutation = killed. Two of arm A's three
tests never reliably passed against real code even after one blind corrective round
(fed the raw panic output, no mutation hint) -- both tripped on the same real,
pre-existing gotcha this session's sample and the one below both independently
surfaced: `BucketState::refill()`/equivalent reads real `std::time::Instant`, not
tokio's virtual clock, so `#[tokio::test(start_paused = true)]` doesn't freeze it.
Two independent samples, two different agent counts, the same qualitative result and
the same specific failure mode in arm A's tests -- this is not one lucky run.

## Review-Pipeline-Phase-2: mutation-guided test loop -- PF-3 passed, §2 shipped, §1/§3/§4 deferred on PF-0

**Sprint P2 (`KONJO_REVIEW_PIPELINE_PLAN.md` Phase 2, the surviving-mutant -> assertion
loop). Primary repo is lopi for the pre-flight measurement work (PF-0 baseline, PF-3
kill-test); kiban's scope is the feedback formatter (section 2) plus this record. No
critic, router, or gate shipped, per the plan's own non-goals. §1 (uncovered-item
extraction), §3 (the loop + gate), and §4 (`konjo/mutation-hunt` skill) are not built
this sprint -- see the deferral reasoning below, not silently dropped.**

**PF-0: the full-workspace baseline is launched but NOT complete -- report accordingly.**
First launch attempt failed outright: `--timeout 60` bounds every cargo command
including the one-time baseline (unmutated-tree) test pass, and lopi's own
`cargo test --workspace` takes longer than 60s cold. Zero mutants ran. Relaunched with
`--timeout` omitted (cargo-mutants auto-scales the per-mutant timeout from its own
measured baseline time) -- see lopi's `LEDGER.md`, `Review-Pipeline-Phase-2` entry for
the full failure detail and both launch timestamps. **5,315 mutants found**, not the
1,500-2,000 the plan's own §0.1 estimated from the 109-mutant partial sample -- a
~3.5x undercount worth flagging for anyone sizing future full-workspace runs from that
estimate. At last check this session (2026-08-03T22:20Z, ~45 minutes of wall-clock into
the corrected run): 109 caught, 65 missed, 28 unviable, 1 timeout -- 203 of 5,315
mutants tested (3.8%). At this rate the run needs on the order of 20 hours to finish,
which is longer than a single interactive session can sustain inside this container
(background processes do not survive container reclamation) -- **whoever picks up §3
next should relaunch this on a runner that can actually stay up for it** (a dedicated
CI job, a detached process on persistent infrastructure), not assume a `nohup`'d
process in an ephemeral session container will still be running when they return.
KT-D (Phase 2's own kill-test, a 30-run paired Wilcoxon) is blocked on this run's
completion and is not attempted this sprint.

**PF-1: the mutation gate lopi actually uses is genuinely blocking, not advisory --
confirmed by reading the workflow, not assumed.** Two separate paths exist and only
one applies to lopi:
1. `.github/workflows/konjo-gate.yml` G3 (`konjo-gate.yml:370-448`) runs
   `cargo mutants --in-diff <base-diff> --timeout 60 --jobs 2`, parses the summary
   line, and calls Python's `exit(1)` when survival exceeds 10%
   (`konjo-gate.yml:433-436`) -- no `continue-on-error` anywhere in the job, checked
   line by line, not inferred from the step name.
2. `konjo_gates_py.cli`'s own dispatcher (`_tool_argv`/`gate_repo_native`,
   `cli.py:729-871`) wraps `cargo mutants --in-diff` through `newonly.net_new` and
   blocks (`FAIL` is in `_BLOCKING`, `cli.py:81`) on net-new findings -- but **lopi does
   not use this path**: `.konjo/profile.yml:104` sets
   `mutation: "none -- kept repo-native"` specifically because cargo-mutants' own
   stdout carries wall-clock timing on every line, which defeats `net_new`'s line-diff
   (confirmed against a real PR #184 failure, documented in lopi's own profile
   comment). `_gate_plan` (`cli.py:914-917`) skips any `mutation` value starting with
   `"none"`.
   Net effect: the feedback loop this sprint is building sits on top of a gate that
   **can and does reject** for lopi (path 1). Section 3's "the gate must be able to
   reject" requirement needed no fix here -- a real difference from the shape the plan
   anticipated ("if PF-1 found the existing mutation step advisory, fixing that is in
   scope"), worth recording so a future sprint doesn't assume it still needs fixing.
3. Neither per-PR path persists `--output`/`mutants.out/` today -- only `kiban bench`
   (`lib/bench.py`'s `_mutation_rust`, `bench.py:244-315`) already parses
   cargo-mutants' structured `outcomes.json`, and section 2's formatter follows that
   same schema rather than inventing a second parser.

**PF-2 (KT-2A): cargo-mutants' own report already resolves all 5 needed fields --
`konjo-ast-diff-rs` is not needed for section 2, only for section 1.** Confirmed
directly against a live `cargo mutants --output` run (cargo-mutants v27.1.0):
`outcomes.json`'s `scenario.Mutant` embeds `file`, the exact mutated `span`
(file:line:col), `replacement`, and -- the one the plan flagged as possibly needing
`konjo-ast-diff-rs`'s `collect_items` -- `function.function_name`, which is **already
qualified** for methods (`"BudgetGovernor::config"`, not bare `"config"`) and comes
with the enclosing item's own full line span (`function.span`). "Original expression"
isn't a discrete field but is trivially the pre-mutation source at that span, already
on disk. Stop rule did not fire. `konjo-ast-diff-rs`'s existing `ItemSig`
(`packages/konjo-ast-diff-rs/src/main.rs:75-119`) remains real, separate, necessary
work for section 1 specifically -- it has no line-span capture today (built for
token-stream diffing, not line-to-item mapping), so section 1 needs to extend it, not
just reuse it as-is. Not done this sprint (see deferral below).

**PF-3 (KT-2B) PASSED: mutation-guided regeneration beats plain "write more tests," on
real surviving mutants, arm B strictly dominates arm A.** The plan's own P0 partial
baseline (109 mutants) was not recoverable from disk (its `.cargo-mutants-bench/`
output was never committed, by design, and the container that ran it is gone) -- see
lopi's `LEDGER.md` for the substitution reasoning. Ten real surviving mutants were
pulled instead from a scoped `cargo mutants -p lopi-ratelimit` run (11 found, 10
used, spanning 5 distinct enclosing items across `lib.rs`/`budget.rs`: arithmetic
refill-rate bugs, a no-op function body, a getter returning a leaked default, and a
boundary comparison operator). Two arms, 15 independent fresh-context agents (5 arm A,
10 arm B, zero shared context between any two), each producing Rust test code with no
tool access beyond reading the prompt:

- **Arm A** (given the enclosing item's source only, asked to "write tests"): **7/10
  mutants killed.**
- **Arm B** (given the enclosing item plus the specific surviving mutation, told which
  existing tests still passed despite it): **9/10 mutants killed.**
- Arm B never lost a case arm A won; it won on 2 (a deficit-sign arithmetic bug and a
  boundary `>`/`>=` comparison, the latter only killable by realizing a
  *zero-usd-per-hour* governor config makes the equivalence observable -- exactly the
  kind of mutation-specific reasoning "write more tests" has no reason to attempt).
  Both arms missed the same one mutant (`Duration::from_secs_f64(deficit % rate)` vs
  `/ rate`) -- a timing-precision bug neither a generic nor a mutation-informed
  black-box unit test found tractable without controlling the tokio clock more
  carefully than either arm attempted.
- **A secondary, unplanned finding: arm A's generated tests were less reliable, not
  just less effective.** 3 of arm A's 5 tests for `TokenBucket::acquire` failed on
  *unmutated* code -- a real bug in the generated tests (conflating tokio's paused
  virtual clock with `BucketState::refill()`'s use of real `std::time::Instant`, a
  gotcha the pre-existing test suite's own comments already document for exactly this
  reason) that had nothing to do with any mutation. Those 3 were excluded and the
  remaining 2 working tests re-verified against all 4 of that item's mutants before
  counting; arm B's 10 tests all passed on unmutated code on the first attempt.
  n=1 item, not a general claim -- but consistent with the mechanism the plan
  predicted (a specific target narrows what the model has to get right).
- Not a substitute for the real KT-D (30-run paired Wilcoxon, blocked on PF-0's
  completion) -- a pre-registered pilot at the size the plan itself specified (10
  mutants), sized to decide whether to proceed to section 2 onward, not to close the
  kill-test permanently.

**Section 2 shipped and verified: `lib/mutation_feedback.py` + `tests/
test_mutation_feedback.py` (8 tests, all passing).** One `FeedbackRecord` per
surviving mutant: `file`, `line`, `function` (qualified), `original`, `replacement`,
`item_source` (the full enclosing item, read from `function.span`), `tests_still_
passing`, one-line `rationale`. Capped (`cap`, default 20), deterministically ordered
(file, then line) so repeated runs against an unchanged report produce the same
truncated set -- no silent-cap violation, callers can compare the returned length
against `load_missed_mutants`'s full count to detect truncation. **"Tests that
exercise this item" is a documented heuristic, not precise call-graph attribution** --
every `#[test]`/`#[tokio::test]` in the same file's `mod tests` block, because true
per-test coverage attribution needs per-test line coverage this sprint does not
compute. Verified against the real 11-mutant `lopi-ratelimit` scoped run (not just the
synthetic pytest fixture): all 11 records resolved to a real item, a real mutation,
and a real (if file-scoped, not item-scoped) test list.

**Deferred to next session, not silently dropped:**
1. **Section 1 (uncovered-item extraction).** Real, scoped work:
   `konjo-ast-diff-rs`'s `ItemSig`/`collect_items` need line-span capture added (they
   currently carry only `qualified_name`/token-stream text, built for before/after
   body diffing, not line-to-item mapping) before lcov/coverage.py output can be
   mapped to enclosing items the way section 1 needs. Not started this sprint --
   section 2 turned out not to need it (PF-2), so it wasn't pulled forward by
   necessity, and there wasn't session time left to do it carefully alongside
   everything else above.
2. **Section 3 (the loop + gate) and section 4 (`konjo/mutation-hunt` skill).**
   Deliberately not attempted, not a time-ran-out cut: the plan's own PF-0 instruction
   states "everything in section 3 is calibrated against it" (the full baseline) --
   building the round cap, token ceiling, and gate wiring against a baseline that is
   3.8% complete would mean calibrating against a number known to be wrong, and
   section 3's own verify step ("report rounds taken, mutants killed per round, and
   tokens spent per round" on a real end-to-end fixture run) cannot honestly be
   claimed done without a real run, which was not attempted. **No "tokens per round"
   figure exists this sprint for that reason** -- this is the reporting rule's
   headline number that has no value to report, not an omission.
   The waiver/ledger substrate section 3 needs already exists and needs no new
   plumbing: `lib/oneway.py`'s trailer mechanism (`POLARITY_WAIVED_TRAILER` at
   `oneway.py:30`, `make_trailer`/`find_trailer`), the same one `gate_polarity` (K1)
   already reuses -- a mutation-loop waiver mints a sibling trailer
   (`Konjo-Mutation-Waived`) through the same functions, not a second override
   channel.
3. `evals/fixtures/rust/` does not exist yet (only `mojo/`, `squish/`, `typescript/`
   under `evals/fixtures/`) -- section 3's verify step needs to create it, not find it.

## Review-Pipeline-Phase-1: plan-artifact schema plus the telemetry fields it feeds (kiban's half)

**Sprint P1 (`KONJO_REVIEW_PIPELINE_PLAN.md` Phase 1, the Planner/Executor split).
Primary repo is lopi; kiban's scope here is the plan-artifact schema and the
telemetry wiring it feeds. Full pre-flight (PF-1 entry-point audit, PF-2/PF-3 live
kill-tests, PF-4 prior-art check) and the Planner/Executor handoff itself are recorded
in lopi's `LEDGER.md`, `Review-Pipeline-Phase-1` entry; read that first for the
complete picture. No critic, router, or gate shipped, per the plan's Phase 3
boundary.**

**Design decision: hand-written validator, not a generic JSON Schema engine.**
`schemas/plan_artifact.schema.json` is the one schema this repo needs to validate
against today, and its constraints (`type`, `required`, `properties`, `items`,
`minItems`, `minLength`, `additionalProperties`) are a small, fixed subset. Adding the
`jsonschema` pip dependency for one schema would be premature machinery, the same
call `lopi_core::schema`'s own doc comment already makes for lopi's structured-output
validator ("a heavier external `jsonschema` crate would also pull `regex` and `url`
into the dependency graph, not worth it for the four keywords lopi actually
consumes"). `lib/plan_artifact_schema.py`'s validator reads the schema file's own
declared `required`/`minItems` at import time rather than hardcoding them a second
time, so the two cannot silently drift without `test_schema_still_declares_scope_min_
items_one` (`tests/test_plan_artifact_schema.py`) going red. If a future schema needs
real JSON Schema semantics (`oneOf`, `$ref`, conditional subschemas), revisit adding
the dependency then, not preemptively now.

**Design decision: `planner_scope`, not `scope`, on `PrTelemetryRecord`.** The record
already carries a top-level `scope: str = "org"` field meaning ledger scope (`org`
versus `repo:<name>`), predating this sprint. The plan artifact's own `scope` field
(an explicit file/glob list) is a different type and a different meaning entirely; had
this sprint reused the field name `scope`, either the dataclass would refuse the
collision outright or, worse, one of the two meanings would silently overwrite the
other depending on assignment order. Naming it `planner_scope` costs one field name
and closes the collision permanently, rather than requiring every future reader of
`pr_telemetry.jsonl` to remember which `scope` a given record's `scope` key means.
Constrains future work: any future plan-artifact-derived telemetry field that could
plausibly collide with an existing `PrTelemetryRecord` field name (there are none
currently, `predicted_tier`/`planner_model`/`planner_commit` are all new names) should
get the same `planner_`-prefixed treatment rather than assuming the record's flat
namespace is safe to reuse.

**Verified with one real end-to-end record**, not a synthetic fixture: the plan
artifact used in `test_pr_telemetry_plan_artifact.py` is the live Planner run's actual
output (built in lopi this sprint against a throwaway repo, see lopi's `LEDGER.md`),
field for field. `apply_plan_artifact()` reuses `lib.plan_artifact_schema.validate`
rather than re-validating by hand, so a telemetry record can never carry a scope value
that did not independently pass schema validation, closing the same fail-open gap
section 2.4 identifies for a future router.

## Review-Pipeline-Phase-0-1: instrumented the review-pipeline plan's telemetry, backfilled it against real history, found the plan wrong about its own tooling twice

**Sprint P0 (`KONJO_REVIEW_PIPELINE_PLAN.md` Phase 0). Non-goal discipline held: no gate,
critic, or router shipped. Everything below is measurement infrastructure plus one
work order.**

**PF-1 corrected the plan on two tooling assumptions before any code was written, both
confirmed against the real repos, not inferred:**
1. **Coverage tool is wrong.** The plan specifies tarpaulin everywhere. Neither target
   repo uses it. lopi's own CI (`konjo-gate.yml` G2) already standardized on
   `cargo llvm-cov nextest` (lcov output, real measured coverage 68.34% locked in
   `.konjo/coverage-floor.txt`); squish's is `pytest --cov` (its own `konjo-gate.yml` G2,
   `coverage-80`). `kiban bench` (`lib/bench.py`) uses each repo's own tool, not a third
   one that would disagree with the gate already enforcing it.
2. **Mutation testing is not "wire from scratch."** `cargo-mutants` is already wired —
   diff-scoped only (`--in-diff`, PR-triggered, `konjo-gate.yml` G3 and
   `konjo_gates_py.cli`'s dispatcher), survival capped at 10%, never persisted anywhere
   durable. `kiban bench`'s full-repo, un-scoped run is the genuinely new measurement;
   the diff-scoped gate stays exactly as it was.

**PF-2 (KT-0A): kledger's existing telemetry (`review_log.py`, per-review dispatch/finding
counts) overlaps zero of the Phase 0 schema's 23 fields. Stop rule did not fire —
proceeded with full scope.**

**PF-3 (KT-0B): 204 merge commits to lopi `main` in the 90-day window, far above the
20-commit floor.** lopi's entire git history (816 commits total) starts 2026-05-04 — the
repo is younger than the window itself, so this backfill is lopi's whole PR history to
date, not a rolling recent sample. Stop rule did not fire.

**PF-4: full-workspace `cargo mutants` on lopi is a multi-hour job, not a single-session
one.** Scoped trial on the smallest crate (`lopi-github`, 242 lines): 5 mutants, 64s test
time on top of a 30s baseline build. Extrapolated against the ~77k-line workspace
(~1,500-2,000 mutants order of magnitude), confirmed live: a real full-workspace run,
capped at 35 minutes, reached only 109 mutants (~5-7% of the ~1,500-2,000 estimate) before
the cap. Ran detached per the plan's own instruction rather than blocking the session;
**this baseline is genuinely incomplete and the honest number is partial, not final** —
49 caught / 53 missed / 7 unviable in the time available, 52.0% survival on what ran
(missed / (caught + missed)). A real full baseline needs a dedicated multi-hour run,
tracked in `NEXT_SESSION_PROMPT.md`. The 52% partial survival rate is itself informative
even incomplete: comparable order of magnitude to lopi's known 68.34% line-coverage floor
being well under its 80%/95% targets, i.e. a repo with real coverage gaps plausibly has
real mutation-survival gaps too, consistent rather than contradictory — but this is a
109-mutant sample, not a claim to build on without the full run.

**§1, `kiban bench` (`bin/kiban-bench`, `lib/bench.py`): built, and it found two real bugs
in itself before I'd trust its numbers.** Both found by actually running it against
squish, not by inspection:
1. A timed-out subprocess (`mutmut run`) left two ~1.8GB worker processes running after
   `subprocess.run(..., timeout=...)` returned — killing the direct child doesn't kill
   its own children. Fixed: `_run` now launches in its own process group
   (`start_new_session=True`) and kills the whole group on timeout
   (`os.killpg`/`SIGKILL`), confirmed live (a synthetic `sleep 30 & sleep 30 & wait`
   under a 2s timeout leaves zero orphans after the fix, versus real orphaned mutmut
   workers before it).
2. squish's `pytest-cov` has `fail_under=100` configured, which makes pytest-cov call
   `pytest.exit()` on a coverage-threshold miss — this **skips pytest's normal
   `"N passed"` terminal summary line entirely**, confirmed live (squish's real bench run
   produced zero such line while the suite plainly ran, 209s of real test time). Test
   count now comes from counting `-q` progress-line outcome characters
   (`.`/`F`/`E`/`s`/`x`/`X`) instead, cross-checked against `pytest --collect-only`'s
   per-file counts (6,387 counted vs. 6,413 collected, <0.5% off — attributable to
   deselection/collection-vs-run differences, not a parsing bug). Also fixed: the
   coverage regex assumed a fixed column count before the `%`; squish's `TOTAL` row has
   branch-coverage columns the line-coverage-only regex didn't anticipate. Now prefers
   pytest-cov's precise `"Total coverage: XX.XX%"` line when present, falling back to the
   `TOTAL` row's rounded percentage.
3. A third: when `mutmut run` fails outright (not a timeout, not "tool missing"), the
   first version of this code still reported `mutation_caught`/`mutation_missed` as `0`/
   `0` — indistinguishable from "ran cleanly, killed nothing," when the truth is "did not
   run at all." Fixed to leave both `None` on a hard failure and record the real reason
   in `mutation_notes`. Found by reading squish's own real (post-fix-1/fix-2) artifact and
   noticing a `0%`-shaped score next to zero test time made no sense for a 6,387-test repo.
4. (Design fix alongside, not a bug: the original two-pass Python path ran the full test
   suite twice — once plain, once with `--cov`. Consolidated to one pytest invocation
   that produces both numbers, roughly halving squish's bench wall-clock: 92s → 86s once
   warm, versus 209s across the original two passes.)

**Verify, run against squish end to end**: real recorded artifact at
`bench_results/squish/2026-08-03-a2469def1fc6.json`; test suite ran for real
(85.54s, 6,387 outcomes counted from progress characters — cross-checked at 6,413 via
`pytest --collect-only`, <0.5% off — 1 real test failure, a missing Rust extension
`squish_quant_rs` not built in this environment, unrelated to kiban-bench, reflected via
`tests_ok: false`), coverage 87.35% (pytest-cov, precise `"Total coverage"` line, not the
rounded `TOTAL` row). **Mutation on squish did not complete**: `mutmut`'s own baseline
collection failed with `AttributeError: module 'squish.cli' has no attribute
'build_parser'`, even though `from squish import cli; cli.build_parser` resolves fine in
a plain interpreter — consistent with mutmut's isolated source-copy diverging from the
editable install's resolved path, not a real code defect in squish and not a
`kiban-bench` bug. Recorded as `mutation_notes`/`errors` on the artifact
(`mutation_caught`/`mutation_missed` both `null`, not `0`, per bug 3 above), not faked as
a score. **Determinism (the plan's explicit ask, "confirm re-running on the same SHA
produces the same mutation score") could not be checked for squish** because no mutation
score was ever produced to compare — recorded as not-verified, not smoothed into "n/a."

**§2, per-PR telemetry schema (`ledger/pr_telemetry.py`, `ledger/schema.md`): a third
sibling stream on the jsonl_store substrate, not a Decision Ledger event** — a bench/PR
measurement is not a durable call, so it doesn't go through `Ledger.decide()`. All 23
Phase-0 fields defined now (11 git-derivable, 12 live-capture-only including the
critic fields, null until Phase 3, per the plan's explicit instruction not to let the
schema churn later). Verified: 3 synthetic records written and read back correctly; 50
concurrent writes from 10 threads produced 50 distinct records with zero loss or
corruption (append-only holds under concurrency).

**§3, retroactive backfill (`bin/kiban-backfill`, `lib/backfill.py`,
`packages/konjo-ast-diff-rs`): all 204 merge commits backfilled, zero unparseable
`.rs` files.** The plan's explicit instruction — "use syn for the AST delta and for
locating unsafe, .unwrap(), and attribute additions... grep is acceptable only for
`continue-on-error` in workflow YAML" — is followed literally: `konjo-ast-diff-rs` is a
new, separate `syn`-based Rust binary (not a repurposing of the phase-1
`konjo-gates-rs` CI-gate-runner stub, which is reserved for different future work),
invoked once per touched `.rs` file per commit. It classifies every function/method by
qualified name into identical/body-changed/signature-changed, and detects net-new
`unsafe`, `.unwrap()`/`.expect()`, `#[allow(...)]`, `#[ignore]`, removed
`assert!`/`assert_eq!`/etc., removed test functions, and a syn-matched (not regex-guessed)
subset of trigger-surface call paths (subprocess, deserialization, network egress, sql,
ffi, concurrency, crypto — **not** `auth`/`path_construction`, explicitly not covered:
no syn-safe call-path signature exists for either without an unacceptable false-positive
rate, recorded as a known gap, not silently claimed). One real bug found and fixed during
this build: `assert!(true);` in statement position parses as `Stmt::Macro`, not
`Expr::Macro` — a visitor overriding only `visit_expr` silently missed every
statement-form assert; fixed by overriding `visit_macro` instead (catches both forms),
confirmed by a regression test that failed before the fix and passes after.

**Hand-check, 5 commits drawn with a fixed random seed (42) for reproducibility:**
`lines_added`/`lines_removed`/`files_touched` matched `git diff --numstat` exactly on all
5 (2342/571/30, 76/24/5, 4910/93/55, 2130/303/57, 10476/1833/144). AST-derived
trigger-surface counts spot-checked against the real diffs matched exactly on both
checked (a `concurrency:2` claim on one commit matched 2 real `Mutex::new`/`tokio::spawn`
additions; a `sql:6` claim on another matched 6 real `sqlx::query_as` additions). One
field on the largest sampled commit (144 files, a real reorganization) showed a
divergence worth stating plainly: `removed_test_fn` recorded 42, a naive line-diff grep
for removed `#[test]`/`#[tokio::test]` attribute lines found 45. Traced to git's
line-based diff algorithm counting a test function that moved within the file (unchanged
content, different position) as both a deletion and an addition — the `syn`-based
whole-file count correctly does not count that as "removed" (nothing about the function
actually changed), the line-diff grep does. **Disagreement count: 0 of 5 records wrong;
1 of 5 showed one field where two legitimately different measurement methods disagree,
and the syn-based one is the more defensible answer, not a detector bug** — stated
plainly rather than folded into "4/5 clean."

**§4, cost circuit breaker: shipped as a work order, not a speculative patch, exactly as
instructed.** PF-1 found lopi already has real token/cost accounting the plan didn't know
about — `TurnMetrics` persisted to SQLite, a per-session USD hard ceiling
(`EconomicsConfig::hard_session_ceiling`, reactive, polled every 10s), a mid-stream kill
at 95% of a CLI session's budget, and a second, parallel, **explicitly unwired** budget
system (`lopi_ratelimit::BudgetGovernor` — `lopi-orchestrator/src/budget/mod.rs` states
outright it is dead code, never call it from here). No per-day ceiling existed in any
form, enforced or estimate-only, and neither existing mechanism is a pre-call gate — both
fire reactively, after tokens are already spent. Shipped for real this sprint: the pure
`CostCircuitBreaker::check` decision logic and `EconomicsConfig`'s two new
`Option<u64>` ceiling fields (`crates/lopi-core/src/cost_breaker.rs`,
`crates/lopi-core/src/economics_config.rs`), 6 passing unit tests with stubbed counters,
`cargo build`/`cargo test -p lopi-core` both green. **Not shipped**: wiring the check into
`claude_spawn.rs:130`/`:255` and `api_client.rs:196`/`:240` — `ClaudeCode` is a pure
CLI-argument builder today with no config/DB handle at all, so live wiring is a
cross-cutting change to its construction chain across `lopi-agent`, not a same-file patch.
Precise integration points, the recommended error-propagation shape (reusing the
`ERR_BUDGET_HARD_STOP`/`terminal_errors.rs` terminal-classification precedent, confirmed
by reading that file, not guessed), and why `BudgetGovernor` must stay untouched: all in
`lopi/docs/work-orders/cost-circuit-breaker.md`.

**Where the plan was wrong, restated plainly (not buried above):** tarpaulin (both
repos use something else), "wire cargo-mutants from scratch" (already wired,
diff-scoped), and "build a circuit breaker" framed as if nothing existed (lopi already
had three overlapping-but-incomplete mechanisms; the gap was specifically a pre-call
token gate with a daily scope, not the whole concept).

## Task-to-Diff-Loop-1: `lib/gen_runner.py` + `evals/gen_cassettes.py` + `konjo-eval genrun` exist -- the missing measurement instrument KT-13.1 named, built and run for real

**One-way door: the harness Phase 2's six candidate invariants (and every future
authoring-context claim) now measures against.** `.konjo/killtests/P13/KT-13.1.md`
found `konjo-headless`/`lib/headless.py` a thin `claude -p` argv builder with no
"task in, diff out" loop -- Phase 14, Phase 1 builds that loop as a *consumer* of
`lib.headless`, not a replacement (`LiveGenerationBackend.generate` still calls
`headless.headless_argv` for the `--verbose`-with-stream-json correctness; see
`lib/gen_runner.py`'s module docstring for the full boundary). Sibling to
`bin/konjo-headless`, not a superseding rewrite of it, per the sprint's own
instruction to say so in the docstring.

**Two real environment findings shaped the backend's defaults, not guesses:**
1. `--dangerously-skip-permissions` is refused by the installed CLI under root
   ("cannot be used with root/sudo privileges for security reasons") -- this
   container runs as root, so the standard headless-automation permission bypass is
   unavailable here. `LiveGenerationBackend` instead uses `--permission-mode
   acceptEdits` with an explicit tool allowlist (`Read,Write,Edit,Bash,Grep,Glob` --
   no `WebFetch`/`WebSearch`; see `DEFAULT_TOOLS`), confirmed working end-to-end
   against a real scratch repo before spending any budget on lopi.
2. `--bare` mode's auth is "strictly `ANTHROPIC_API_KEY`... OAuth and keychain are
   never read" (per `claude --help`) -- this remote session has no API key, only a
   host-managed provider token, so a `--bare` call fails closed with an
   authentication error while the identical prompt without `--bare` succeeds
   (confirmed directly, not inferred). `LiveGenerationBackend` defaults to
   `bare=False`; both defaults are overridable via constructor args for a caller
   running as a non-root CI user with its own key, where `--bare` +
   `--dangerously-skip-permissions` is the faster, correct combination.

**Cassette family is a new, distinct pattern from `evals/cassettes.py`, not a
generalization of it** -- `evals/gen_cassettes.py`'s module docstring states why:
different backend shapes (`dispatch(specialist, prompt)` vs `generate(task,
context)`), different result shapes (a reply string vs a `GenerationResult`
dataclass). Reusing the *pattern* (hash the inputs, record once, hard-miss on
replay) was the right level of reuse; forcing one generic module over both would
have needed an awkward lowest-common-denominator interface neither caller has.

**KT-14.2, found and fixed before any measurement ran**: tracing a known-
unclassified taxonomy class through every layer of `konjo-eval gen`'s reporting path
found `run_gen_corpus`'s `totals` dict initialized every class to `0` and only
incremented the classified ones -- an unclassified class's total stayed `0` forever,
indistinguishable from "checked, clean." Fixed to initialize `None` (matching
`ClassificationResult`) and only become an int once a fixture actually classifies it.
Full writeup: `.konjo/killtests/P14/KT-14.2.md`. This shipped in the harness Phase 13
built (`evals/genfixtures.py::run_gen_corpus`) undetected since 1.8.0 -- caught here
because this kill-test asked the procedure to trace the value through aggregation
specifically, not just the single-diff classifier Phase 13 already verified.

**KT-14.1, run for real, PASS**: 3 tasks drawn from real closed lopi work (git log,
not invented), 3 runs each, identical baseline context. 8 of 9 live sessions produced
a diff; every task with 2+ successful runs produced byte-identical per-class defect
counts across its repeats (21/21 mechanically-classified cells agree). The one real
non-reproducibility this run found was generation-layer (a session that exited 0 but
wrote no diff), not classifier-layer -- named as a distinct failure mode, not folded
into the agreement number. Full writeup and the real task table (commit shas, parent
refs, which defect class each targets): `.konjo/killtests/P14/KT-14.1.md`.

## Phase-3-Real-Measurement-1: a real, small slice of Phase 3 ran -- both tested candidates measured null, and the measurement itself caught a live classifier bug worth its own record

**Honest-null outcome, per the sprint's own explicit permission to publish one.**
2 tasks (real closed lopi work, feature-shaped, not defect-fix-shaped -- deliberately
distinct from KT-14.1's three tasks, to avoid confounding "does context reduce
*incidental* defects" with "did the agent follow an explicit fix instruction"), 3
conditions (baseline, candidate 3 "queue bounded/timeout/retry-capped," candidate 5
"typed errors at a library boundary"), 3 runs each -- 18 real sessions. Full writeup,
task table, and the methodological lesson about baseline incidence:
`.konjo/killtests/P14/phase3-report.md`.

**A real classifier bug, found by the measurement itself, not by inspection**: the
first pass showed `unbounded_queue`/`untyped_error_boundary` hits that looked like a
signal. Tracing them before writing the report found `lib.threat.classify`'s diff
hints and `lib.defect_shapes`'s new scans were reading Rust test-helper code (a
`mod tests { ... }` block's fixtures: `oneshot::channel()`, `.unwrap()` in test setup)
as production code -- exactly the shape the org's own real convention ("No
unwrap()/expect() outside tests") explicitly permits. Two fixes, both narrow and
confirmed against the real data, not designed in the abstract:

1. **`lib/defect_shapes.py::added_lines_excluding_test_scope`** (new) -- drops added
   lines once a `mod tests { ... }` / `#[cfg(test)]` marker is seen, checking two
   signals: an added line opening the marker itself, and (the one that actually
   caught the live case) a unified diff's hunk header naming the enclosing scope
   (`@@ -357,4 +429,6 @@ mod tests {` -- the marker line itself predates the diff and
   never appears in the diff body at all). `genfixtures.classify_diff` now scans this
   stripped text for `missing_timeout`/`untyped_error_boundary`, and passes it as
   `lib.threat.classify`'s `diff_text` argument for this harness's reuse of
   `unbounded_queue`/`untrusted_input_reaching_exec` specifically --
   **`lib.threat.classify` itself is unchanged**, so `gate_threat_model`'s real
   trust-boundary hinting still scans the full diff (a reviewer plausibly still cares
   that a PR's test code touches a webhook/subprocess boundary; a defect *count*
   comparing authoring contexts does not want test scaffolding inflating it).
2. **`lib/threat.py`'s `SUBPROCESS_EXEC` diff hint**, narrowed from a bare `spawn\(`
   (which also matched `tokio::spawn(fut)`/`thread::spawn(closure)` -- in-process
   concurrency, no subprocess/OS-exec boundary at all) to `\.spawn\(\)` (the zero-arg
   method call matching a process builder's terminal call,
   `Command::new("x").spawn()`). This is a real, if narrow, behavior change to
   `gate_threat_model`'s own hinting too, not just this harness's reuse of it --
   recorded here since it is a genuine correction, not purely additive.

**Both KT-14.1's and Phase 3's own numbers were re-classified with the fix before
either report was finalized** -- see `.konjo/killtests/P14/KT-14.1.md`'s own note on
this. After the fix, every one of the 20 successful Phase 3 sessions classified
completely clean on all seven mechanically-classified defect shapes, in every
condition.

**Decision: no candidate ships this sprint.** Not because either tested candidate
failed a measured bar -- because the baseline rate for both candidates' target
classes was already zero on both tasks, so there was no incidence for either
candidate to be measured against. Phase 3's own instruction ("keep only candidates
whose measured reduction clears the run-to-run variance") requires a measured
reduction to exist before it can clear anything. Candidates 1, 2, 4, 6 remain
entirely unmeasured (candidate 1 by the brief's own stated low priority; 2/4/6 simply
not reached inside this session's live-model budget on top of everything else this
sprint required). All six stay recorded in this file's own Phase 13 history as
drafted, not shipped -- Phase 3 changed the evidence available about two of them from
"none" to "a real null at small scale," not to "measured and kept."

## Defect-Classifier-Gap-1: 4 of 8 taxonomy classes classified mechanically -- from 3 to 7 of 8, `raw_index_external_input` recorded as genuinely not classifiable this way

**Grew `evals/genfixtures.py`'s mechanical coverage without writing a fully new
detector for most of it**, per Phase 2's own "reuse before you build" instruction.
Per-class decision, all recorded in `evals/genfixtures.py`'s `MECHANICALLY_CLASSIFIED`
comment as the single source of truth (this entry summarizes, does not duplicate):

- **`unbounded_queue`** -- mechanical, **zero new detector code**: reuses
  `lib.threat.classify`'s existing `RESOURCE_LIMITS` reason. Wiring it up surfaced (and
  this sprint fixed) two real bugs in that regex, found while making a hand-authored
  fixture (`04_unbounded_channel`, modeled on lopi's real two-production-unbounded-
  channel finding, PR #184) actually fire: the pattern's `$` anchor had no
  `re.MULTILINE` flag, so it only ever matched on a diff's *last* line regardless of
  where the risky call actually was (silently near-inert on any multi-line diff since
  the boundary shipped in Phase 13); and it had no case for `unbounded_channel()` /
  `unbounded()` (tokio's and crossbeam's *explicitly named* unbounded constructors --
  the shape whose name says what it is), only bare `channel()`. Both fixed
  (`lib/threat.py`), confirmed against the real fixture, `tests/test_threat.py` still
  green.
- **`missing_timeout`**, **`untyped_error_boundary`**, **`missing_test_failure_path`**
  -- mechanical, new hint-shaped scans in the new `lib/defect_shapes.py`, same
  diff-line-hint discipline `lib.threat`/`lib.polarity` already accept for this
  harness (a call-site/catch-shape/new-test-without-a-failure-case regex, not a full
  parse -- documented as a carried limit in the module docstring, not hidden).
- **`raw_index_external_input`** -- **genuinely not classifiable this sprint**, left
  `None`. Needs dataflow/taint tracking ("is this index expression reachable from
  external input") a line-diff regex scan cannot answer without a false-positive rate
  high enough to corrupt the defect *count* Phase 3 measures (unlike a threat-model
  hint feeding a human review step, where over-triggering is cheap -- see
  `lib.threat`'s own module docstring for that contrast). An LLM-classified pass with
  a measured inter-rater agreement rate was considered (Phase 2's own third option)
  and explicitly not attempted this sprint: with only this one class left unclassified
  and Phase 1/Phase 3's live-model budget already the sprint's biggest cost, spending
  more live-model budget on a classifier study for a single class judged the weaker
  use of this session's time than actually running Phase 3 on the 7 classes already
  covered. Carried to `NEXT_SESSION_PROMPT.md`, not silently dropped.
- **Seed corpus grew from 3 to 7 fixtures** (`evals/gen_fixtures/04`-`07`), each
  hand-authored and modeled on a real, cited defect (three from `konjoai/lopi`'s real
  history: the two-unbounded-channel fix in PR #184, the `security-invariants.md`
  timeout line, the `lopi-memory` untyped-error gap PR #184 itself named as unstarted;
  one generic, matching `03`'s existing precedent), each confirmed by a dedicated test
  (`tests/test_genfixtures.py::test_new_fixtures_fire_their_target_class`) to actually
  fire the classifier it's named for -- a fixture that silently classified to zero
  would have been worse than no fixture at all.

## Claude-Contract-Ramp-1: `gate_claude_contract` flips to blocking for lopi (0 standing violations) -- stays advisory for squish and vectro, with the real count and the reason recorded, not guessed

**Default change, made per-repo on measured evidence, not a blanket flip.** Phase 4
measured `lib.claude_contract.check_contract` against all three real pilot repos'
actual current `CLAUDE.md` (not a diff -- the whole file, the same standing-violation
question Phase 0's original hand audit asked for lopi in Phase 13):

| Repo | Standing violations | Decision |
|---|---|---|
| lopi | **0** -- Sprint S13R (PR #184, merged this session's own start time) already converted it to the full section contract, every invariant naming its enforcer | `profiles/lopi.yml`: `claude_contract.advisory: false` |
| squish | 4 of 6 required sections missing (org rules, invariants, repo map, repo-specific rules), no org import | stays `advisory: true`, explicit and reasoned, not the silent code default |
| vectro | Same shape as squish -- 4 of 6 sections missing, no org import | stays `advisory: true`, explicit and reasoned |

Every rules-file `citation_ratio` check (the gate's other half) was already clean
across all three repos with no override needed (highest measured: lopi's
`security-sinks.md` at 0.25, well under the 0.5 majority-incident-log threshold).

**The org-wide code default (`cfg.get("advisory", True)` in
`packages/konjo-gates-py`) stays `True`, recorded explicitly rather than silently
carried**: 2 of 3 real pilot profiles are not ready, and flipping the code-level
default would silently promote every future onboarding repo (and squish/vectro right
now) to blocking before their CLAUDE.md is in contract -- the exact "fail the very
next unrelated PR that touches CLAUDE.md" trap this gate's advisory-ramp existed to
avoid. Each ready repo instead gets an explicit per-profile override
(`profiles/lopi.yml`), the same shape `gate_polarity`'s own advisory ramp uses.

**Proposed conversions for squish and vectro written this sprint**
(`docs/pilots/squish-claude-md.proposed.md`, `docs/pilots/vectro-claude-md.proposed.md`),
matching `docs/pilots/lopi-claude-md.proposed.md`'s Phase 13 precedent exactly (this
session holds read-only access to both repos; applying either is that repo's own PR).
Both proposals verified for real against `lib.claude_contract.check_contract` before
being recorded here (`check.ok == True` on the proposed file content, not just
asserted) -- a real, if smaller-scale, repeat of Phase 13's own finding that most
"Critical Constraints" lists have no mechanical enforcement behind them:

| Repo | Constraints with real mechanical enforcement found this sprint | How found |
|---|---|---|
| squish | 2 of 9 (bare/`Exception`-except and quantization-accuracy) | read `.konjo/hooks/pre-commit` and `.github/workflows/model_pipeline.yml` in full |
| vectro | 1 of 14 (`unwrap`/`expect`, via clippy) | read `.konjo/hooks/pre-commit` and `.github/workflows/konjo-gate.yml` in full |

Every other bullet in both files is marked `ADVISORY` in the proposal rather than
guessed at -- a bounded, real search (not exhaustive per-line CI archaeology at
Phase 13's original depth) that found no matching check, stated as absence-of-evidence
rather than presented as proof-of-absence. See `Squish-Vectro-Gate-Reconciliation-1`
below for the CI-shape finding these proposals surfaced in passing (`continue-on-
error: true` swallowing nearly every check in both repos' own Wall 2 CI).

## Squish-Vectro-Gate-Reconciliation-1: promote/keep/delete tables for both repos, plus a real finding neither this session's brief nor either repo's own CLAUDE.md named -- most of both repos' "Wall 2" CI is decorative

**Non-goal-respecting decision, same shape as `Lopi-Gate-Reconciliation-1`**: this
phase connects and records what exists, it does not rebuild either repo's CI. Read
both repos' real `.github/workflows/konjo-gate.yml` in full (squish: 210 lines;
vectro: 138 lines), not assumed from `profiles/*.yml`'s existing (accurate, from an
earlier sprint) `format_lint`/`contract_gates` declarations.

**The real finding, not named anywhere before this session traced it**: squish's G1
(static analysis) and G2 (coverage) jobs, and vectro's G1/G2/G3/G4 jobs, wrap
*every* check step in `continue-on-error: true`. A step under `continue-on-error:
true` can exit nonzero and the *job* still reports `success` -- and the final
`konjo-gate` job's merge decision reads `needs.<job>.result`, the *job's* conclusion,
not any individual step's outcome. Net effect, confirmed by reading the exact YAML,
not inferred from the job names: **squish's entire Wall 2 CI blocks a merge on
exactly one condition** (new-file 500-line size, the one step without `continue-on-
error`) **despite squish's own CLAUDE.md describing it as "Coverage ≥ 80% · mutation
survival ≤ 10% · complexity ≤ 15 · file ≤ 500L · zero DRY violations... Blocks the
merge."** Four of those five clauses do not block anything today. **Vectro's Wall 2
CI blocks on literally nothing** -- every step in every job, including its own
file-size check, carries `continue-on-error: true`; the `konjo-gate` job's
`[ "$FAILED" ... ] && exit 1` line can never fire. This is the same defect class
`konjoai/lopi`'s own PR #182/#184 (Sprint S13, Phase 0) found for lopi's CLAUDE.md
self-claims -- found here independently, for two more repos, by the same mechanical
question ("does this claimed gate actually have a consumer") applied to YAML instead
of prose.

**Where vectro's real blocking enforcement actually comes from**: a *second*,
separate workflow file, `.github/workflows/konjo-gates.yml` (following
`templates/repo-ci.yml`'s pattern -- the real kiban `konjo-gates` dispatcher, no
`continue-on-error` wrapping, a genuine nonzero exit blocks the merge). Squish has no
equivalent file at all -- **squish has never connected kiban's own gate orchestrator
to its CI**, the same gap lopi had before Sprint S13R's Phase A this same week.

**A second, live instance of the exact stale-pin problem this sprint's own Phase 5
item named** (misfiled in the sprint brief as `templates/repo-CLAUDE.md`, which was
already clean -- the real offender was its sibling, `templates/repo-ci.yml`):
vectro's real `konjo-gates.yml` pins `KIBAN_REF: "v1.1.5"`, seven-plus minor releases
behind current (`1.8.0` at sprint start). Vectro's only genuinely-blocking kiban
gate has been running a version of kiban that predates `gate_polarity`,
`gate_can_fail`, the doc-integrity gate, Wall-3 multi-run, and all of Phase 13 --
every quality mechanism this project has shipped in roughly its last dozen sprints.
`templates/repo-ci.yml`'s own example pin was itself stale (`v1.1.0`, matching the
pattern that let vectro's copy drift too) -- bumped to `1.9.0` this sprint, with this
finding cited inline so a future reader sees the live consequence, not just an
abstract "don't do this."

**Table (this sprint's new findings; every `format_lint`/`contract_gates` entry
already reconciled by an earlier sprint stays as-is, not re-litigated)**:

| Finding | Repo | Decision |
|---|---|---|
| G1/G2 (`static`, `coverage`) fully `continue-on-error` -- 4 of 5 CLAUDE.md-claimed Wall 2 gates do not block | squish | KEEP REPO-NATIVE as documentation of *intent*; recorded here as a correction, not silently left implying it blocks. Fixing squish's own YAML is squish's sprint, out of scope for "connect what exists." |
| No `konjo-gates` job exists in CI at all | squish | **Flagged for next squish sprint**: add a job following `templates/repo-ci.yml`, the same connection lopi's Sprint S13R Phase A just did -- `profiles/squish.yml`'s `format_lint`/`contract_gates` are real and ready, they are simply never invoked by anything in squish's own repo today. |
| Every G1-G4 step `continue-on-error` -- Wall 2 CI blocks on nothing | vectro | KEEP REPO-NATIVE as documentation of intent, same reasoning as squish; vectro's real enforcement is entirely the separate `konjo-gates.yml`. |
| `konjo-gates.yml` pinned at `v1.1.5`, ~7 minor releases stale | vectro | **Flagged for next vectro sprint**: bump `KIBAN_REF` to current and re-run the reconciled `profiles/vectro.yml` against real vectro CI, the same way `Lopi-Gate-Reconciliation-1`'s closing step verified `konjo-gates` against a real lopi checkout. This session's read-only access cannot push the bump itself. |
| `cargo-audit` | vectro | **PROMOTED** (`profiles/vectro.yml`): moved from `contract_gates` (documentation-only) to `format_lint` (real dispatch) -- the generic `_TOOL_SCOPE`/`_TOOL_BIN` support already existed (added for lopi, Phase 13), so this is a one-line reclassification, zero new detector code, the same PROMOTE shape `Lopi-Gate-Reconciliation-1` used. |
| `templates/repo-ci.yml`'s example `KIBAN_REF` | kiban itself | Bumped `v1.1.0` → `1.9.0`, with this session's real vectro finding cited inline as the concrete cost of leaving a template example stale. |

**Nothing was deleted, nothing was rewritten to actually block** -- per this phase's
own non-goal ("connecting what exists, not improving any gate"), squish's and
vectro's `continue-on-error` wrapping is not this sprint's to remove; that is a real
gate-hardening decision each repo's own maintainers should make deliberately (some
`continue-on-error` uses are legitimate soft-launch choices, not all decoration is a
mistake), not something to flip silently from a reconciliation pass in a different
repo's sprint.

## Learn-Loop-Seed-1: lopi's four sprint-cited security lines converted through `konjo-learn`, all four found a home -- confirmed by running the guardrail for real, not by inspection

**Not a one-way door, but the sprint's most direct confirmation that this sprint's new
mechanisms actually connect to something.** Phase 13, Phase 5 grepped `konjoai/lopi`'s
full `.claude/rules/` (`security.md`, `testing.md`, `benchmarking.md`,
`rust-conventions.md`, `git-workflow.md`) for `Sprint S\d+` citations. Only
`security.md` carries any (confirmed: `grep -n "Sprint S[0-9]" .claude/rules/*.md`
returns four hits, all in `security.md` -- the other four rule files have none). All four
were run through `konjo-learn add --scope repo:lopi` for real this session (not
simulated): the WhatsApp/Twilio HMAC fix (Sprint S10, Phase 4), the repo-supplied-command
source-trust check (Sprint S10, Phase 0), the subprocess environment allowlist (Sprint
S10, Phase 1), and the MCP server allowlist (Sprint S10, Phase 5). Ids:
`9f79216b9cb9`, `29a000027a3c`, `5de29bb5f874`, `2751494f08a5`.

**Every one of the four found a real, already-shipped enforcement target this same
sprint built** -- none resolved to "no home" (Phase 5's own instruction: log a gap as a
gap if one is found; none was). Three of the four are the same shape,
`subprocess_exec` (a repo-supplied command, a spawned CLI subprocess, a spawned MCP
server are all, mechanically, a process spawn); the fourth is `network_ingress` (the
webhook). All four now point at `lib/threat.py`'s taxonomy + `gate_threat_model` +
`security_globs` (`profiles/lopi.yml`) + `craft`'s new pre-implementation contract
(`Threat-Seam-1`, this file) as their enforcement target -- the exact "an invariant, a
lane, a lint word, or a gate" `konjo-learn`'s guardrail (`lib/learnings.py`,
`MissingEnforcement`) requires, and would have refused to log without.

**Honest caveat, not silently glossed over**: `LearningsLog`'s default path
(`ledger/learnings.jsonl`) resolves through `jsonl_store._resolve` under
`~/.konjo/state` (an env-overridable *local machine* state dir per that module's own
docstring: "the Ledger lives in ~/.konjo/state, never in the repo"), not into this
kiban checkout. The four entries above are real and queryable
(`konjo-learn search --scope repo:lopi`) for the remainder of this session's environment,
but they do not travel with this git commit the way `LEDGER.md` does -- a future session
on a fresh container starts with an empty learnings log unless that state directory
itself persists across sessions on the same machine. This entry is the durable record;
the four ids above are reproducible by re-running the four `konjo-learn add` invocations
if a fresh environment's log needs seeding again.

**Deferred, per Phase 5's own conditional wording** ("Do the same for the S13 Phase 0
findings once that sprint reports"): S13 has not reported as of this sprint. Nothing to
convert yet; not silently skipped, the precondition simply hasn't happened.

## Gen-Fixtures-1: `evals/gen_fixtures/` and `konjo-eval gen` exist -- a new fixture shape and a new CI job, both report-only by design

**New surface, not a one-way door in the same sense as a trailer label, but recorded
because it changes what "the eval corpus" means going forward.** Phase 13, Phase 4 added
`evals/genfixtures.py` (fixture discovery, `classify_diff` against the eight-class
`DEFECT_TAXONOMY` from `.konjo/killtests/P13/KT-13.1.md`, `run_gen_corpus`) and
`konjo-eval gen`, a new sibling to `konjo-eval run`/`record`. Distinct fixture shape from
`evals/fixtures/*/{diff.patch,expect.json}`: a review fixture's `diff.patch` is the input
to a detector under test; a generation fixture's `candidate.diff` is the *output* of an
authoring context under test, and there is no single pass/fail expectation, only
per-class counts.

`classify_diff` reuses three existing detectors verbatim (`lib.redact.scan_diff` for
`secret_in_source`, `lib.polarity.lint_text` for `unconfigured_permit_branch`,
`lib.threat.classify` for `untrusted_input_reaching_exec`) rather than building a sixth
pattern library; the other five taxonomy classes report `None` (unclassified), never
silently defaulted to zero, since a zero for a class nothing checks would misreport an
unmeasured absence as a clean result -- the same false-precision KT-13.1 refuses.

**Seed corpus is illustrative, not empirical**: three hand-authored fixtures modeled on
real `lopi` `.claude/rules/security.md` defect classes (Sprint S10's webhook-HMAC,
env-allowlist, and a generic hardcoded-token line), explicitly NOT produced by a live
`konjo-headless` run. `.konjo/killtests/P13/KT-13.P4.md` records this distinction so a
future reader doesn't mistake "the harness works" for "Phase 2 has evidence" -- it does
not; see `.konjo/killtests/P13/KT-13.1.md`.

**CI placement corrected during this sprint, not shipped wrong**: the report-only job was
first drafted into `templates/repo-ci.yml` (what a *consuming* repo runs per-PR), then
moved to kiban's own `.github/workflows/ci.yml` once it was clear the fixture corpus is
kiban's own generation-quality tracking, unrelated to any single consuming repo's diff --
`konjo-eval` is not even a registered `project.scripts` entry point (only `konjo-gates`
is), so `templates/repo-ci.yml` calling it would have been dead on arrival for any repo
that actually adopted the template. Caught and fixed in-session, not left for a later
sprint to find.

## Threat-Seam-1: `konjo-threat`/`gate_threat_model` join the substrate as a third record-and-check pair -- `security_globs` is a new, permanent profile field

**One-way door: a fourth trailer label, and a new schema field every future profile can
declare.** Phase 13, Phase 3 built `konjo-threat` (`bin/konjo-threat`, `lib/threat.py`) as
a sibling of `konjo-oneway`/`konjo-prove`: brief-time classification against a fixed
eight-class trust-boundary taxonomy (authn/authz, secret lifecycle, deserialization,
subprocess/exec, path handling, network ingress, SQL construction, resource limits),
a session-side record step that refuses an empty mitigation, an empty abuse case, or a
boundary name outside the taxonomy (`threat.MissingContent`, the same
no-content-no-credit discipline `lib/learnings.py` already applies to a different claim
class), and `Konjo-Threat-Model: <fingerprint>` -- the third label built on
`oneway.make_trailer`/`find_trailer` (joining `Konjo-Acknowledged-Oneway`,
`Konjo-Prove-Merge`, and `Konjo-Doc-Verified`; `Konjo-Polarity-Waived` is the fifth
overall). `gate_threat_model` (CI) never re-classifies -- it only checks a diff matching
`security_globs` for the recorded trailer, same as `gate_one_way_door`/`gate_prove`.

**`security_globs` is new in `profiles/_schema.yml`**, a glob-list field mirroring
`longrun_globs`. Routing reuses a newly-extracted `_glob_match` helper
(`packages/konjo-gates-py/.../cli.py`) generalized out of what was `_is_longrun_path` --
the `**`-handling fnmatch logic now exists in one place instead of being duplicated a
third time for this gate, per this sprint's own research finding that `longrun_globs` and
`prove.perf_globs` had each grown a slightly different glob-matching implementation.
`profiles/lopi.yml` is the first real profile to declare it, lifted verbatim from the
`paths:` front matter already prototyped in lopi's own `.claude/rules/security.md` (one
declaration now serves both surfaces).

Ships as a real blocking gate, not advisory -- `security_globs` is opt-in per profile
(SKIP by default for a repo that hasn't matched the default glob set), so there is no
existing-repo baseline to ramp against the way `gate_polarity`/`gate_claude_contract`
need to. See `.konjo/killtests/P13/KT-13.P3.md` for the fixture pair and the reasoning in
full, including the carried limit (content is checked for shape -- non-empty, taxonomy-
valid -- not for being the *right* mitigation, the same boundary `gate_can_fail` already
draws for `rejects_test` commands).

**Also new**: `templates/sprint-brief.md` -- Phase 13's own brief (and K1's before it)
follows a sprint-brief shape that had no file defining it on disk, the same gap
`KONJO_FORWARD.md` had before `KONJO-Forward-Origination-1` closed it. Originated here,
carrying the `TRUST BOUNDARIES`/`ABUSE CASES` per-phase fields Phase 13's own brief asked
for, with `none` recorded as the honest answer for phases that touch no boundary rather
than the fields being silently omitted. The `craft` skill (opt-in, does not count against
the always-on context budget) gained a "Pre-implementation contract" section: name the
boundary, state the mitigation, name the abuse case, name the test -- before the code,
not after -- with `konjo-threat classify`/`record` as the mechanism that turns the stated
intent into a checked commit trailer.

## CLAUDE-Contract-1: `gate_claude_contract` ships advisory -- the section-order/enforcement-naming contract is now checkable, not just auditable by hand

**Default change, adoption-ramp shaped like `gate_polarity`'s.** Phase 13 ("The Authoring
Gate") made S13 Phase 0's one-time hand audit of lopi's CLAUDE.md permanent and mechanical:
`lib/claude_contract.py` + `gate_claude_contract` (`packages/konjo-gates-py/.../cli.py`)
check any changed root `CLAUDE.md` against a fixed section order (org rules, stack,
commands, invariants, repo map, repo-specific rules --
`templates/repo-CLAUDE.md` now carries this skeleton with per-section `decays:` stamps
via `lib/doc_staleness.py`'s new `parse_section_front_matter`/`check_sections`, extending
the whole-document-only convention to section granularity) and require every bullet under
an invariants/hard-rules heading to name its enforcing gate or say `ADVISORY` explicitly.
Separately, any changed `.claude/rules/*.md` file is checked for the incident-log shape
(`citation_ratio`): a majority of lines carrying a sprint/date citation records what broke,
not what to check.

**Applying the contract to real lopi content immediately produced a finding, not just a
mechanism**: converting `lopi/CLAUDE.md`'s "Critical Constraints" to name enforcement
(`docs/pilots/lopi-claude-md.proposed.md`) found that 5 of its 6 bullets have **no**
mechanical check today -- only "no `unwrap()`/`expect()` outside tests" is backed by a
real gate (`repo:clippy`'s `-D clippy::unwrap_used -D clippy::expect_used`). The other five
were always advisory in practice; the file just never said so. That is exactly the
"unenforced rule = a claim with no consumer" failure this gate exists to catch, confirmed
on the first real file it was run against, not a hypothetical.

**Also corrects a stale baseline claim.** The sprint brief that opened Phase 13 asserted
lopi's `.claude/rules/security.md` is "a list where every line ends in a sprint citation."
Read this sprint: 4 of its 11 substantive lines do (`citation_ratio` ~0.36, below this
gate's 0.5 majority threshold) -- the file was evidently partially cleaned up since that
claim was written. The gate does not fire on lopi's current `security.md` as a result,
which is itself evidence the check works as designed (it should not flag a file that
is not, in fact, majority-incident-log) and a correction recorded here per the sprint's
own instruction to fix baseline drift rather than carry it forward silently.

Ships `claude_contract.advisory: true` by default (WARN, not FAIL) -- the same
coverage-floor-ratchet adoption pattern K1's `gate_polarity` and this project's other new
gates use, since no repo's existing CLAUDE.md is likely to already be in contract.
Fixture pair: `tests/test_claude_contract.py` (8 cases), kill-test doc
`.konjo/killtests/P13/KT-13.P1.md`.

**Known limit, carried forward rather than silently shipped past**: the enforcement-naming
check verifies a bullet *names something shaped like* a gate reference (`gate_x`,
`repo:x`, `konjo-x`, or `ADVISORY`) -- it does not verify that gate actually exists in the
repo's gate set or actually enforces the claimed behavior. Closing that gap needs a
cross-reference against the profile's declared gates, a meaningfully larger check left for
a future sprint (see `.konjo/killtests/P13/KT-13.P1.md`'s "Limit carried forward").

## Lopi-Gate-Reconciliation-1: nine of lopi's real CI checks stay repo-native by design, not by oversight -- Phase 0 connects the pilot without rebuilding its enforcement

**Non-goal-respecting decision, recorded because "why nothing moved" is exactly the kind
of call a later sprint would otherwise re-litigate.** Phase 0 ("Connect the pilot")
authored `profiles/lopi.yml` (following the `profiles/vectro.yml`/`profiles/squish.yml`
precedent: the profile is authored and lives in kiban, not pushed into the consuming
repo -- this session's `konjoai/lopi` access is read-only, added for reconciliation
research, matching how vectro's and squish's profiles were built) and read
`konjoai/lopi`'s real `.github/workflows/konjo-gate.yml` (789 lines, jobs G0-G5) in full to
decide, per check, PROMOTE / KEEP REPO-NATIVE / DELETE. Phase 0's own brief states a
non-goal explicitly: "improving any gate. This phase connects what exists." That non-goal
is why most of the checks below are KEEP REPO-NATIVE rather than PROMOTE: promoting a
detector kiban does not yet have (coverage-floor parsing, cognitive-complexity-from-clippy-
JSON, the DRY block-similarity scanner, the soft-gate-convention lint) is new gate-building
work, the thing this phase explicitly declines to do. Only one genuine PROMOTE shipped:
`cargo-audit`, because the mechanism to run it (`gate_repo_native`'s generic
`_TOOL_SCOPE`/`_TOOL_BIN`/`_TOOL_PROBE` dispatcher) already existed in kiban -- adding
`cargo-audit` there is a three-line dict entry, connecting an existing mechanism to a tool
name, not building a new detector. It also retroactively activates the same `cargo-audit`
declaration `profiles/vectro.yml` already carried, inert, since before this sprint.

| Check (lopi's G0-G5) | Decision | Why |
|---|---|---|
| G0 doc-staleness (`konjo-doc-staleness scan`) | KEEP REPO-NATIVE | Already kiban's own script; kiban's CI plane has no *blocking* doc-staleness gate of its own yet (`gate_doc_staleness` does not exist in `konjo-gates-py`; the convention is currently session-side only, via `craft`). lopi's G0 is ahead of kiban's own CI plane here, not behind it. |
| G1 rustfmt / clippy hard | KEEP REPO-NATIVE, already wired | `fmt-check`/`clippy` already in `_TOOL_SCOPE`; declared in `profiles/lopi.yml`'s `format_lint`. |
| G1 clippy pedantic (advisory) | KEEP REPO-NATIVE | Soft variant of the above; not a distinct kiban concept. |
| G1 `cargo audit` | **PROMOTE** | New `_TOOL_SCOPE`/`_TOOL_BIN`/`_TOOL_PROBE` entries in `cli.py`; zero new detector logic, the generic dispatcher already existed. |
| G1 dead code (`RUSTFLAGS=-W dead_code`) | KEEP REPO-NATIVE | No kiban gate parses this today; building one is new detector work, out of scope per the non-goal. |
| G1 scope assertion (`.konjo/scripts/scope_assert.py`) | KEEP REPO-NATIVE | Its own docstring names a lopi-specific business-noun term list (`lopi-app`, `CustomerTier`, Stripe fields) -- not portable. Wired into `profiles/lopi.yml`'s `gates:` (G-CAN-FAIL) via its existing `test_scope_assert_killtest.sh`, so kiban's CI plane at least confirms the check's own rejects-test still passes. |
| G1 reachability check | KEEP REPO-NATIVE | Script's own docstring disclaims it is not a real call-graph analyzer; heuristic and workspace-topology-specific. |
| G1 soft-gate-convention lint | KEEP REPO-NATIVE | Real, generic, and worth promoting eventually, but promoting it is new gate work; deferred, not dropped. |
| G1b `npm audit` | KEEP REPO-NATIVE, already wired | `npm-audit` already in `_TOOL_SCOPE`; declared in `format_lint`. |
| G2 eval-executor regression suite | KEEP REPO-NATIVE | This is lopi's own product test suite, not a kiban-shaped gate; covered by `verify_cmd`. |
| G2 coverage-80/95 (`llvm-cov`) | KEEP REPO-NATIVE | No `gate_coverage` exists in kiban; declared in `contract_gates` as documentation of enforcement kiban is aware of, same precedent as `squish.yml`'s/`vectro.yml`'s already-inert `coverage-80` entries. |
| G2 coverage-floor ratchet | KEEP REPO-NATIVE | Same reasoning; wired into `gates:` via its existing `test_coverage_floor_killtest.sh`. |
| G3 mutation testing | KEEP REPO-NATIVE, near-drop-in | `cargo-mutants` is already generically supported (`gate_repo_native`'s diff-scoped mutation path); `mutation: cargo-mutants` in `profiles/lopi.yml` reuses it directly. lopi's percentage-survival reporting stays repo-native as a companion metric. |
| G4 cognitive complexity | KEEP REPO-NATIVE | No kiban gate parses clippy JSON for this; new detector work. |
| G4 file-size-500 | KEEP REPO-NATIVE | Same reasoning; also already inert in `squish.yml`/`vectro.yml`. |
| G4 DRY check (`dry_check.py`) | KEEP REPO-NATIVE | Genuinely portable-looking (multi-language, stdlib-only) and already duplicated near-verbatim across lopi/squish/vectro per this sprint's research -- a strong future-PROMOTE candidate, explicitly flagged in `NEXT_SESSION_PROMPT.md` rather than silently left. |
| G4 rustdoc missing-docs | KEEP REPO-NATIVE | Same reasoning as complexity/DRY. |
| G4b fuzz targets | KEEP REPO-NATIVE | Target list (`jsonrpc_response_fuzz`, `claude_events_fuzz`, `github_webhook_fuzz`) is lopi-specific by construction; never actually run in CI per its own `KNOWN DEBT` marker. |
| G5 adversarial review (`konjo_review.py`, Wall 3) | KEEP REPO-NATIVE, flagged for future consolidation | kiban already has an equivalent generic mechanism (`bin/konjo-review`/`lib/review.py`'s multi-run specialist-lane review with a red-team pass last -- the same "Wall 3" concept squish's profile comment independently describes). Replacing lopi's bespoke 10-question script with kiban's own review engine is a real consolidation opportunity, but doing it is "improving" a gate's mechanism, not connecting what exists -- out of scope for Phase 0, named here so it isn't lost. |
| `unsafe-budget` | **Newly active** (not previously enforced at all) | kiban-native, diff-only, was already generic; `profiles/lopi.yml` is the first profile to actually turn it on for lopi. |

**Nothing was deleted.** Every one of lopi's `konjo-gate.yml` jobs stays in place, unchanged,
per Phase 0's explicit instruction not to silently drop enforcement in the name of
consolidation. `profiles/lopi.yml` documents what kiban's CI plane is aware of and what it
mechanically double-checks (currently: `cargo-audit`, `unsafe-budget`, `polarity`,
`claude_contract`, plus the three `gates:` rejects-tests) alongside what remains solely
lopi's own responsibility.

**Verified, not assumed**: `PYTHONPATH=kiban python3 bin/konjo-gates --profile
profiles/lopi.yml --base HEAD --no-self-test`, run against the real `/workspace/lopi`
checkout, reports `all gates passed` (18/18; `can_fail` genuinely executed and passed all
three of lopi's real kill-test scripts against the real repo, not a mock). `--no-self-test`
because the self-test/eval-corpus gate needs a cassette recorded against a live model for
this specific profile's specialist set, which this session cannot do offline -- recorded as
a carried step in `NEXT_SESSION_PROMPT.md`, not silently skipped.

The proposed `lopi/CLAUDE.md` conversion and the "remove the shadowed local
`konjo-ship`" follow-up are written up in `docs/pilots/lopi-claude-md.proposed.md` rather
than applied directly, since this session holds no push access to `konjoai/lopi`.

**squish and vectro: explicitly deferred, not silently skipped.** Phase 0's step 4 asks
for the same reconciliation on these two repos, or a recorded reason it's deferred. Both
already have a reconciled `profiles/*.yml` (done in earlier sprints, per
`NEXT_SESSION_PROMPT.md`'s carried notes) -- the *profile* half of Phase 0 is not new work
for either. What's genuinely undone for both: the CLAUDE.md org-import conversion and a
formal per-gate promote/keep/delete record, the same shape this entry just did for lopi.
Deferred because this sprint's pilot is lopi specifically (named in the brief; its S13
cleanup gives "a clean surface" the brief calls out by name), neither squish nor vectro was
re-cloned this session, and duplicating the lopi reconciliation's depth for two more repos
inside one sprint would trade real depth on the named pilot for shallow coverage of two
unrequested ones. Next session: repeat this entry's method (`add_repo` read-only, read the
real CI workflow in full, table of promote/keep/delete, propose the CLAUDE.md conversion)
for squish, then vectro.

## Polarity-Waived-Trailer-1: `Konjo-Polarity-Waived` enters the trailer vocabulary -- a permanent grep surface, not reversible without invalidating history

**One-way door.** `lib/oneway.py`'s trailer labels (`Konjo-Acknowledged-Oneway`,
`Konjo-Prove-Merge`) are a permanent surface: any tool, script, or future gate that
greps commit history for acknowledgements now has a third label to know about.
`POLARITY_WAIVED_TRAILER = "Konjo-Polarity-Waived"` was added rather than inventing a
second override mechanism, per the K1 brief's explicit constraint ("Reuse kiban's
trailer mechanism wholesale for waivers. Do not invent a second override channel.").
Reusing `oneway.fingerprint`/`find_trailer`/`make_trailer` unchanged means the new
trailer inherits the exact same binding semantics as the existing two: keyed on the
sorted changed-file set, not diff content (confirmed as existing, not new, behavior in
KT-K1.2, `.konjo/killtests/K1/KT-K1.2.md`) -- a waiver is bound to "this exact set of
touched files," and adding or removing a file invalidates it. Once a repo's commit
history carries this trailer, removing it from the vocabulary would strand every
recorded waiver with no reader; this decision is treated as permanent the same way the
other two trailer labels are.

## Konjo-Ship-Checklist-2: the self-graded "zero dead code" line is gone, replaced by two commands -- every consuming repo's definition of done changes

**One-way door.** `plugins/konjo/skills/konjo-ship/SKILL.md` ships from a single
global clone (not copied per repo), so this change takes effect for every consuming
repo's next sprint close-out simultaneously, the same distribution mechanism that made
the earlier `konjo-doc-staleness scan` replacement (see `Wall-3-Multi-Run-1`'s sibling
entries in this file's history) a one-way door too. The removed line ("Zero debug
artifacts, dead code, or leftover scaffolding") was self-graded by the same agent that
wrote the code being graded -- the maker-as-checker anti-pattern this framework exists
to forbid, applied to the checklist itself rather than the diff. It is replaced by
`konjo-gates polarity` (clean, or every finding waived on the record) and "every
quality gate this sprint touched has a rejecting test" -- both commands with an exit
code, backed by `gate_polarity` and `gate_can_fail` (this sprint). A repo relying on
the old prose line's judgment call now gets a mechanical check instead; there is no
path back to a self-graded version of this line without repeating the exact failure
mode (`run_verifier_pass`, `lopi-remote::whatsapp`) this replacement exists to close.
Net effect on the skill's line budget: +1 over the prior cap-exact 80 lines, carrying
a recorded `konjo-skill-size-ok:` justification rather than silently exceeding the cap.

## KONJO-Forward-Origination-1: `KONJO_FORWARD.md` did not exist; it does now, and the gap is recorded rather than papered over

**One-way door, and an honesty correction.** Both the birth-defect proposal
("Closing the Birth-Defect Gap") and this sprint's own brief cite `KONJO_FORWARD.md`
as an established doc with three named pillars ("Forward-never-back, Main-is-truth,
Loop-runs-to-stop-condition"), a "one idea underneath" section, and a "What Konjo
Forward rejects" list -- quoting exact sentences from it. It was not present in
`konjoai/kiban` at any commit (`git log --all --diff-filter=A --name-only | grep -i
forward` returns nothing) nor in `konjoai/lopi` at `5760da0`. Rather than silently
treating the citations as pre-existing and only appending to them (which would assert
a false continuity the next reader could not verify), the file is originated in this
sprint at the repo root, `decays: intent`, carrying a provenance note at the top
recording exactly this. From this point forward it is the real thing: future sprints
extend it as the brief instructs (K1 added the two rejections named in its own Phase
4 -- permissive unknowns, tests as proof of wiring -- and the residual-limit section;
later sprints add the claim/reachability rejections named in the birth-defect
proposal's §4.2 but out of scope for Family 0). Any future session that finds this
entry confusing should read it as: the doc's *content* was already fully specified
by two prior documents, only its *existence on disk* was missing, and that gap is now
closed.

## Wall-3-Multi-Run-1: the live review gate now costs 3x per PR -- a default change logged because both cost and behavior change

**Default change with a real, ongoing cost, worth logging on that basis alone.**
`review_diff`'s multi-run machinery (`for _ in range(runs)`, the deduped union,
`per_run`) was fully built but the live gate defaulted to `runs=1` --
`bin/konjo-review` and `lib/review.py`'s own keyword default both said one pass is
enough for the single most consequential judgment in the framework: is this diff safe
to merge. It never was. The reviewer is an LLM; `evals/runner.py` has run every
fixture `DEFAULT_RUNS` (3) times since the eval harness shipped, on the explicit
premise that a single sample of a noisy process is not evidence -- the same premise
`prove.py` applies to a noisy perf measurement with 30 paired trials. The live gate
sampled the noisiest, highest-stakes question exactly once, the one place in the
framework where that premise mattered most.

Pre-flight confirmed before touching anything: (1) the split was real --
`evals/runner.py:34` defines `DEFAULT_RUNS = 3`; `bin/konjo-review`'s `--runs`
argparse default and `lib/review.py`'s `review_diff(..., runs=1)` keyword default
were both `1`; (2) the aggregation (`lib/review.py` ~340-380 pre-fix) already unions
`per_run` findings via `dedup()` -- more runs raise recall, they do not add noise, and
`per_run` is preserved so detection rate stays measurable; (3) the prior sprint
(`Wall-3-Fail-Closed-1`, `1.5.0`) had already landed, so an incomplete dispatch inside
one run of a multi-run review still surfaces as `ReviewResult.incomplete` overall --
confirmed by reading `review_diff`'s loop, not assumed, before raising the default
and thereby raising the number of chances for a specialist to fail mid-review.

**The fix**: `DEFAULT_LIVE_RUNS = 3` (new constant in `lib/review.py`), matching
`evals/runner.py`'s `DEFAULT_RUNS` on the principle that the blocking merge review
must not sample the reviewer process less than the eval that validates its own
detection rate. Both `review_diff`'s `runs` keyword and `bin/konjo-review`'s `--runs`
flag now default to it, and both stay overridable (`runs=1` / `--runs 1`) for a
fast/daily manual check. **This is the log-worthy part**: every consuming repo's CI
now makes ~3x the specialist model calls per blocking review by default, with no
action from that repo -- a real, ongoing cost change riding on a default, not a
one-time migration. Scoped deliberately to 2-3 runs, not `prove.py`'s 30: this is
self-consistency damping variance on a categorical judgment, not a numeric
significance test needing statistical power. No change to the specialist set, lens
set, severity model, or fail-closed behavior from `1.5.0`.

**Companion confidence refinement, additive and non-blocking**: a finding's
`recurrence` (how many of the run's independent passes produced it) now bumps its
merged confidence -- unanimous +2, majority +1, single-run +0 -- using data `per_run`
already captured. Deliberately does *not* suppress or demote a single-run finding in
the blocking review: recall is the priority on the merge path, so a defect a
specialist happened to catch on only one of three passes still surfaces exactly as it
would have before this sprint. Recurrence only raises confidence for what already
cleared the per-run gate; it never gate-keeps existence. This is a heuristic, not a
second `prove.py`-style hypothesis test -- deliberately not over-engineered per the
sprint's own scope line.

## Wall-3-Fail-Closed-1: a specialist that doesn't complete now blocks the merge it used to pass

**One-way door, confirmed before any code was written:** every downstream repo's
merge gate now blocks on review incompleteness where it previously passed silently.
A PR that used to go green because a specialist call timed out or the CLI errored out
(read by the old contract as `dispatched=True` with zero findings, indistinguishable
from a clean pass) will now correctly block until the specialist actually completes.
This is deliberate and irreversible in the sense that matters: reverting it puts Wall
3 back into fail-open decoration, the exact `continue-on-error: true` shape the org
spent the doc-integrity and quality-gate sprints eliminating elsewhere, this time
sitting in the keystone gate everything else falls back to.

Pre-flight confirmed the hole before touching it: `CLIBackend.dispatch` (now
`ClaudeCLIBackend`, `lib/review.py`) funneled `TimeoutExpired`, `OSError`, *and* a
non-zero CLI exit to a return value the parser reads as zero findings -- and the
non-zero-exit path was worse than documented: it logged a warning but still returned
`stdout`, so a process that errored out with partial output could have that output
parsed as valid findings rather than discarded. `SpecialistReport.dispatched` (line
167 pre-fix) was `dispatches > 0`, incremented on attempt, not on success, so a failed
specialist read as `dispatched=True` with `n_findings=0` -- the exact false signal a
caller would need to distinguish from a genuinely clean review, and had no field to
do it with.

**The fix, scoped to the failure contract only** (no change to the specialist set,
the lens set, or the severity/confidence gating -- a clean review is exactly as easy
to pass as before): `ReviewBackend.dispatch` returns `str | None`, with `None`
reserved for "did not complete." `SpecialistReport` gains `failed`/`completed`
distinct from `dispatched`. `ReviewResult.incomplete` is true if any selected
specialist failed even after one retry (a single transient timeout gets a retry
before the hard block, mirroring lopi's verifier's retry-then-fail-closed shape
rather than turning every network blip into a merge block). `bin/konjo-review` (the
live gate) and `evals/runner.py` (the eval harness -- same `review_diff` call, per
the module's "one function, two callers" design, so `packages/konjo-gates-py`'s
`gate_self_test` inherits the same fail-closed behavior) both block on `incomplete`
regardless of whether any finding was produced. See `CHANGELOG.md` [1.5.0] for the
full list of touched call sites.

**Why fail-closed instead of fail-open-with-a-warning:** a WARN-only signal is
decoration with worse incentives than nothing -- it trains reviewers to scroll past a
yellow line the same way `continue-on-error: true` trained CI to scroll past red.
Retry-then-block was chosen over immediate-block specifically to keep that
distinction real: a transient network blip should not have the same cost as a
specialist that is actually broken, or operators will (correctly) start treating
every INCOMPLETE as noise. Multi-run self-consistency (running Wall 3 N times and
requiring agreement) was considered and explicitly deferred to a separate sprint
(`NEXT_SESSION_PROMPT.md`) -- it composes with this fix (multi-run makes a single
failure less likely to matter) but fail-closed is the correctness floor, and it
lands first.

## Doc-Integrity-Gate-1 — the konjo-* plane decision, and the Konjo-Doc-Verified trailer

**The konjo-* skill family is absorbed into the global plane — a one-way door,
confirmed with Wes before any code was written, not decided by the agent.** A
source-level audit of `konjoai/lopi` @ `63908a5` found `docs/LOOP_ENGINEERING_ROADMAP.md`
asserting four capability gaps (no MCP, no real worktrees, no runtime skill engine, no
maker/checker split) all closed on `main`. The cause: `konjo-ship/SKILL.md`'s Sprint
Completion Checklist names three filenames (`CHANGELOG.md`, `PLAN.md`, `README.md`);
the roadmap is on none of them and referenced by no skill or instruction file anywhere
in the repo, so it decayed unnoticed. Pre-flight verified, not assumed, before this
call: (1) `konjo-ship` has no canonical source anywhere in `kiban` — the whole tree was
grepped; (2) `lib/self_update.sh` fast-forwards only the global clone at
`$KONJO_HOME/kiban`, never a consuming repo's `.claude/skills/` — read line by line,
not inferred; (3) `konjo-ship/SKILL.md` is byte-identical between `konjoai/lopi` and
`konjoai/miru` (`diff -rq`, zero output) — a hand-copy that has never been re-synced,
across two repos in two different languages (`lopi` is Rust, the checklist's own
`cargo test`/`cargo clippy` lines were wrong for `miru` the whole time). Three options
were on the table: absorb the family into `plugins/konjo/skills/` (single source,
auto-distributed, per-repo customization needs a designed override path); keep the
per-repo plane and build a sync mechanism (preserves tailoring, costs a second
distribution path); or hand-edit `lopi`/`miru` now (rejected by the brief itself — it
reproduces the exact bug this sprint exists to fix). Wes chose absorption. Consuming
repos will start depending on wherever this lands, which is what makes it one-way:
reversing it later means re-forking `konjo-ship` back out to N repos by hand, the thing
this decision exists to stop doing. This sprint moves `konjo-ship` itself
(`plugins/konjo/skills/konjo-ship/SKILL.md`, generalized off Rust-only commands and
off lopi-specific branding) and documents the override path (a repo-scoped
`.claude/skills/<name>/SKILL.md` wins over an identically-named global skill, per
Claude Code's own resolution rule — no new plumbing needed). The other four
(`konjo-boot`, `konjo-philosophy`, `konjo-quality`, `konjo-retrofit`) are not migrated
here; `konjo-quality`/`konjo-retrofit` are Rust-quality-framework specific and need real
generalization, not a file move — see `NEXT_SESSION_PROMPT.md`. `lopi` and `miru` still
carry their local `.claude/skills/konjo-ship/` copies, now shadowing the global one for
those two repos until each repo's own sprint removes its stale local copy; hand-editing
consuming repos is explicitly not this sprint's job.

**`Konjo-Doc-Verified` joins the record-and-check trailer family
(`Konjo-Acknowledged-Oneway`, `Konjo-Prove-Merge`) — same fingerprint scheme, not a
fourth ad hoc format.** `lib/doc_staleness.py` is the mechanism behind the
`decays:` front-matter convention (`plugins/konjo/skills/craft/SKILL.md`): a `state`
doc fails once `verified-against` falls too far behind `HEAD` (default 20 commits / 14
days), and fails hard if `verified-against` is missing at all — the unstamped case that
caused this whole sprint. `historical` docs (`CHANGELOG.md`, `LEDGER.md`, dated audits)
are exempt from staleness by declaration, `intent`/`reference` are warn-only regardless
of age, matching the four classes' actual horizons rather than one blanket rule. The
trailer reuses `oneway.make_trailer`/`oneway.find_trailer` and
`oneway.fingerprint(doc_paths)` — the same fingerprint every other Konjo trailer keys
on — rather than inventing new plumbing. Verified against real drift, not just
synthetic fixtures: run against a real clone of `konjoai/lopi`, the checker correctly
reports 0/72 docs have adopted the convention yet (an honest finding, not a bug — lopi
hasn't opted in, so everything legitimately `SKIP`s); a scratch copy of
`docs/LOOP_ENGINEERING_ROADMAP.md` stamped as it would have been at the commit that
introduced it (`f91b111`, 2026-06-22, the only commit that has ever touched that file)
fails loudly: 440 commits / 32 days behind `HEAD`, on a doc whose four claimed gaps are
all closed at that same `HEAD`. This sprint does not stamp or reclassify any of lopi's
docs — that is lopi's own sprint's job, flagged in `NEXT_SESSION_PROMPT.md`, not this
one's, per the brief's explicit scope line: "do not reclassify lopi's docs from here."
