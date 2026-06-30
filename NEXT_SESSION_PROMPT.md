# Next session: Phase 11 (lifecycle hooks and the headless host helper)

## What Phase 10 built (0.10.0)

The craft skill: one small, opt-in skill carrying how to build the Konjo way, plus the
verify-loop made a per-repo contract.

- `plugins/konjo/skills/craft/SKILL.md`: the four behaviors (think before coding, simplicity
  first, surgical changes, goal-driven execution) plus the verify-loop. Routed from the
  `konjo` umbrella. Deliberately short.
- `verify_cmd` profile field + `gate_verify_cmd` (report-only WARN): a repo declares how the
  agent verifies its own work; a missing one is a surfaced gap, not a hard block. squish
  declares `pytest`; vectro's is an honest UNVERIFIED TODO.

## Carried activation steps (unchanged, still parked)

1. **Rust cassettes** (Phase 7): ACTIVATED; no carried step.
2. **VECTRO reconciliation** (Phase 7): reconcile `profiles/vectro.yml` and clear every
   UNVERIFIED field (now including `verify_cmd`) when VECTRO unparks.
3. **Squish prove gate** (Phase 5): still PENDING on the M3 bench hardware.

## Phase 11 tasks (lifecycle hooks + multi-host generation)

Evolution plan section 9. Keep hooks opt-in and few; two narrow hooks, both tied to
verification, is the ceiling. Hooks and preamble logic are where bloat accumulates, so resist
adding more.

1. An optional **Stop-hook** template that runs the repo's `verify_cmd` (Phase 10) when the
   agent ends a turn, so a long autonomous run cannot end on a red state silently. The
   deterministic version of "verify with a background agent when done."
2. An optional **PostToolUse format hook** template that runs the repo's formatter after an
   edit, so a formatting slip never reaches CI. Low-risk, keeps the format gate quiet.
3. The **headless host helper**: bake `--bare` (the SDK skips CLAUDE.md/MCP discovery, up to
   10x faster startup) and `--output-format stream-json` into the kiban headless invocation
   helper, so every repo's `claude -p` automation starts fast and emits structured events.
   (This also closes the lopi `claude_stream.rs` gap: the missing `--output-format
   stream-json` is the same flag.)
4. Kill-test: the hooks are opt-in templates; verify the Stop hook runs `verify_cmd` and the
   format hook runs the formatter, both without a model or network.

## Then Phase 12 (1.0.0)

The context-budget guardrail enforced as a gate (`gate_context_budget`, report-only then
blocking once calibrated), a skill-size limit, the TypeScript pack (`lib/packs/lang/typescript`,
the lanes the `SCOPE_TS` flag was added for in Phase 7), and the `konjo-gates-js` runner. Cut
1.0.0 only when the budget gate is green on the core itself.

## Tag and release discipline (in force)

`release.yml` cuts the release and tag server-side on a VERSION change on main. Every VERSION
bump is a one-way door: classify and confirm it. The build environment cannot push tag refs.

## Still out, permanently

The Machine Room hub, cross-model review as a default, web/design/iOS/browser tooling,
psychographic/profile-tuning behavior, completeness-toward-10 defaults, the plugin
marketplace, and "boil the ocean" completeness.
