# Next session: finish Phase 2 of the review-pipeline plan (sections 1, 3, 4)

Sprint P2 (`CHANGELOG.md` [1.12.0], full reasoning in `LEDGER.md`'s
`Review-Pipeline-Phase-2`, primary detail in lopi's own `LEDGER.md` entry of the same
name) ran the full pre-flight (PF-0 through PF-3), shipped section 2's feedback
formatter, and deliberately deferred sections 1, 3, and 4. Read `LEDGER.md`'s
`Review-Pipeline-Phase-2` entry in full before starting anything below -- it has the
complete PF-1/PF-2 findings and the PF-3 kill-test methodology, none of which should
be re-derived.

## What's already done and should not be re-derived

1. **PF-0: a full-workspace `cargo mutants --workspace` baseline against lopi has not
   completed and is currently stopped, not running** -- see lopi's `LEDGER.md`,
   `Review-Pipeline-Phase-2` entry for the full record of three launch attempts.
   5,315 mutants found; best progress reached was 10.2% (544 mutants) before dying.
   **Do not relaunch this inside another interactive Claude Code session and expect
   it to finish.** Two independent launches each died within roughly an hour of
   starting, both times near a gap between the session's own turns rather than at a
   random point mid-run, with no panic/OOM/kill signal in either case -- the
   diagnosis in lopi's `LEDGER.md` is that this class of session environment
   suspends (preserving disk, killing live processes) when idle between turns, which
   no amount of relaunching from inside it can fix. Confirm that diagnosis or refute
   it before trying a fourth time the same way; either way, the real fix is a runner
   that stays up unattended for the full ~20-hour extrapolated completion time
   (dedicated CI, persistent infrastructure), not another ephemeral
   interactive session left to run in the background and hope.
2. **PF-1 confirmed lopi's mutation gate (`konjo-gate.yml` G3) already rejects on
   breach** -- no fix owed to section 3's "the gate must be able to reject"
   requirement, unlike what the plan anticipated might be needed.
3. **PF-2 confirmed cargo-mutants' own `outcomes.json` already resolves every field
   section 2 needs** (file, line, qualified enclosing item name via
   `function.function_name`, full item span via `function.span`, replacement) --
   `konjo-ast-diff-rs` is not needed for section 2. It IS still needed for section 1
   (see below).
4. **PF-3 passed**: a 10-mutant pilot found mutation-specific test generation beats
   generic "write more tests" 9/10 vs 7/10, arm B never losing a case arm A won. Full
   methodology and the secondary test-reliability finding in `LEDGER.md` -- this is
   evidence enough to proceed with sections 1/3/4, not something to re-run before
   starting (the real 30-run KT-D stays blocked on PF-0's completion regardless).
5. **`lib/mutation_feedback.py` (section 2) ships, verified against both a synthetic
   fixture and a real 11-mutant `lopi-ratelimit` run.** `format_feedback(repo,
   mutants_out_dir, cap=20)` is the entry point section 3's loop should call directly
   -- do not write a second surviving-mutant parser.

## Section 1: uncovered-item extraction (not started)

Parse each repo's native coverage output (lcov for lopi, coverage.py for squish), map
uncovered lines to enclosing items, emit a ranked list (uncovered-line count
descending, per the plan's own "attack the largest gaps first" instruction).

**`konjo-ast-diff-rs`'s existing `ItemSig`/`collect_items`
(`packages/konjo-ast-diff-rs/src/main.rs:75-119`) need line-span capture added before
they can serve this** -- today `ItemSig` carries only `qualified_name` and
token-stream text (`signature_tokens`/`body_tokens`), built for gate_polarity's
before/after body-diffing, with no line-range field at all. `syn`'s own span info
(available via the `proc_macro2::Span` on any parsed item, given `syn`'s
`span-locations` feature or `full` parsing mode -- check what's already enabled
before adding a new feature flag) is the natural source; extend `ItemSig` with a
`start_line`/`end_line` pair rather than writing a second walker, per the plan's own
"reuse it" instruction. `collect_items` is not currently `pub` (this is a CLI binary,
`src/main.rs`, not a library crate) -- decide whether section 1 needs it as a library
dependency (making `konjo-ast-diff-rs` a lib+bin crate) or can shell out to the binary
with a new output mode; check which is less invasive before choosing.

**Verify:** run against lopi at HEAD, hand-check 3 items against the lcov report
directly, per the plan's own instruction.

## Section 3: the loop and the gate (not started, blocked on PF-0)

Coverage run -> uncovered items (section 1) -> model writes tests -> `cargo mutants
--in-diff` on the changed lines -> surviving mutants -> feedback (section 2, already
built) -> back to model, round cap and per-round token ceiling required (L25
precedent), gate on zero surviving mutants or an explicit kledger waiver.

**The waiver mechanism already exists and needs no new plumbing**: `lib/oneway.py`'s
trailer substrate (`POLARITY_WAIVED_TRAILER`, `oneway.py:30`,
`make_trailer`/`find_trailer`) -- mint a sibling `Konjo-Mutation-Waived` trailer
through the same functions, the same way `gate_polarity` (K1) already does, rather
than inventing a second override channel.

**Do not build this section's exit-gate verification against the current 3.8%-complete
baseline.** The plan's own PF-0 instruction is explicit that section 3 is calibrated
against the full run; wait for it (or accept and clearly label a partial-baseline
caveat if a full run genuinely isn't feasible in this environment -- but say so, don't
build silently against a number known to be wrong).

**Verify:** one real end-to-end run on a deliberately under-tested fixture in
`evals/fixtures/rust/` (does not exist yet -- create it). Report rounds taken, mutants
killed per round, tokens spent per round -- none of this exists yet.

## Section 4: `konjo/mutation-hunt` skill (not started, depends on section 3)

Package sections 2 and 3's loop as a reusable skill so squish and vectro consume it
via pin bump. Per Sprint S13's own rule (cited in the plan): a skill file with no real
call site is not a shipped feature -- wire the call site before claiming this done,
same discipline the plan's own brief calls out.

## Non-goals, unchanged from the plan

Any critic, router, tier, or `routing.toml`; wiring `planner_executor` into lopi's
`AgentRunner::run()`; the `RepoProfile`/`allow_self_modify`/cost-breaker gaps from
Phase 1's audit table; `auth`/`path_construction` trigger detection; Kani harnesses;
changing any coverage floor.
