---
name: recall
description: Search the Konjo Ledger (decisions) and the learnings log before re-litigating a past call or repeating a known mistake. Surfaces active items first and shows supersede chains. Use before reopening a settled question or a class of mistake.
---

<!-- konjo-skill-size-ok: carries the four skis-contract must-match blocks
(chain-reasoning, redacted-vs-absent, freshness-basis, output-shape) verbatim
alongside the learnings-search half that has no skis counterpart. The shared
blocks are enforced identical with konjo-skis/recall/SKILL.md by
bin/konjo-skis-check (konjo-skis/CONTRACT.yml); splitting them out would
either duplicate the enforcement surface or break the single-file-per-skill
convention. This length is a recorded one-way door, Sprint K3. -->

# recall

Search the org memory before reopening a settled question or repeating a known mistake.
This is the guard against re-litigating a call the org already made and against rediscovering
a mistake the org already turned into a rule. The memory has two streams on one substrate:
the Ledger (decisions) and the learnings log (mistakes turned into rules).

This file and `konjo-skis/recall/SKILL.md` are a declared pair
(`konjo-skis/CONTRACT.yml`, enforced by `bin/konjo-skis-check`). Sections
marked `skis-contract:*` below must stay in sync with their counterpart
there -- edit both, or the gate fails the build. `konjo-skis/recall` has no
learnings-search counterpart (Cortex projects the decision Ledger only, not
the learnings log), so that section below is outside the contract.

## Self-update preamble (run first)

```bash
bash "$HOME/.konjo/kiban/plugins/konjo/hooks/preamble_update.sh"
```

## How to search decisions

<!-- skis-contract:recall.read-path -->
```bash
konjo-decision search "<keywords>"            # active matches only
konjo-decision search "<keywords>" --scope org
konjo-decision search "<keywords>" --all      # include superseded and redacted
```

Search is substring/keyword over the decision text and rationale, run
directly against the live `~/.konjo/state/ledger/decisions.jsonl` stream --
no projection step, no staleness window.
<!-- /skis-contract:recall.read-path -->

## How to search learnings

```bash
konjo-learn search "<keywords>"               # active learnings only
konjo-learn search "<keywords>" --scope org
konjo-learn search "<keywords>" --all         # include redacted
```

Search is substring/keyword over the mistake, the rule, and the enforcement target. Use
this before repeating a class of mistake: if the org already learned it, the rule names
where it now lives (a CLAUDE.md line, a prose-lint word, a lane, or a gate).

## How to answer

<!-- skis-contract:recall.chain-reasoning -->
A decision with a supersede chain has one active entry and the rest
superseded. Name the active entry as the current answer. Only walk the
chain or mention a superseded predecessor when the question is explicitly
about history ("what did we used to do", "why did this change") rather than
the present state.
<!-- /skis-contract:recall.chain-reasoning -->

<!-- skis-contract:recall.redacted-vs-absent -->
"No record" and "redacted/superseded" are different answers and must not be
collapsed into one. Before concluding nothing was decided, check retired
and superseded entries, not just the active set -- a redacted decision is
still real history, just not the current call. Only say "no record" once
both active and retired/superseded have been checked and neither has a
match.
<!-- /skis-contract:recall.redacted-vs-absent -->

<!-- skis-contract:recall.freshness-basis -->
State the basis for how current your answer is before giving it. Reading a
Cortex projection: cite the page's `projected-at` front-matter stamp (e.g.
"as of the last Cortex refresh, 2026-08-06"). Reading the live Ledger
directly: say the answer reflects the stream as of now. Never answer
without naming one of the two.
<!-- /skis-contract:recall.freshness-basis -->

<!-- skis-contract:recall.output-shape -->
Every answer names: the current call (or "no record" per the
redacted-vs-absent rule above), the freshness basis it was read under, and
whether a supersede chain exists for the topic. State these plainly rather
than requiring the reader to infer them from the citation alone.
<!-- /skis-contract:recall.output-shape -->

## When to use

- Before proposing something that smells like a past call (decisions).
- Before repeating something that smells like a past mistake (learnings).
- When you need the rationale behind a current convention, or the rule behind a gate.
- When you suspect a decision has been superseded and want the chain.

If nothing matches, that absence is itself a signal: the question may be genuinely new,
so log the new decision with `decide`, or, if you just caught a mistake, the new rule with
`correct`.
