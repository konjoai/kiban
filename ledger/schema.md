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

---

# Konjo learnings log event schema

The learnings log is the second stream of the lab notebook, a sibling of the decision
Ledger on the same substrate. It records the compounding loop: a mistake turned into a
durable rule. Same storage discipline (append-only, atomic, injection-rejected,
redact-scanned); same scoping (`org` or `repo:<name>`).

## Storage

- File: `~/.konjo/state/ledger/learnings.jsonl` (state dir is `KONJO_STATE_DIR`-overridable).

## Events

### learn

A mistake turned into a rule. The enforcement target is load-bearing: a `learn` with no
enforcement target is refused (it is a note, not a learning).

| field | type | notes |
|-------|------|-------|
| event | string | `"learn"` |
| id | string | 12-hex unique id |
| scope | string | `org` or `repo:<name>` |
| mistake | string | one line: what went wrong |
| rule | string | the rule that prevents it |
| enforcement | string | where the rule now lives (CLAUDE.md line, prose-lint word, lane, gate). REQUIRED, non-empty |
| date | string | ISO 8601 UTC |
| author | string | who logged it |

### redact

Retires a learning without rewriting history. The target stops being active.

| field | type | notes |
|-------|------|-------|
| event | string | `"redact"` |
| id | string | event id |
| redacts | string | the id being retired |
| reason | string | why it was retired |
| date, author | | as above |

## Derived state

- **active**: a learn whose id is not redacted by a later event.

## The guardrail

A learning must name an enforcement target. A learning with no target is not a learning, it
is a note, and notes do not go in the log. `konjo-learn add` refuses one (exit 4). This is
what keeps the loop tied to mechanism instead of becoming a diary.
