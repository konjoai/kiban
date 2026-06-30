---
name: correct
description: Turn a caught mistake into a durable rule. Writes a learning to the log, proposes the smallest durable fix (a CLAUDE.md rule, a prose-lint word, a new lane, or a gate), and applies it on confirmation. Use the moment you catch the agent doing something wrong.
---

# correct

The compounding loop. When you catch the agent doing something wrong, do not just fix it in
this chat. A correction that only fixes this run is a patch; a correction that edits the
rules is a fix. `correct` records the mistake as a durable rule so the class of mistake does
not recur.

## Self-update preamble (run first)

```bash
bash "$HOME/.konjo/kiban/plugins/konjo/hooks/preamble_update.sh"
```

## The three steps

### 1. Recall first

Check whether this class of mistake was already learned, so you extend a rule rather than
duplicate it:

```bash
konjo-learn search "<keywords of the mistake>"
```

### 2. Write the learning

A learning is four things, and the enforcement target is load-bearing:

```bash
konjo-learn add --scope org \
  --mistake "<one line: what went wrong>" \
  --rule "<the rule that prevents it>" \
  --enforcement "<where the rule now lives: a CLAUDE.md line, a prose-lint word, a new lane, or a gate>" \
  --author <you>
```

The guardrail: a learning MUST name where its rule lives. A learning with no enforcement
target is not a learning, it is a note, and `konjo-learn` refuses it. This keeps the loop
tied to mechanism and stops the log from becoming a diary.

### 3. Propose the smallest durable fix, apply on confirm

Propose the smallest change that makes the rule mechanical, then apply it only after the
human confirms. In order of preference (smallest first):

- A `CLAUDE.md` line in the affected repo (a rule the agent reads every session).
- A `konjo-prose` word (an editorial tell the lint will now catch).
- A new specialist check (a review lane sees the pattern on every diff).
- A new gate (a blocking contract in `konjo-gates`).

Match the enforcement target you named in step 2 to the fix you apply. A learning that
names `tests/...` and a fix that edits `CLAUDE.md` is an inconsistency; reconcile them.

## When to use

- The agent repeated a mistake a rule could have caught.
- A review or a human caught a class of defect, not a one-off typo.
- A negative result worth not rediscovering, where the rule has a home.
