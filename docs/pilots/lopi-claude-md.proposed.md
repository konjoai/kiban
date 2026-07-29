---
decays: intent
verified-against: 05c044f
verified-date: 2026-07-29
---

# Proposed `lopi/CLAUDE.md`, converted to the Phase 13 section contract

**Not applied.** This session's access to `konjoai/lopi` is read-only (added for research
and reconciliation, not push). Applying this is a `konjoai/lopi` PR, not a `kiban` one --
this file is the prepared patch content plus the reasoning, for whoever opens that PR
(this sprint's `NEXT_SESSION_PROMPT.md` names it as the next concrete task).

Converted against `lopi/CLAUDE.md` at `b93e68f` (main) and the new
`templates/repo-CLAUDE.md` section contract (`## Org rules`, `## Stack`, `## Commands`,
`## Invariants`, `## Repo map`, `## Repo-specific rules`, in that order).

## What changed and why

- **Title/description**: kept, folded under "Repo-specific rules" (it is a repo fact, not
  a contract section by itself).
- **Stack**, **Commands**, **Crate Map** (renamed **Repo map**): kept verbatim -- Phase 0's
  own instruction ("the crate map, the stack line, and the commands stay").
- **Critical Constraints → Invariants**: every bullet now names its enforcement or says
  `ADVISORY`. Running each against lopi's real `konjo-gate.yml` (read this sprint) and
  the new `profiles/lopi.yml`:
  - "No `unwrap()`/`expect()` outside tests" -- **enforced**: `repo:clippy` already runs
    `-D clippy::unwrap_used -D clippy::expect_used` in lopi's `static` job (confirmed by
    reading the workflow). The only constraint in the original six with a real mechanical
    check behind it.
  - "No blocking I/O on async paths" -- **ADVISORY**. No gate in lopi's CI or kiban's gate
    set checks this today.
  - "No silent failures -- log via `tracing::warn!`" -- **ADVISORY**, same reason.
  - "`cargo build` must stay green" -- **ADVISORY** in this file's own terms (it's a
    workflow property, not a rule this repo's gates assert about a diff); the repo's CI
    build step is the actual check, referenced here for honesty rather than invented as a
    named gate.
  - "Stay inside `crates/` and `src/`" -- **ADVISORY**. No gate.
  - "Tokio is the only async runtime" -- **ADVISORY**. No gate.

  This is the concrete, load-bearing finding from applying the contract to a real file:
  **five of lopi's six "Critical Constraints" have no mechanical enforcement today.**
  That is exactly the gap `gate_claude_contract` exists to surface -- not a defect in lopi
  (nothing here claims to be a gate), but a defect in the *original* framing, which called
  these "Critical Constraints" with no distinction between "checked every PR" and "trust
  the agent to remember." Converting to explicit `ADVISORY` markers doesn't add
  enforcement; it stops the file from implying enforcement that isn't there.
- **Quality Framework / Additional Hard Rules → deleted, replaced by a pointer**: this was
  a second, hand-maintained copy of the same thresholds now declared once in
  `.konjo/profile.yml`'s `contract_gates` (see `profiles/lopi.yml` and
  `LEDGER.md`'s `Lopi-Gate-Reconciliation-1`). Two copies of the same threshold is the DRY
  violation Phase 0 exists to close; one pointer replaces ten lines.
- **Live Dashboard, Skills**: kept verbatim under "Repo-specific rules" -- pure lopi UX
  instructions, not contract material.
- **Org rules / Pinning**: added per the template -- the two sections that were entirely
  absent before (lopi imported nothing from kiban's session plane; this is the Phase 0
  root-cause fix).

## Proposed file

```markdown
# lopi

High-performance Rust agent orchestrator for Claude Code -- runs Claude agents concurrently in git-isolated branches with retry loops, SQLite memory, TUI+web dashboard, and Telegram/WhatsApp remote control.

## Org rules

@~/.konjo/kiban/plugins/konjo/skills/konjo/SKILL.md

The org ethos applies here: ship over optimize, kill-test first, statistical rigor,
honest negative results, evidence first, token-efficient context.

Editorial rules: no em dashes, no AI-tell vocabulary. The prose lint enforces it; run
`konjo-prose` on docs before pushing.

Log durable decisions with `konjo-decision decide` at `repo:lopi` scope. Search with
`konjo-decision search` before reopening a settled call.

When you catch a mistake worth not repeating, invoke `correct`: it records a learning with
`konjo-learn` and proposes the smallest durable fix. A learning must name where its rule
lives (a CLAUDE.md line, a prose-lint word, a lane, or a gate), or it is refused.

Build the Konjo way: the `craft` skill carries the four behaviors (think before coding,
simplicity first, surgical changes, goal-driven execution) plus the verify-loop and the
pre-implementation trust-boundary contract. `verify_cmd` is declared in
`.konjo/profile.yml`.

## Stack
Rust 2021 · tokio · axum · ratatui · sqlx/SQLite · teloxide · git2 · clap

## Commands
```bash
cargo build                    # build workspace (also installs git hooks via cargo-husky)
cargo test --workspace         # run all crate tests (the standard runner -- what CI + hooks use)
cargo nextest run              # optional faster runner; install first: cargo install cargo-nextest
cargo clippy -- -D warnings    # lint
cargo llvm-cov nextest         # tests + coverage report (needs cargo-nextest + cargo-llvm-cov)
cargo audit                    # security advisory check
cargo deny check               # license + advisory + bans
cargo run -- run --goal "fix foo" --repo .  # run a task
cargo run -- sail              # web dashboard on :3000
scripts/start-dashboard.sh     # same, but idempotent -- checks /api/health first, no-ops if already up
cargo run -- watch             # TUI dashboard
bash .konjo/scripts/install-hooks.sh        # install pre-commit hooks
```

## Invariants
- No `unwrap()`/`expect()` outside tests (enforced: `repo:clippy` -- `-D clippy::unwrap_used -D clippy::expect_used`)
- No blocking I/O on async paths -- use `spawn_blocking` for synchronous ops (ADVISORY)
- No silent failures -- log via `tracing::warn!` if a fallback swallows an error (ADVISORY)
- `cargo build` must stay green -- fix before doing anything else (ADVISORY; CI build step)
- Stay inside `crates/` and `src/` -- never touch root `Cargo.lock` deliberately (ADVISORY)
- Tokio is the only async runtime -- never introduce another (ADVISORY)

Gate thresholds (coverage, complexity, dead code, docs, DRY, file size) are declared once
in `.konjo/profile.yml`, not duplicated here -- see `contract_gates` there for the current
list and `konjo-gates` for what's actually enforced today vs. kept repo-native.

## Repo map
| Crate | Role |
|-------|------|
| `lopi-core` | Shared types: `Task`, `AgentRun`, `Score`, `LopiConfig` |
| `lopi-context` | KV cache eviction layer -- owns all message history + eviction policies |
| `lopi-git` | `GitManager` (branch/rollback/PR) + `DiffChecker` |
| `lopi-agent` | Plan → Implement → Test → Score → Retry → PR |
| `lopi-memory` | SQLite via sqlx |
| `lopi-orchestrator` | `AgentPool` + priority `TaskQueue` |
| `lopi-ui` | ratatui dashboard + axum web/JSON API |
| `lopi-remote` | teloxide Telegram bot + Twilio WhatsApp |
| `lopi-webhook` | GitHub CI-failure → task injection |
| `lopi-toon` | TOON (Token-Oriented Object Notation) |
| `lopi-ratelimit` | Rate limiting primitives |

## Repo-specific rules

### Live Dashboard (Browser Pane)
When asked to check on running stacks/tasks ("what's lopi running right now", "show me the stacks"), in a Claude Code Desktop session with a Browser pane:
1. Run `scripts/start-dashboard.sh --repo <path>` -- it checks `/api/health` on the target port (from `lopi.toml`, default `3000`) and no-ops with an "already running" message if `sail` is up, so it's always safe to run instead of hand-checking with `lsof`/`ps`.
2. If nothing was running, the script starts `lopi sail` backgrounded and waits until it's healthy before returning.
3. Open the dashboard with the Browser pane's `preview_start` tool using `{url: "http://localhost:<port>"}`. This step is required every time -- the Browser pane does **not** auto-detect an already-running `lopi sail` process the way it detects a typical `npm run dev` server, since it's a Rust binary outside the usual JS dev-server patterns.

### Skills
See `.claude/skills/` -- auto-loaded when relevant. `konjo-ship` now comes from the global
kiban clone; the local `.claude/skills/konjo-ship/` copy should be removed once this
profile lands, so it stops shadowing the global one.

## Pinning

This repo pins a kiban ref in `.konjo/kiban.ref` (currently `v1.4.0`; bump to this
sprint's release once it ships) and `KIBAN_REF` in CI.
```

## Follow-up this PR should also do (not CLAUDE.md content, but adjacent)

1. Remove `/workspace/lopi/.claude/skills/konjo-ship/` (shadows the global copy per
   kiban's own `NEXT_SESSION_PROMPT.md`, pre-Phase-13 note).
2. Wire `.konjo/profile.yml` = this session's `profiles/lopi.yml` content (copy, don't
   symlink -- the established convention per `profiles/vectro.yml`/`profiles/squish.yml`
   is that the profile is authored in kiban and *placed* in the consuming repo by that
   repo's own maintainers/session).
3. Add a `konjo-gates` CI job to `.github/workflows/konjo-gate.yml` (or a sibling
   workflow) invoking `konjo-gates --profile .konjo/profile.yml`, alongside the existing
   G0-G5 jobs -- Phase 0 keeps every one of them, per `LEDGER.md`'s
   `Lopi-Gate-Reconciliation-1`, none are deleted.
