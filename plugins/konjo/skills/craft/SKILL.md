---
name: craft
description: How to build, the Konjo way. The build behaviors from Karpathy's field notes (read before you write, think before coding, simplicity, surgical changes, verification, goal-driven execution, debugging, dependencies, communication, and the common failure modes) plus the verify-loop. Opt-in per repo. Invoke before a non-trivial build step.
---

# craft

How to build, the Konjo way: the field notes earned by watching the same model mistakes
twice. The throughline is one thing: the model is fast at generating plausible code and slow
at noticing that plausible is not the same as correct, so the discipline comes from the
process. This is prose, not machinery, and it is opt-in per repo (loaded only when invoked,
so it does not count against the always-on context budget).

## Self-update preamble (run first)

```bash
bash "$HOME/.konjo/kiban/plugins/konjo/hooks/preamble_update.sh"
```

## Read before you write

The biggest source of bad model-written code is writing before reading. Read the files you
are about to touch; read, do not skim. Copy the patterns that already exist, and check what
the project actually depends on, so you do not reach for `axios` where everything is `fetch`.
When you cannot find a pattern, ask instead of guessing.

## Think before coding

State your assumptions ("add authentication" is five different things, so name the one you
picked and name the tradeoffs). If interpretations differ, present them rather than pick one
silently. If something is genuinely confusing, stop and ask rather than fill the gap with
plausible-looking code; that is exactly the code that passes a casual review and fails when
it matters. This is "evidence first, not deference" applied to the build step.

## Simplicity first

Write the minimum that solves the problem in front of you, not the minimum that could solve
every future version of it. Resist premature abstraction, skip error handling for errors that
cannot occur, and hardcode values until there is a real reason to configure them. If the only
reason something is abstracted is "in case we need to," you have over-built it. This is "ship
over optimize."

## Surgical changes

Your diff should be as small as the task allows. Do not touch what you were not asked to
touch, match the existing style, and do not reformat: a formatter pass buries the three lines
that matter inside three hundred that do not. The test is whether you can justify every
changed line by the task. If a line is there because "while I was in there," revert it. Remove
only the orphans your own change created; mention unrelated dead code, do not delete it.

## Verification (the verify-loop)

The gap between code that works and code you think works is testing. Every repo declares how
the agent verifies its own work: the `verify_cmd` in its profile (a test command, a bench
command, a browser path for a web UI, a simulator for iOS). Run that loop before claiming
done. Test behavior that can actually break, not that a constructor sets a field. If something
is hard to test, that is information about the design, not permission to skip it. A repo with
no `verify_cmd` is a surfaced gap (the gate warns), the way a missing prove threshold is.

## Goal-driven execution

Every task needs a success criterion before code is written. "Add validation" becomes "reject
a missing or malformed email, return 400 with a clear message, and test both cases." For
anything multi-step, state the plan first so the user can catch a wrong approach before you
spend an hour building it. This is "kill-test first" pointed at ordinary work.

## Debugging

When something breaks, investigate; do not guess. Read the whole error and the stack trace,
reproduce the bug before you change anything, and change one thing at a time. Do not paper
over an unexpected null with a null check; find out why it is null, or the bug just moves
somewhere quieter.

## Dependencies

Every dependency is permanent code you do not control. Before adding one, ask whether the
project or the standard library can already do it (`crypto.randomUUID()` over a uuid package).
When you do add one, say why, so the choice is visible rather than smuggled into the manifest.
Konjo's supply-chain gates (`cargo-deny`, `npm-audit`, the still-stubbed `supply_chain`) are
the mechanical half of this; the behavior is the other half.

## Communication

Say what you did and why, not just a block of code. Flag concerns even when you did exactly
what was asked, and be precise about uncertainty: "I am not sure this library supports
streaming" tells the user what to verify; "I think this should work" does not. This is "honest
negative results" made a habit.

## Common failure modes

A few patterns recur often enough to name. Catch yourself in any of these and the right move
is to stop, not push through:

- **Kitchen Sink**: restructuring half the codebase while you are at it (see surgical changes).
- **Wrong Abstraction**: copy-paste twice before you abstract (see simplicity first).
- **Optimistic Path**: the happy path handled and the 500 ignored (see verification).
- **Runaway Refactor**: a fix that cascades across files (stop and re-scope).
