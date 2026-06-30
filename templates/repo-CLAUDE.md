# CLAUDE.md (consuming-repo template)

Drop this into a consuming repo's root. It imports the org rules from the global kiban
clone (the session plane) and then adds repo-specific rules below.

## Org rules (imported from kiban)

@~/.konjo/kiban/plugins/konjo/skills/konjo/SKILL.md

The org ethos applies here: ship over optimize, kill-test first, statistical rigor,
honest negative results, evidence first, token-efficient context.

Editorial rules: no em dashes, no AI-tell vocabulary. The prose lint enforces it; run
`konjo-prose` on docs before pushing.

Log durable decisions with `konjo-decision decide` at `repo:<this-repo>` scope. Search
with `konjo-decision search` before reopening a settled call.

When you catch a mistake worth not repeating, invoke `correct`: it records a learning with
`konjo-learn` and proposes the smallest durable fix. A learning must name where its rule
lives (a CLAUDE.md line, a prose-lint word, a lane, or a gate), or it is refused. Search
past learnings with `konjo-learn search` before repeating a class of mistake.

Build the Konjo way: the `craft` skill carries the four behaviors (think before coding,
simplicity first, surgical changes, goal-driven execution) plus the verify-loop. Declare a
`verify_cmd` in this repo's profile (the test/bench/browser path that proves a change works)
and run it before claiming done; a missing one is surfaced as a warning.

## Pinning

This repo pins a kiban ref in `.konjo/kiban.ref` (and `KIBAN_REF` in CI). The session
plane checks out that ref on self-update instead of pulling main, so kiban changes land
here on a deliberate schedule. The current recommended pin is `v1.0.1`.

## Repo-specific rules

<!-- Add rules unique to this repo below. Keep them plain. -->
