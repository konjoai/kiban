# Next session: migrate consuming-repo pins to signed tags, then Wall-3 run-count tuning, then Doc Integrity follow-ups, then post-1.0.0 pilots

## Migrate existing pins from mutable refs to signed tags (companion to 1.7.0)

1.7.0 (see `CHANGELOG.md` and `LEDGER.md`'s `Sign-Distribution-1`/`-2` entries) made
`lib/self_update.sh` verify a signed tag before it will apply an unpinned update or
honor a pin, and it refuses -- rather than silently no-ops -- a pin that names a
mutable ref (a branch) or an unsigned tag. That is the correct behavior going forward,
but it means **any consuming repo currently pinned to `main`, another branch, or an
unsigned tag stops receiving kiban updates the moment it picks up this version**, with
no error, just a `~/.konjo/security.log` entry an operator has to go looking for. This
sprint deliberately did not touch any consuming repo's pin (out of scope: "do not
hand-edit consuming repos"), so that migration is unstarted.

A follow-up sprint should:
1. Enumerate every repo's current pin (`.konjo/kiban.ref`, `KIBAN_REF` in CI) across
   `lopi`, `miru`, and any other consuming repo -- `templates/repo-CLAUDE.md`'s
   "Pinning" section and each repo's own copy of it is the starting list. `lopi` pins
   `v1.4.0` per this sprint brief's own framing; confirm whether that pin is already an
   annotated tag (it predates signing, so it is not *signed*, but check whether it's at
   least a real tag object vs. a branch name -- that changes how urgently it needs to
   move).
2. For each repo pinned to anything other than a `vX.Y.Z` tag cut *after* 1.7.0 lands
   (i.e., a signed one), bump the pin to the newest signed tag available at the time,
   the same deliberate, repo-by-repo schedule the rollout control already uses --
   never all repos at once.
3. Confirm each migrated repo's next session actually applies the pin (no
   `pin_refused` entries appear in that repo's `~/.konjo/security.log` afterward).
4. Until a repo's pin is migrated, its session plane is frozen at whatever it last
   pinned -- flag this loudly in that repo's own state docs so it isn't mistaken for
   "kiban development stalled" when it's really "this repo hasn't migrated its pin
   yet."

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

`release.yml` cuts the release on a VERSION change on main, and (since 1.7.0) creates and
pushes a **signed** annotated tag itself (`git tag -s -a`, ssh format, `RELEASE_SIGNING_KEY`
secret) before creating the GitHub release against it -- see `docs/DISTRIBUTION.md` and
`LEDGER.md`'s `Sign-Distribution-1`/`-2` entries. This is now load-bearing, not optional: a
release that lands without a valid signed tag is one every consuming repo's `self_update.sh`
will silently refuse to propagate. The 1.0.0 bump is a one-way door, confirmed and logged.
Post-1.0, follow SemVer: patch for fixes, minor for additive packs/gates, major only for a
breaking change to the profile schema or the gate contract.

## Still out, permanently

The Machine Room hub, cross-model review as a default, web/design/iOS/browser tooling,
psychographic/profile-tuning behavior, completeness-toward-10 defaults, the plugin
marketplace, and "boil the ocean" completeness.
