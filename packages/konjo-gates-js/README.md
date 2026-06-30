# @konjoai/konjo-gates-js

A Node-native CI-plane gate runner for Konjo JS/TS repos. **Stub: not the active path.**

## Status (Phase 12, 1.0.0)

TypeScript is enforced today through the single Python orchestrator, `konjo-gates`
(`konjo-gates-py`), exactly as Rust is. The orchestrator imports the real engine, routes
changed files by `diff_scope` scope, runs the kiban-native gates, and shells out to the TS
tools wired into its tables: `tsc --noEmit`, `eslint`, `stryker`, and `npm audit`, each
wrapped in `konjo-newonly` so only net-new findings block. The TypeScript review lanes
(`type-soundness`, `async-correctness`, plus the shared `api-surface` and `red-team`) ship in
`lib/packs/lang/typescript`.

This keeps a single source of truth for the gate logic (the decision behind the root
distribution): a Node reimplementation would duplicate the engine. So a TS repo uses the same
pinned `kiban` distribution and `konjo-gates --profile .konjo/profile.yml` that every other
stack uses.

## When this becomes the active path

A Node-native runner earns its keep only for a JS-first CI environment that does not want a
Python toolchain on the runner. It lands when a real JS repo is piloted as such; until then it
stays a stub and TS runs through `konjo-gates`.
