---
name: craft
description: How to build, the Konjo way. Four behaviors (think before coding, simplicity first, surgical changes, goal-driven execution) plus the verify-loop. Opt-in per repo. Invoke before a non-trivial build step.
---

# craft

How to build, the Konjo way. Four behaviors plus a verify-loop. This is prose, deliberately
short: it is loaded per repo and pays a token cost, so it carries the rules and nothing else.

## Self-update preamble (run first)

```bash
bash "$HOME/.konjo/kiban/plugins/konjo/hooks/preamble_update.sh"
```

## Think before coding

State your assumptions. If interpretations differ, present them rather than pick one
silently. If a simpler path exists, say so. If something is unclear, stop and name it. This
is "evidence first, not deference" applied to the build step.

## Simplicity first

The minimum that solves the problem, nothing speculative. No configurability that was not
asked for. If it is 200 lines and could be 50, rewrite it. This is "ship over optimize."

## Surgical changes

Touch only what the task requires. Match the existing style even if you would do it
differently. Do not refactor unbroken code. Remove only the orphans your own change created.
Mention unrelated dead code; do not delete it.

## Goal-driven execution

Turn the task into a verifiable success criterion before starting, and loop until it is met.
"Fix the bug" becomes "write a test that reproduces it, then make it pass." This is
"kill-test first" pointed at ordinary work.

## Verify-loop

Every repo declares how the agent verifies its own work: the `verify_cmd` in its profile (a
test command, a bench command, a browser path for a web UI, a simulator for iOS). Run that
loop before claiming done. This is the single highest-value habit, made a per-repo contract
rather than a hope.

A repo with no `verify_cmd` is a surfaced gap (the gate warns), the way a missing prove
threshold is, not a hard block. If yours has none, add one.
