# Konjo Ledger event schema

The Ledger is append-only and event-sourced. Each line in `decisions.jsonl` is one
event. The current state is folded from the stream; nothing is mutated in place.

## Storage

- File: `~/.konjo/state/ledger/decisions.jsonl` (state dir is `KONJO_STATE_DIR`-overridable).
- One JSON object per line, written through `lib/jsonl_store` (atomic append,
  injection-rejected, redact-scanned).

## Scoping

- `org`: cross-repo memory. The org-wide decision log.
- `repo:<name>`: local to one consuming repo.

A search may filter by scope or span all scopes.

## Events

### decide

A durable call.

| field | type | notes |
|-------|------|-------|
| event | string | `"decide"` |
| id | string | 12-hex unique id |
| scope | string | `org` or `repo:<name>` |
| decision | string | the call, one line |
| rationale | string | why, plainly |
| alternatives_considered | list[string] | rejected options |
| confidence | int | 0-10 |
| date | string | ISO 8601 UTC |
| author | string | who logged it |

### supersede

A later decide that replaces an earlier one. Carries its own full decision payload.

| field | type | notes |
|-------|------|-------|
| event | string | `"supersede"` |
| id | string | new decision id |
| supersedes | string | the id being replaced |
| scope | string | inherited from the prior decision |
| decision, rationale, alternatives_considered, confidence, date, author | | as in decide |

### redact

Retires a decision without rewriting history. The target stops being active.

| field | type | notes |
|-------|------|-------|
| event | string | `"redact"` |
| id | string | event id |
| redacts | string | the id being retired |
| reason | string | why it was retired |
| date, author | | as above |

## Derived state

- **active**: a decide whose id is neither superseded nor redacted by a later event.
- **chain**: for a superseding decision, the ordered list of ids it replaced, so the
  full lineage reads `oldest -> ... -> active`.
