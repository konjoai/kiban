---
decays: reference
verified-against: 05c044f
verified-date: 2026-07-29
---

# CLAUDE.md (consuming-repo template)

Drop this into a consuming repo's root. It imports the org rules from the global kiban
clone (the session plane), then declares this repo's own facts in a fixed section order.
`gate_claude_contract` (Phase 13) checks this order and checks that every bullet under
`## Invariants` names the gate that enforces it -- an unenforced rule in always-on
context is a claim with no consumer, the same class as a rubric with no reader.

## Org rules

@~/.konjo/kiban/plugins/konjo/skills/konjo/SKILL.md

The org ethos applies here: ship over optimize, kill-test first, statistical rigor,
honest negative results, evidence first, token-efficient context.

Editorial rules: no em dashes, no AI-tell vocabulary. The prose lint enforces it; run
`konjo-prose` on docs before pushing.

Log durable decisions with `konjo-decision decide` at `repo:<this-repo>` scope. Search
with `konjo-decision search` before reopening a settled call.

When you catch a mistake worth not repeating, invoke `correct`: it records a learning with
`konjo-learn` and proposes the smallest durable fix. A learning must name where its rule
lives (a CLAUDE.md line, a prose-lint word, a lane, or a gate), or it is refused. Search
past learnings with `konjo-learn search` before repeating a class of mistake.

Build the Konjo way: the `craft` skill carries the four behaviors (think before coding,
simplicity first, surgical changes, goal-driven execution) plus the verify-loop. Declare a
`verify_cmd` in this repo's profile (the test/bench/browser path that proves a change works)
and run it before claiming done; a missing one is surfaced as a warning. Before writing code
that crosses a trust boundary, introduces a queue, spawns a process, or parses external
input, state the invariant it will satisfy and name the test that will prove it -- the
pre-implementation contract `craft` adds in Phase 13.

## Stack

<!-- decays: state
verified-against: <sha>
verified-date: <YYYY-MM-DD> -->
<!-- List languages/runtimes, e.g. "Rust 2021 · tokio · axum". Keep it to one line. -->

## Commands

<!-- decays: state
verified-against: <sha>
verified-date: <YYYY-MM-DD> -->
<!-- The build/test/lint/run commands a session needs. A fenced code block is fine. -->

## Invariants

<!-- Every bullet here names the gate that enforces it, or says ADVISORY explicitly.
     gate_claude_contract fails a bullet that does neither -- an unenforced "invariant"
     is a claim with no consumer. Example:
     - No unwrap()/expect() outside tests (enforced: repo:clippy -D clippy::unwrap_used)
     - No blocking I/O on async paths (ADVISORY -- no mechanical check yet) -->

## Repo map

<!-- decays: state
verified-against: <sha>
verified-date: <YYYY-MM-DD> -->
<!-- Crate/package/module map: what owns what. A table is fine. -->

## Repo-specific rules

<!-- Add rules unique to this repo below. Keep them plain. -->

## Pinning

This repo pins a kiban ref in `.konjo/kiban.ref` (and `KIBAN_REF` in CI). The session
plane checks out that ref on self-update instead of pulling main, so kiban changes land
here on a deliberate schedule. Check `.konjo/kiban.ref` for the currently pinned version
rather than trusting a version number written into this template, which goes stale the
moment the pin next moves.
