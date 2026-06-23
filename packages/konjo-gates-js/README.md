# @konjoai/konjo-gates-js

CI-plane gate runner for Konjo JS/TS repos. **Phase-1 stub (spec only).**

The working package shells out to `eslint`, `tsc`, and `stryker` per the consuming
repo's profile, selecting gates by changed-file scope, and exits nonzero on a blocking
failure. The CI plane is self-contained and never reads `~/.konjo`; the gate logic is
this pinned package.

## Planned use (in a consuming repo's CI)

```bash
npx --package @konjoai/konjo-gates-js@0.1.0 konjo-gates-js --profile .konjo/profile.yml
```

## Status

Spec only this sprint. The working runner lands in Phase 1.
