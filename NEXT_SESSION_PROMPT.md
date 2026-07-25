# Next session: Wall-3 multi-run, then Doc Integrity follow-ups, then post-1.0.0 pilots

## Wall-3 multi-run (companion to the 1.5.0 fail-closed fix)

1.5.0 made Wall 3 fail closed on a specialist that does not complete (see
`CHANGELOG.md` [1.5.0] and `LEDGER.md`'s `Wall-3-Fail-Closed-1` entry). That fixes the
failure contract only: a specialist either completes and its verdict counts, or it
fails (after one retry) and the whole review is `INCOMPLETE`. It says nothing about a
specialist that *completes* but is simply wrong on a given run -- a real model can miss
a bug on one pass and catch it on the next, and today a single completed run is the
whole verdict.

**Not done in the 1.5.0 sprint, on purpose (explicitly out of scope there):**
self-consistency across multiple runs of Wall 3 on the same diff, i.e. requiring
agreement (or a supermajority) across N independent completed runs before a clean
verdict is trusted, the same way `evals/runner.py` already runs each eval fixture
`DEFAULT_RUNS` (3) times and applies a stricter detection-rate bar for CRITICAL bugs
than for lower severities. The live gate (`bin/konjo-review`) still reviews a working
diff with `runs=1` by default.

A follow-up sprint should:
1. Decide whether `bin/konjo-review`'s default `runs` should move above 1 for the live
   gate (cost/latency tradeoff: each additional run is a real specialist dispatch,
   i.e. real wall-clock and, in production, a real model call).
2. Decide the agreement rule for a clean verdict across runs -- unanimous silence
   (strictest, matches the `must_be_silent` control's per-run bar in the eval harness)
   vs. a supermajority (matches the eval harness's non-CRITICAL `must_flag` bar:
   detected on at least one run is enough to flag, so silence would need to hold on
   *every* run to still pass clean).
3. Wire it through the same `ReviewResult`/`SpecialistReport` surface 1.5.0 added
   (`per_run`, `incomplete`) rather than a parallel mechanism -- `per_run` already
   carries what each run individually found; this is a question of what `review_diff`
   (or its caller) does with that list before returning a verdict, not a new plumbing
   layer.
4. Multi-run composes with the 1.5.0 fix, not against it: an `INCOMPLETE` run should
   presumably not count as a "clean" vote in whatever agreement rule lands (an
   incomplete run carries no signal either way, per `ReviewResult.incomplete`'s own
   docstring) -- confirm that composition explicitly rather than assuming it falls out
   for free.

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
