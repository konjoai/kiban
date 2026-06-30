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

1. **VECTRO reconciliation** (Phase 7): DONE in 1.0.1. `profiles/vectro.yml` was reconciled
   against the real `konjoai/vectro` repo (stack `[rust, python, typescript]`, the
   konjo-gate.yml gate set, prove metric `qps`, `verify_cmd`/`format_cmd`). The only thing
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
