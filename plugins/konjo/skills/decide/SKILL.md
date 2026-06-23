---
name: decide
description: Log a durable decision to the Konjo Ledger with rationale, rejected alternatives, and a confidence score. Use when making a call worth remembering across sessions or repos.
---

# decide

Record a durable decision in the Konjo Ledger. The Ledger is append-only and
event-sourced: nothing is ever overwritten, and "active" is computed from the event
stream. Use this for any call future-you (or another repo) would want the provenance
of.

## Self-update preamble (run first)

```bash
bash "$HOME/.konjo/kiban/plugins/konjo/hooks/preamble_update.sh"
```

## How to log a decision

```bash
konjo-decision decide \
  --scope org \
  --decision "<the call, one line>" \
  --rationale "<why, plainly>" \
  --alt "<a rejected alternative>" \
  --alt "<another rejected alternative>" \
  --confidence <0-10> \
  --author <you>
```

- `--scope` is `org` (cross-repo memory) or `repo:<name>` (local to one repo).
- Record rejected alternatives. A decision without its alternatives is half a record.
- Free-text fields are redact-scanned on write; a HIGH-tier secret blocks the write.

## When to use

- A load-bearing choice (architecture, distribution, language, scope boundary).
- A kill-test verdict or a prove verdict.
- A negative result worth not rediscovering. Record those plainly.
