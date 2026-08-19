# Konjo Ledger event schema

The Ledger is append-only and event-sourced. Each event is one file. The current
state is folded from the stream; nothing is mutated in place.

## Storage

- Directory: `$KONJO_CORTEX_DIR/ledger/events/` (defaults to `~/.konjo/cortex/ledger/events`;
  `KONJO_CORTEX_DIR` names the local `konjo-cortex` clone). One file per event, named
  `<id>.json`, written through `lib/event_store` (atomic write-once, injection-rejected,
  redact-scanned). Superseded by `Ledger-Laptop-Only-1` in `LEDGER.md` -- Sprint K5 moved
  the Ledger's canonical home from a laptop-only `~/.konjo/state/ledger/decisions.jsonl`
  into the shared `konjo-cortex` clone, so any surface with Cortex checked out (laptop,
  cloud session, phone routine) can write and every surface can read.
- A shared append-only JSONL file conflicts at the last line on every concurrent write --
  the one place a merge tool cannot resolve safely. Separate files never conflict: two
  surfaces adding two events add two files.
- A directory listing carries no chronological order, so the fold (`ledger/engine.py`)
  sorts events by `decided_at` (falling back to `date`, then `id`) before folding, rather
  than relying on file position -- see `Ledger-Events-Per-File-1` in `LEDGER.md` for the
  stated ceiling this trades away (directory listing doesn't scale the way a single file
  read scales, at very large event counts) and the concurrent-write kill-test (KT-10).
- Tests use an explicit relative path (`Ledger("ledger/events")`), resolved under
  `KONJO_STATE_DIR` like any other `lib/event_store`-backed store -- only the production
  default resolves under `KONJO_CORTEX_DIR` instead.

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

---

# PR telemetry event schema

Phase 0 of the review-pipeline plan (`KONJO_REVIEW_PIPELINE_PLAN.md` section 4, Sprint P0
section 2). A third sibling stream on the same substrate, `ledger/pr_telemetry.jsonl`. Not
a Decision Ledger event -- a measurement, not a durable call -- so it does not go through
`Ledger.decide()`. See `ledger/pr_telemetry.py`.

## Storage

- File: `~/.konjo/state/ledger/pr_telemetry.jsonl` (`KONJO_STATE_DIR`-overridable).
- One JSON object per line, append-only, injection-rejected, redact-scanned, same as the
  decision Ledger and learnings log.
- Purely additive: re-running backfill over an already-recorded commit appends a second
  record rather than replacing the first (see `PrTelemetry.for_sha` for idempotent-read
  dedup at the caller layer).

## Events

### pr_telemetry

One record per merged PR (one merge commit).

| field | type | capture | notes |
|-------|------|---------|-------|
| event | string | | `"pr_telemetry"` |
| id | string | | sha prefix (12 hex chars), so backfill re-runs are traceable to the commit |
| repo | string | | e.g. `"lopi"` |
| scope | string | | `org` or `repo:<name>`, as elsewhere |
| source | string | | `"backfill"` or `"live"` |
| recorded_at | string | | ISO 8601 UTC, when this record was appended (not when the PR merged) |
| recorded_by | string | | who/what ran the recording (script name or author) |
| sha | string | git | the merge commit sha |
| merged_at | string\|null | git | ISO 8601 UTC merge timestamp |
| files_touched | list[string] | git | paths changed |
| path_classes | list[string] | git | `docs`, `assets`, `meta`, `test`, `generated`, `src`, `infra`, `gate` (plan section 2.1) |
| lines_added | int\|null | git | |
| lines_removed | int\|null | git | |
| crates_touched | list[string] | git | Rust workspace members touched |
| ast_delta | object\|null | git | `{"identical": n, "bodies_changed": n, "signatures_changed": n}`, `syn`-derived |
| trigger_surface_hits | list[string] | git | unsafe / subprocess / deserialization / path construction / auth / network / SQL / crypto / FFI / concurrency / new-dependency, per plan section 2.1 |
| weakening_markers | list[string] | git | added `#[allow(...)]`, `continue-on-error: true`, `#[ignore]`, removed assertion, deleted test, `?`→`.unwrap()`, lowered gate threshold |
| new_dependencies | list[string] | git | new lines in a dependency manifest |
| tokens_input | int\|null | live | |
| tokens_cache_read | int\|null | live | |
| tokens_cache_write | int\|null | live | |
| tokens_output | int\|null | live | |
| wall_clock | float\|null | live | seconds |
| runner_minutes | float\|null | live | CI runner minutes consumed |
| coverage_delta | float\|null | live | percentage points, this PR vs. base |
| mutation_score_on_diff | float\|null | live | diff-scoped `cargo mutants --in-diff` survival, when run |
| review_rounds | int\|null | live, null until Phase 3 | |
| findings_raised | int\|null | live, null until Phase 3 | |
| findings_that_caused_a_change | int\|null | live, null until Phase 3 | |
| findings_later_contradicted | int\|null | live, null until Phase 3 | |

## Derived state

None. Unlike the decision Ledger, telemetry records are not superseded or redacted --
each merge commit gets exactly one canonical record (barring an idempotency-violating
re-run of backfill, which is a caller bug, not a first-class event type).
