---
name: recall
description: Search the Konjo Ledger (decisions) and the learnings log before re-litigating a past call or repeating a known mistake. Surfaces active items first and shows supersede chains. Use before reopening a settled question or a class of mistake.
---

# recall

Search the org memory before reopening a settled question or repeating a known mistake.
This is the guard against re-litigating a call the org already made and against rediscovering
a mistake the org already turned into a rule. The memory has two streams on one substrate:
the Ledger (decisions) and the learnings log (mistakes turned into rules).

## Self-update preamble (run first)

```bash
bash "$HOME/.konjo/kiban/plugins/konjo/hooks/preamble_update.sh"
```

## How to search decisions

```bash
konjo-decision search "<keywords>"            # active matches only
konjo-decision search "<keywords>" --scope org
konjo-decision search "<keywords>" --all      # include superseded and redacted
```

Search is substring/keyword over the decision text and rationale. A superseded
decision still surfaces so the chain reads end to end (`old -> ... -> active`).

## How to search learnings

```bash
konjo-learn search "<keywords>"               # active learnings only
konjo-learn search "<keywords>" --scope org
konjo-learn search "<keywords>" --all         # include redacted
```

Search is substring/keyword over the mistake, the rule, and the enforcement target. Use
this before repeating a class of mistake: if the org already learned it, the rule names
where it now lives (a CLAUDE.md line, a prose-lint word, a lane, or a gate).

## When to use

- Before proposing something that smells like a past call (decisions).
- Before repeating something that smells like a past mistake (learnings).
- When you need the rationale behind a current convention, or the rule behind a gate.
- When you suspect a decision has been superseded and want the chain.

If nothing matches, that absence is itself a signal: the question may be genuinely new,
so log the new decision with `decide`, or, if you just caught a mistake, the new rule with
`correct`.
