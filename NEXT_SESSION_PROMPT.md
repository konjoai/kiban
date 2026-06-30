# Next session: Phase 12 (1.0.0), the context-budget gate and the TypeScript pack

## What Phase 11 built (0.11.0)

Lifecycle hooks and the headless host helper.

- `lib/headless.py` + `bin/konjo-headless`: the headless `claude -p` invocation, baking
  `--bare` (fast start) and `--output-format stream-json` (a realtime event stream), and the
  `--verbose` the CLI requires alongside stream-json (verified, not assumed). Closes the lopi
  `claude_stream.rs` gap by construction.
- `templates/hooks/`: two opt-in hooks, both tied to verification. `stop-verify.sh` runs
  `verify_cmd` and blocks a red end-of-turn; `posttooluse-format.sh` runs `format_cmd` after
  an edit and never blocks. `bin/konjo-profile-get` reads the fields; `format_cmd` is a new
  profile field.

## Carried activation steps (unchanged, still parked)

1. **Rust cassettes** (Phase 7): ACTIVATED; no carried step.
2. **VECTRO reconciliation** (Phase 7): reconcile `profiles/vectro.yml` and clear every
   UNVERIFIED field (stack, tools, prove fields, `verify_cmd`) when VECTRO unparks.
3. **Squish prove gate** (Phase 5): still PENDING on the M3 bench hardware.

## Phase 12 tasks (1.0.0)

Evolution plan section 8 and section 5c/5d. This is the 1.0.0 cut; do not cut it until the
context-budget gate is green on the core itself.

1. **`gate_context_budget`** (report-only first, blocking once calibrated): measure the token
   cost of the always-on session-plane preamble plus the umbrella skill text, and fail a
   change that pushes it over a ceiling (start at a measured number, e.g. ~1,500 tokens for
   the umbrella skill plus ethos). kiban holds itself to this the way it dogfoods prose_lint
   and shellcheck. Packs load only when their scope fires; they are never always-on, so they
   do not count against the budget.
2. **A skill-size limit**: no single SKILL.md over a fixed length without a recorded
   one-way-door justification. The mechanical version of "if it could be 50 lines, rewrite it,"
   applied to the framework's own prose.
3. **The TypeScript pack** (`lib/packs/lang/typescript`): the lanes the `SCOPE_TS` flag was
   added for in Phase 7 (`type-soundness`, `async-correctness`, `api-surface` reused). Tool
   table: `tsc --noEmit`, `eslint`, `stryker`, `npm-audit`/`pnpm audit` (the JS realization of
   supply_chain). A third repo profile if a JS repo is available, else seed it UNVERIFIED.
4. **`konjo-gates-js`**: the JS CI-plane runner, mirroring konjo-gates-py, wiring the TS tools.
5. Eval fixtures for the TS lanes (planted bug per lane + a clean control), cassettes recorded
   if a model is reachable, else NOT ACTIVATED per the Phase 7 honesty rule.

Cut 1.0.0 only when `gate_context_budget` is green on the core. Classify and confirm the
1.0.0 VERSION bump as a one-way door, and log it to the Ledger.

## Tag and release discipline (in force)

`release.yml` cuts the release and tag server-side on a VERSION change on main. Every VERSION
bump is a one-way door: classify and confirm it. The build environment cannot push tag refs.

## Still out, permanently

The Machine Room hub, cross-model review as a default, web/design/iOS/browser tooling,
psychographic/profile-tuning behavior, completeness-toward-10 defaults, the plugin
marketplace, and "boil the ocean" completeness.
