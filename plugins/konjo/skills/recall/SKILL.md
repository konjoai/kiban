---
name: recall
description: Search the Konjo Ledger before re-litigating a past decision. Surfaces active calls first and shows supersede chains. Use before reopening a settled question.
---

# recall

Search the Ledger before reopening a settled question. This is the guard against
re-litigating a call the org already made. It returns active decisions first and keeps
supersede chains visible so you can read how a decision evolved.

## Self-update preamble (run first)

```bash
bash "$HOME/.konjo/kiban/plugins/konjo/hooks/preamble_update.sh"
```

## How to search

```bash
konjo-decision search "<keywords>"            # active matches only
konjo-decision search "<keywords>" --scope org
konjo-decision search "<keywords>" --all      # include superseded and redacted
```

Search is substring/keyword over the decision text and rationale. A superseded
decision still surfaces so the chain reads end to end (`old -> ... -> active`).

## When to use

- Before proposing something that smells like a past call.
- When you need the rationale behind a current convention.
- When you suspect a decision has been superseded and want the chain.

If nothing matches, that absence is itself a signal: the question may be genuinely new,
so log the new decision with `decide`.
