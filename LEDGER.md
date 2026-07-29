# Ledger

A running log of load-bearing design decisions — the ones that would be expensive to
silently re-litigate in a later sprint. One entry per sprint, newest first. Not a
changelog (that's `CHANGELOG.md`) — this is *why*, not *what*. (kiban's runtime
decision Ledger — `ledger/engine.py`, `bin/konjo-decision` — records the durable calls
a *consuming* repo makes during a session, scoped `org`/`repo:<name>`, in
`~/.konjo/state/ledger/decisions.jsonl`; this file is kiban's own project-level
record of its architecture, the way `lopi`'s `LEDGER.md` records lopi's.)

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
