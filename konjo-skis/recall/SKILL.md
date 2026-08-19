---
name: recall
description: Read the Konjo Cortex (a markdown projection of the Konjo Ledger) before re-litigating a past call. Portable variant of kiban's recall skill -- no konjo-* CLI, no ~/.konjo, works on any surface (phone, cloud routine, claude.ai). Use before reopening a settled question.
---

# recall (portable)

Answer "did we already decide this?" from the Konjo Cortex -- a markdown
read model, not the live Ledger. This is the `konjo-skis` variant of kiban's
`recall` skill: same purpose, no CLI, no `~/.konjo`. If you have shell access to
a `konjo-*` binary and a real `~/.konjo/state`, use kiban's own `recall` skill
instead -- it searches the live stream, which this cannot.

This file and `plugins/konjo/skills/recall/SKILL.md` are a declared pair
(`konjo-skis/CONTRACT.yml`, enforced by `bin/konjo-skis-check`). Sections
marked `skis-contract:*` below must stay in sync with their counterpart
there -- edit both, or the gate fails the build.

## How to read the source

<!-- skis-contract:recall.read-path -->
Read the Cortex page for the relevant scope (`org`, or `repo:<name>` for a
specific consuming repo) from the `konjo-cortex` repo -- one markdown file
per scope, e.g. `org.md`, `repo-lopi.md`. Reachable from any surface holding
a GitHub repository integration with read access to `konjo-cortex` (a
private repo): a routine's own Repositories configuration, a session's
`source_url`, or a local clone. Not a claude.ai connector -- see
`LEDGER.md`'s `Skis-Contract-1` entry (Finding 1) if that distinction is
unfamiliar.
<!-- /skis-contract:recall.read-path -->

Read the whole page, not just the first match. It is a few KB, well inside
context -- reasoning over the full page beats keyword-matching a single
line, especially across a supersede chain (`KT-1`, `KT-4`: a naive keyword
script gets this wrong roughly 1 time in 6; reading the page and reasoning
about which entry is current does not).

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

A page can be stale between refreshes (`lib/doc_staleness.py`'s
`check_projection` gates this in CI, but a gate that ran last week does not
guarantee freshness today) -- a plausible answer with no visible age is
worse than a correct one, and worse still than an answer that admits it
might be behind.

## When to use

- Before proposing something that smells like a past call, on a surface with
  no local `konjo-*` install.
- When you need the rationale behind a current convention and only have read
  access (a phone, a cloud routine with no `~/.konjo`).

## What this cannot do

- **Cannot write.** No `decide`/`supersede`/`redact` from here -- writes are
  laptop-only, unchanged by this sprint (`.konjo/killtests/CortexSkis/`, the
  sprint's own stated non-goal). If the answer is "no, this hasn't been
  decided," say that plainly and suggest logging it once back on a surface
  with `konjo-decision`.
- **Cannot search learnings.** Cortex only projects the decision Ledger this
  sprint, not the learnings log (`ledger/schema.md`'s `learn` stream) -- a
  future sprint's scope, not this one's.
- **Can be stale.** Cortex refreshes when a sprint's post-flight runs
  `konjo-decision project`, not on every write. Between refreshes, a very
  recent laptop-side decision will not show up here yet.
