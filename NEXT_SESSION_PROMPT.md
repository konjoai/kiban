# Next session: Phase 14 follow-ups (the full Phase 3 protocol, squish/vectro CI connection, vectro's stale pin), then K2

## Phase 14 handoff: scale Phase 3 up, connect squish's CI, bump vectro's stale kiban pin

Phase 14 ("The Measurement Harness," `CHANGELOG.md` [1.9.0]) shipped the task-to-diff
loop KT-13.1 named as missing (`lib/gen_runner.py`, `evals/gen_cassettes.py`,
`konjo-eval genrun`), closed the defect classifier from 3 to 7 of 8 taxonomy classes,
and ran a real (small) slice of Phase 3 -- an honest null on the two candidates it
tested, found and fixed two real classifier bugs along the way. See
`.konjo/killtests/P14/` for KT-14.1, KT-14.2, and the Phase 3 report; `LEDGER.md` for
every one-way door.

1. **Scale Phase 3 up to the specified protocol.** This sprint measured 2 tasks × 3
   conditions (baseline, candidate 3, candidate 5) × 3 runs = 18 sessions -- the brief's
   own floor is 12-20 tasks × 3 runs per condition, and Phase 3 asks for all six
   candidates measured individually (7 conditions total), i.e. 252-420 sessions at the
   floor. Not affordable in one session on top of everything else this sprint required;
   stated plainly rather than shrunk further. The harness (`bin/konjo-eval genrun`,
   `lib/gen_runner.py`, `evals/gen_cassettes.py`) is real, tested, and ready to scale --
   do not rebuild it. Two things to fix before scaling up, both found live this sprint
   and already fixed once but worth re-checking against a larger, more diverse task set:
   the test-code exclusion (`lib.defect_shapes.added_lines_excluding_test_scope`) is a
   line-scan heuristic, not real scope tracking -- verify it holds on Python/TypeScript
   test conventions too (this sprint only exercised it against Rust `mod tests` blocks).
2. **Measure candidates 2, 4, and 6** (untrusted-by-default, no-raw-indexing, no
   failure-path-without-a-test) -- not reached this sprint's live-model budget. Given
   this sprint's finding that an *incidental*-risk task needs a verified non-zero
   baseline rate to measure a reduction against (see
   `.konjo/killtests/P14/phase3-report.md`'s methodological lesson), pick or construct
   tasks accordingly rather than assuming any feature task will do -- e.g. run baseline
   first across a wider task pool and keep only the ones that already show the target
   defect at least once.
3. **Attempt candidate 1 only if there is budget to spare.** The brief's own note: it is
   the fail-closed shape `gate_polarity` already catches deterministically since 1.7.0,
   so it is the lowest-priority of the six and a null is the expected result.
4. **Connect `konjo-gates` to squish's CI.** Reading squish's real `.github/workflows/
   konjo-gate.yml` in full this sprint found it has no `konjo-gates` job at all -- unlike
   lopi (Sprint S13R, Phase A, this same week) and vectro (a separate, if badly stale,
   `konjo-gates.yml`). `profiles/squish.yml`'s `format_lint`/`contract_gates` are real
   and ready; nothing in squish's own repo invokes them. Same connection lopi's Phase A
   did, following `templates/repo-ci.yml`.
5. **Bump vectro's stale `KIBAN_REF`.** `konjoai/vectro`'s real `konjo-gates.yml` pins
   `v1.1.5` -- confirmed this sprint, ~7 minor kiban releases behind. Vectro's only
   genuinely-blocking kiban gate (its own "Wall 2" `konjo-gate.yml` is almost entirely
   `continue-on-error: true` -- see `LEDGER.md`'s `Squish-Vectro-Gate-Reconciliation-1`)
   has been running a version of kiban that predates `gate_polarity`, `gate_can_fail`,
   the doc-integrity gate, Wall-3 multi-run, and all of Phase 13. This session's
   read-only access cannot push the bump; a `konjoai/vectro` PR is the fix, then
   re-verify `konjo-gates --profile .konjo/profile.yml` against a real vectro checkout,
   the same closing step `Lopi-Gate-Reconciliation-1` used.
6. **Apply the prepared squish/vectro CLAUDE.md conversions.** This session held
   read-only access to both repos; `docs/pilots/squish-claude-md.proposed.md` and
   `docs/pilots/vectro-claude-md.proposed.md` are ready to apply as PRs to each repo
   (both verified for real against `lib.claude_contract.check_contract` this sprint).
   Once either lands, flip that repo's `profiles/*.yml` `claude_contract.advisory` to
   `false`, the same way `profiles/lopi.yml` did this sprint.
7. **Decide `raw_index_external_input`'s classification path.** Still `None` --
   genuinely not classifiable at diff-grep granularity (needs dataflow/taint tracking).
   An LLM-classified pass with a measured inter-rater agreement rate was considered and
   explicitly not attempted this sprint (see `LEDGER.md`'s `Defect-Classifier-Gap-1`);
   worth real consideration once Phase 3 has more live-model budget to spend on it.
8. **Promote the DRY check (`dry_check.py`) into kiban proper.** Carried from Phase 13's
   `LEDGER.md`: the strongest repo-native-to-promote candidate, near-verbatim duplicated
   across lopi, squish, and vectro already, multi-language and stdlib-only by design.
9. **Consider consolidating lopi's bespoke Wall-3 adversarial review** (`konjo_review.py`)
   with kiban's own `bin/konjo-review`/`lib/review.py` multi-run specialist engine --
   flagged, not attempted, in `Lopi-Gate-Reconciliation-1` (a real gate-mechanism change,
   out of scope for "connect what exists, don't improve it").
10. **Close the `gate_claude_contract` known limit** named in
    `.konjo/killtests/P13/KT-13.P1.md`: the enforcement-naming check verifies a bullet
    *names something shaped like* a gate reference, not that the named gate actually
    exists. Cross-referencing against the profile's real declared gate set is the fix.

## K2 handoff: G-WIRED + G-CLAIM (Families A/B of the birth-defect proposal)

K1 (Failure Semantics, this sprint -- see `CHANGELOG.md` [1.7.0] and `LEDGER.md`'s
three K1 entries) shipped `G-POLARITY` and `G-CAN-FAIL`, Family 0 of "Closing the
Birth-Defect Gap." Sequencing per that proposal's §6: K2 is `G-WIRED` (a field only
test code ever sets) and `G-CLAIM` (no unproven quantitative claim), in that order --
`G-WIRED` is cheap and narrow and catches lopi's single most expensive defect
(`api_client`'s one write site, one caller, and that caller was a test); `G-CLAIM`
reuses `newonly.py`'s new-findings-only differ and the trailer mechanism wholesale, the
same way K1's waiver channel did.

**Carried finding, load-bearing for how ambitious K2's detectors can be:** KT-K1.1
(`.konjo/killtests/K1/KT-K1.1.md`) found G-POLARITY's shape *cleanly separable* with a
five-pattern, per-language regex vocabulary -- no AST, no type information, and the
detector needed exactly one non-obvious restriction (a bare terminal `else` only counts
as "unrecognised case" when preceded by at least one `else if`) to avoid a false
positive on a real adjacent branch (`scorer.rs`'s `skip_build_check` domain check
sitting four branches from the real defect, both setting the identical constant).
That is a favorable data point for regex/grep-shaped detection in general, but it does
not automatically transfer to G-WIRED or G-CLAIM:

- **G-WIRED needs cross-reference, not local shape.** "A field with exactly one write
  site and that site is test-only" requires finding *every* write site for a field
  across a crate/package, not scanning one function's condition/return shape in
  isolation. This is a different, harder detection problem than G-POLARITY's --
  probably still regex/grep-shaped per the birth-defect proposal's own honesty
  ("Implementation honesty... the cheap approximation... is a module-level reference
  scan," §Family B), but budget a K2 kill-test (construct lopi's pre-F1
  `api_client`/`with_api` state, verbatim, the same KT-K1.1 discipline) before assuming
  the cheap version catches it. If it doesn't cleanly separate a real test-only write
  site from a real production one, the same rescope-to-advisory fallback K1's own brief
  specified for G-POLARITY applies here too -- do not skip that check just because K1's
  version of it turned out well.
- **G-CLAIM is closer to K1's shape** (pattern-match a quantitative-claim vocabulary in
  prose/doc-comments, not control flow) and should reuse `lib/newonly.py`'s
  `_findings_at_head` pattern the same deliberate way K1's brief specified and this
  sprint followed for the waiver trailer -- see `gate_polarity` in `cli.py` for the
  net-new-via-base-file-diff pattern K1 used (mirrors `gate_prose`, not a literal
  `newonly.net_new` subprocess call, since these are in-process AST/regex scans, not
  external scanner shells).

Do not assume K1's clean separation generalizes; write each family's own KT-K2.x
fixture set from real lopi source *before* writing the detector, per the same
anti-goal K1's brief named and this sprint held to (fixtures assembled from `5760da0`
before `lib/polarity.py` existed, never edited afterward to fit what the detector
caught).

## Wall-3 run-count tuning from measured detection rates (companion to 1.6.0)

1.6.0 defaulted the live gate (`bin/konjo-review`, `review_diff`) to
`DEFAULT_LIVE_RUNS = 3` self-consistency passes and added a recurrence-based
confidence bump (see `CHANGELOG.md` [1.6.0] and `LEDGER.md`'s `Wall-3-Multi-Run-1`
entry). That fix picked one run count for every specialist, chosen to match
`evals/runner.py`'s `DEFAULT_RUNS` -- a considered number, but a uniform one, not one
derived from how much a second or third pass actually helps each specialist.

**Not done in the 1.6.0 sprint, on purpose (explicitly out of scope there, per its own
"no per-finding statistical test" line):** per-specialist run counts. Some specialists
(e.g. a lens with a narrow, mechanical check) likely have near-100% single-pass recall,
where a second run buys nothing but cost; others (a lens judging something fuzzier,
like `red-team`'s adversarial pass) may have real run-to-run variance where a third
pass catches what the first two missed. Today every specialist gets the same `runs`
count, uniformly.

A follow-up sprint should:
1. Use `lib/specialist_stats.py` (already folds the review log into per-specialist
   dispatch/finding counts) as the evidence source -- extend it, or a sibling
   analysis, to measure per-specialist detection-rate lift from run 1 to run 2 to run
   3 across real logged reviews (`review_log.py`'s output, which now carries
   `per_run` and `recurrence` per finding after 1.6.0).
2. Decide a per-specialist `runs` override only once that data exists in enough
   volume to clear `specialist_stats`'s own `INSUFFICIENT_DATA` floor (default 10
   dispatches) -- do not guess ahead of the evidence; that would repeat exactly the
   mistake this project's ethos exists to avoid ("evidence first, not deference").
3. If the lift data shows most specialists plateau after 2 runs, that is itself a
   finding worth logging even if it argues for *lowering* `DEFAULT_LIVE_RUNS` back
   toward 2 -- honest negative results, not just the result that happens to justify
   more model spend.

## Doc Integrity Gate follow-ups (1.4.0)

This release built the `decays:` convention and `lib/doc_staleness.py` (see
`CHANGELOG.md` and `LEDGER.md`). What's deliberately not done here:

1. **Layer 4 — generating state tables from code probes, not front-matter honesty
   alone.** `doc_staleness.py` only checks whether a `state` doc's *stamp* is current;
   it cannot tell whether the doc's *claims* are true. That's real and valuable, and it
   belongs in `lopi`, where the four wrong claims this sprint's audit found (no MCP, no
   real worktrees, no runtime skill engine, no maker/checker split) are mechanically
   checkable against a real codebase — `src/mcp_commands.rs`, `crates/lopi-git/src/
   worktree.rs`, `crates/lopi-skill/`, the isolated `VerifierAgent`. Do not attempt this
   in kiban; it is out of scope here by design.
2. **The `lopi` sprint this checker is for.** `konjoai/lopi` currently has zero docs
   using the `decays:` convention (confirmed this sprint — `konjo-doc-staleness scan`
   against a real clone at `63908a5` reports 72 `SKIP`, 0 `FAIL`; that is an honest
   finding, not a clean bill of health). A follow-up `lopi` sprint should: adopt
   `decays:` front matter on `docs/LOOP_ENGINEERING_ROADMAP.md` and its siblings,
   reclassify the ones that are actually done (`historical`, with a superseded banner)
   rather than re-verifying claims that are simply wrong, and wire
   `konjo-doc-staleness` into `lopi`'s own CI once its docs are stamped. This sprint
   does not reclassify any of lopi's docs — that is lopi's sprint's job.
3. **The rest of the konjo-* family.** `konjo-ship` moved into
   `plugins/konjo/skills/` this sprint (see `LEDGER.md` for the plane decision).
   `konjo-boot`, `konjo-philosophy`, `konjo-quality`, and `konjo-retrofit` did not:
   `konjo-quality`/`konjo-retrofit` are Rust-quality-framework specific (hardcoded
   `cargo`/`clippy` commands, a lopi/miru-specific repo-type checklist) and need real
   generalization, not a file move. `lopi` and `miru` still carry their local
   `.claude/skills/konjo-ship/` copies, now shadowing the global one for those two
   repos specifically — removing the stale local copy is each repo's own call, not
   this sprint's (per "do not hand-edit consuming repos").
4. **Optional: wire `doc_staleness` into `konjo-gates` as a report-only gate**, the
   way `gate_context_budget`/`gate_skill_size` are report-only until calibrated. Not
   done here because doing it before any repo has adopted `decays:` would either warn
   on everything (noise) or check nothing (a no-op) — wait for a repo to actually stamp
   docs first, per the "optional hardening" discipline below. This is safer now than it
   would have been at 1.4.0: `craft` runs the scan before any build step and `konjo-ship`
   requires zero repo-wide FAILs before shipping (1.4.1, in response to feedback that the
   original checklist only re-verified docs "touched by this sprint" — a doc nobody
   touches can still go stale from time alone, with no session ever assigned to fix it).
   A CI gate wired in now would mostly be catching what a session already fixed upstream,
   not surprising anyone with an unfixable red build.
5. **kiban's own docs haven't adopted `decays:` either.** `README.md` and
   `DISTRIBUTION.md` are natural `reference`-class candidates; `NEXT_SESSION_PROMPT.md`
   itself is arguably `state`. Worth dogfooding once the convention has seen one real
   consuming-repo adoption, so the worked examples aren't purely synthetic.

---

# Next session: post-1.0.0 (pilots and activation, not new phases)

kiban reached 1.0.0. The evolution plan's twelve phases are all shipped: the substrate and
Ledger (0.1-0.4), the prove gate and Squish pilot (0.5-0.6), the pack seam and Rust pack
(0.7), the compounding loop (0.8), the long-run gate (0.9), the craft skill (0.10), lifecycle
hooks and the headless helper (0.11), and the context-budget guardrail plus the TypeScript
pack (1.0). The remaining work is not new mechanism; it is reconciling seeded profiles against
real repos and activating the gates that are honestly inert.

## What 1.0.0 built (Phase 12)

- `gate_context_budget` (always-on context under a token ceiling, ~463 of 1500 on the core)
  and `gate_skill_size` (no SKILL.md over the line cap without a `konjo-skill-size-ok:`
  justification). Both report-only; the core is green, which is what gated the 1.0.0 cut.
- The TypeScript pack (`lib/packs/lang/typescript`: `type-soundness`, `async-correctness`,
  reusing `api-surface`/`red-team` via `SCOPE_TS`), the TS tools wired into `konjo-gates-py`
  (`tsc`, `eslint`, `stryker`, `npm audit`), the seeded `profiles/ts_example.yml`, and the TS
  eval corpus.

## Carried activation steps (the real backlog now)

1. **VECTRO reconciliation** (Phase 7): DONE in 1.0.1, extended in 1.1.0. `profiles/vectro.yml`
   was reconciled against the real `konjoai/vectro` repo (stack `[rust, python, typescript,
   mojo]`, the konjo-gate.yml gate set, prove metric `qps`, `verify_cmd`/`format_cmd`). The
   Mojo surface (38 `.mojo` files) is covered by the new Mojo pack (1.1.0). The only thing
   still PENDING for VECTRO is its prove `min_effect_pct`, which needs a bench-host run (see
   step 3); everything else is confirmed.
2. **TypeScript pilot**: `profiles/ts_example.yml` is seeded, not a real repo. When a JS/TS
   repo is piloted, reconcile it, confirm the TS lanes against real diffs, and decide whether
   a Node-native `konjo-gates-js` runner is worth building (today TS runs through the single
   Python orchestrator, exactly as Rust does).
3. **Prove gates on bench hardware**: the Squish prove gate (since Phase 5) and the VECTRO
   prove gate are both honestly NOT ACTIVATED, PENDING a `min_effect_pct` measured on real
   bench hardware. Work each profile's activation checklist.
4. **Rust and TypeScript cassettes**: recorded against a live model this session; re-record
   only if a lane is reworded (the frozen prompt-hash test in `tests/test_packs.py` guards
   against accidental drift).

## Optional hardening (only if a real need appears, never speculatively)

- Flip `gate_context_budget` / `gate_skill_size` from report-only (WARN) to blocking once the
  ceilings are calibrated against more usage. A one-line change each; do it when a real bloat
  regression is caught, not before.
- A Node-native `konjo-gates-js` only for a JS-first CI environment that refuses a Python
  toolchain on the runner.

## Tag and release discipline (in force)

`release.yml` cuts the release and tag server-side on a VERSION change on main. The 1.0.0 bump
is a one-way door, confirmed and logged. Post-1.0, follow SemVer: patch for fixes, minor for
additive packs/gates, major only for a breaking change to the profile schema or the gate
contract.

## Still out, permanently

The Machine Room hub, cross-model review as a default, web/design/iOS/browser tooling,
psychographic/profile-tuning behavior, completeness-toward-10 defaults, the plugin
marketplace, and "boil the ocean" completeness.
