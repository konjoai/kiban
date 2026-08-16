# KT-3 — Does a Claude Code routine reach a Cortex page? (BLOCKED, infra gap not fixed)

**Verdict: BLOCKED, not PASS, not FAIL.** `konjo-cortex` now exists (private,
personal account, `wesleyscholl/konjo-cortex`) with `repo-kiban.md` (the real
`repo:kiban` Cortex page, folded from the K1 fixture corpus via
`lib/cortex.py:render_scope()`) and `README.md` pushed to `main`
(`8aef317`). That was the blocker recorded in `LEDGER.md`'s
`Cortex-Projection-1` entry last time this kill-test ran (`403` on
`mcp__github__create_repository`) — it is fixed. But standing the repo up
surfaced a second, more specific blocker: **a bare Claude Code routine
(`create_trigger` with `create_new_session_on_fire: true`) gets zero MCP
connector tools by default, and `konjo-cortex` is private, so the fired
session had no verified path to the file's content at all** — independent of
whether the Cortex mechanism itself works.

## Method

1. Confirmed via `ListConnectors` (twice, at the start and again mid-session)
   that no GitHub connector is registered under claude.ai Settings →
   Connectors for this account. Only Canva, Gmail, Google Calendar, Google
   Drive, Mermaid Chart (authless, disabled), Superhuman Docs (disabled), and
   Trello are connected.
2. Created a throwaway Routine (`create_trigger`, `create_new_session_on_fire:
   true`) whose prompt was: *"Read repo-kiban.md in the GitHub repository
   wesleyscholl/konjo-cortex (main branch) via the GitHub connector and tell
   me the current (active) decision about konjo-decision search's default
   review pass count — cite the decision id."* Correct answer: id
   `4d26cb337b09`, "Default review_diff to runs=3 instead of runs=1."
3. `create_trigger`'s own response returned an explicit warning: *"this
   trigger stores no MCP connectors, so the sessions it fires will run
   without connector (`mcp__<server>__*`) tools."* The returned
   `session_context.allowed_tools` list for the fired session confirmed this:
   `Task, Bash, Glob, Grep, Read, Edit, MultiEdit, Write, NotebookEdit,
   WebFetch, TodoWrite, WebSearch, BashOutput, KillBash, Skill, Tmux, Monitor,
   SendUserFile, REPL` — zero `mcp__` entries. No GitHub connector, no GitHub
   MCP server, no `add_repo`.
4. Fired it (`fire_trigger`). The session (`session_013TsakpgNVYDBg7VaC3iuSM`)
   transitioned PENDING → RUNNING → IDLE and produced a real final turn
   (`cache_read_tokens: 381348`, `cache_write_tokens: 49711`,
   `output_tokens: 1468` — substantive work, not an instant no-op or error
   exit).
5. Independently confirmed, via the GitHub API from this (non-routine)
   session, that `wesleyscholl/konjo-cortex` is **private**
   (`GET /repos/wesleyscholl/konjo-cortex` → `"private": true`), and that
   `raw.githubusercontent.com/.../repo-kiban.md` returns `404` unauthenticated.
   So even the fired session's own `WebFetch` tool had no public fallback
   route to the file.

## Stop rule applied, and where it broke down

The brief's own method requires reading the fired session's actual transcript
before trusting a green run status — a session finishing "IDLE" proves it
produced *a* final answer, not that the answer is correct or even that it
found the file. This reporting session tried multiple ways to retrieve that
transcript verbatim: `ListAgents` (session not listed — routine-fired
sessions with the `routine:agent-minted` tag are not surfaced there),
`SendMessage` by session id and by session title (both `"not reachable"`),
`list_sessions` filtered to `mine: true` and unfiltered up to 30 results
(session not present in either), and `WebFetch` against the session's
`claude.ai/code` URL (out of scope per that tool's own stated exception list,
which covers only `claude.ai/code/artifact/{uuid}`, not session pages). **No
tool available to this reporting session could retrieve the fired session's
verbatim final message.** This is recorded as a gap in this environment's own
tooling, not papered over with a fabricated excerpt — the fired session
(`session_013TsakpgNVYDBg7VaC3iuSM`) remains open for a human with browser
access to `claude.ai/code` to read directly.

## Why this is reported as BLOCKED rather than guessed as PASS or FAIL

Regardless of what that specific session's text says, the precondition for a
meaningful PASS was not met: with no account-level GitHub connector, no MCP
connectors passed to the trigger, and a private target repo with no public
fallback, a correct citation from that session would be difficult to
distinguish from a lucky guess or a hallucinated id (`4d26cb337b09` is a
12-hex string; a model asked to "cite the decision id" under a `WebFetch`
404 has a real incentive to fabricate one rather than report failure). A
missing or wrong citation would confirm the negative straightforwardly; a
correct one would need the actual transcript to trust, which is exactly what
could not be retrieved. Declaring PASS on session-status alone is the precise
failure mode the brief's stop rule exists to prevent.

## What is confirmed fixed, and what is not

**Fixed:** `konjo-cortex` exists, `repo-kiban.md` is a real, faithful Cortex
projection (verified locally: id `4d26cb337b09` present, active, correct
decision text, matches `LEDGER.md`'s real history) and is live on `main`.

**Not fixed, and not attempted here (needs a human with claude.ai Settings
access):**
1. Register a GitHub connector under Settings → Connectors and grant it
   access to `wesleyscholl/konjo-cortex`.
2. Re-run KT-3 either passing `connectors: ["GitHub"]` to `create_trigger`
   once that connector exists, or via a routine created directly from the
   claude.ai Routines UI (which may default differently than
   `create_new_session_on_fire` fired via this MCP tool).
3. Alternatively, if "zero setup, any Claude Code session" is the literal bar
   KT-3 needs to clear, `konjo-cortex` cannot stay private and connector-gated
   -- that is a real design tension between "personal account, private" (this
   sprint's stated choice) and "a routine with no local `~/.konjo` can always
   reach it" (KT-3's claim), not something this run's tooling gap can resolve
   on its own.

## Command / mechanism reference

```
# Local proof the projection itself is correct (not what KT-3 tests, but
# what it depends on):
rm -rf /tmp/k1_state && mkdir -p /tmp/k1_state
python3 evals/fixtures/ledger/gen_k1_corpus.py   # writes ledger/decisions.jsonl
python3 -c "
from ledger.engine import Ledger
from lib import cortex
print('4d26cb337b09' in cortex.render_scope(Ledger('ledger/decisions.jsonl'), 'repo:kiban'))
"
# -> True
```
