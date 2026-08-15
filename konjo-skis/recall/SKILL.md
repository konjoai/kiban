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

## How to answer

1. Read the Cortex page for the relevant scope (`org`, or `repo:<name>` for a
   specific consuming repo) from the `konjo-cortex` repo, via the GitHub
   connector or a local clone -- one markdown file per scope, e.g. `org.md`,
   `repo-lopi.md`.
2. Read the whole page, not just the first match. It is a few KB, well inside
   context -- reasoning over the full page beats keyword-matching a single
   line, especially across a supersede chain (`KT-1`, `KT-4`: a naive keyword
   script gets this wrong roughly 1 time in 6; reading the page and reasoning
   about which entry is current does not).
3. Find the **Active decisions** section for the topic. If a decision has a
   `chain:` line, the entry shown is the current one -- name it as current, and
   mention the chain only if the question is about history ("what did we used
   to do") rather than the present state.
4. If nothing in Active matches, check **Retired** before answering "no
   record" -- a redacted decision is still real history, just not the current
   call.

## Every answer states its own freshness

Cite the page's `projected-at` front-matter stamp in your answer, e.g. "as of
the last Cortex refresh (2026-08-06), the active call is...". **Never answer
from a Cortex page without stating that date.** A page can be stale between
refreshes (`lib/doc_staleness.py`'s `check_projection` gates this in CI, but a
gate that ran last week does not guarantee freshness today) -- a plausible
answer with no visible age is worse than a correct one, and worse still than
an answer that admits it might be behind.

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
