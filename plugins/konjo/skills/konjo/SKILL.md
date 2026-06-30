---
name: konjo
description: Konjo foundation umbrella skill. Quality gates and the decision Ledger from the kiban global clone. Invoke for org quality tooling, decision logging, or recall of past calls.
---

# konjo

The umbrella skill for the Konjo foundation (`kiban`). It groups the quality and memory
tools the org shares: the Ledger (decide, recall), the learnings log (correct, the
compounding loop), and the prose lint. The tools keep the `konjo-*` brand; `kiban` is the
repo they ship from.

## Self-update preamble (run first, every invocation)

Before doing anything else, run the throttled, failure-safe self-update so the session
plane stays current against the global clone. This is the gstack-style update path: a
plain `git pull`, no marketplace. It can never block or error the session.

```bash
bash "$HOME/.konjo/kiban/plugins/konjo/hooks/preamble_update.sh"
```

The update is a no-op when:
- `KONJO_SKIP_UPDATE=1` is set, or
- the throttle interval (`KONJO_UPDATE_INTERVAL`, default 3600s) has not elapsed, or
- the clone is pinned via `.konjo/kiban.ref` or `KIBAN_REF` (it checks out that ref
  instead of pulling main).

## What this skill routes to

- `decide`: log a durable decision to the Ledger.
- `correct`: turn a caught mistake into a durable rule (the compounding loop).
- `recall`: search the Ledger (decisions) and the learnings log before re-litigating a past
  call or repeating a known mistake.
- `longrun`: make a benchmark or training script resumable (the checkpoint/resume contract).
- `konjo-prose`: editorial lint (no em dashes, no AI-tell vocabulary).

## Ethos (do not weaken)

Ship over optimize. Kill-test first. Statistical rigor. Honest negative results.
Evidence first, not deference. Token-efficient context.
