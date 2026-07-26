# Ledger

A running log of load-bearing design decisions — the ones that would be expensive to
silently re-litigate in a later sprint. One entry per sprint, newest first. Not a
changelog (that's `CHANGELOG.md`) — this is *why*, not *what*. (kiban's runtime
decision Ledger — `ledger/engine.py`, `bin/konjo-decision` — records the durable calls
a *consuming* repo makes during a session, scoped `org`/`repo:<name>`, in
`~/.konjo/state/ledger/decisions.jsonl`; this file is kiban's own project-level
record of its architecture, the way `lopi`'s `LEDGER.md` records lopi's.)

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
