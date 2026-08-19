# KT-7 — Does a fresh cloud session with `source_url` reach the private Cortex page?

**Status at pre-registration time: NOT YET RUN.** This section was written and
committed *before* the session was spawned, so the questions and their expected
answers could not be rescoped after seeing what came back. Same discipline
Sprint K1's Phase 3 applied to KT-4. The verdict section below is appended
after the run, not edited into this one.

## Why a new kill-test instead of re-running KT-3

KT-3 is BLOCKED and stays BLOCKED: it tests the *bare routine* path
(`create_trigger` + `create_new_session_on_fire`), which gets zero `mcp__`
tools and therefore has no route to a private repo. That blocker is
account-level and manual (claude.ai Settings -> Connectors) and is not fixed
as of this run -- re-confirmed via `ListConnectors` at the start of this
session: Canva, Gmail, Google Calendar, Google Drive, Mermaid Chart
(authless, disabled), Superhuman Docs (disabled), Trello. **No GitHub
connector.** Re-running KT-3's exact mechanism would reproduce KT-3's exact
result, which `NEXT_SESSION_PROMPT.md` point 3 explicitly warns against.

`NEXT_SESSION_PROMPT.md`'s "Open work" item 2 names the alternative by name:
test `create_session`'s `source_url` parameter -- "a fresh session with the
repo already checked out, not a bare routine" -- as a **narrower but real**
reachability proof. KT-7 is that test. It is deliberately a weaker claim than
KT-3's and does not substitute for it (see "What a PASS here does not mean").

## The two things that must both hold

1. **Reach.** A session that is not this one, holding no local `~/.konjo` and
   no pre-existing clone, can obtain the contents of `repo-kiban.md` from the
   private `wesleyscholl/konjo-cortex`.
2. **Verifiability.** This session can read that session's answer *verbatim*,
   from an artifact it cannot itself author. This is the half KT-3 could not
   satisfy: no tool available to the firing session (`ListAgents`,
   `SendMessage`, `list_sessions`, `WebFetch`) could retrieve a fired
   session's transcript, and `list_events` is not in this session's toolset
   either (checked via `ToolSearch`, this run). KT-7 routes around that
   instead of re-hitting it: the spawned session **pushes its answer to a git
   branch**, and this session reads that branch back through the GitHub API.
   A commit is verbatim, timestamped, and attributable in a way a summarized
   status field is not.

## Contamination control

The answer to every question below also exists inside the `kiban` repo
(`evals/fixtures/ledger/k1_corpus.jsonl`, `kt1_questions.jsonl`, and KT-3.md
/ KT-5.md's own prose all contain `4d26cb337b09` and its decision text). A
spawned session holding `kiban` could therefore answer without ever reaching
`konjo-cortex`, and the run would prove nothing.

**Therefore the spawned session is given `wesleyscholl/konjo-cortex` as its
only source.** Questions Q1/Q2/Q4 below are additionally chosen so that their
answers appear *nowhere in kiban at all* -- they are properties of the
projected page's own structure (its frontmatter stamp, its event count, its
redaction set), not of the corpus kiban generates. Q3 is retained even though
it does leak into kiban, because it is the question KT-3 posed and keeping it
makes the two runs comparable.

## Pre-registered questions and expected answers

Ids are `sha1(decision_text)[:12]` (`evals/fixtures/ledger/gen_k1_corpus.py`),
so a 12-hex id is not guessable and a wrong one is unambiguously wrong.

| # | Question | Expected answer | In kiban? |
|---|----------|-----------------|-----------|
| Q1 | The exact `projected-at` value in the frontmatter | `2026-08-06T12:00:00Z` | no |
| Q2 | How many ids are listed under `source-events` | `33` | no |
| Q3 | Which decision id supersedes `d1f4131159dc`, and what does it say | `4d26cb337b09` -- "Default review_diff to runs=3 instead of runs=1." | **yes** |
| Q4 | The ids of every entry marked `(REDACTED)` | `b75046fe0b29` and `9552b0a690c4` (order-independent) | no |

Verified present in the pushed file at pre-registration time by reading the
local clone of `konjo-cortex` at `8aef317`.

## Grading rule, fixed in advance

- **PASS** requires all four correct, *and* the answer retrieved from the
  pushed branch rather than from any session-status field.
- **FAIL** is any wrong or missing answer with the branch successfully
  pushed -- that is a real negative result about reach, and gets reported as
  one.
- **BLOCKED** is reserved for the case where the mechanism never got far
  enough to answer: the session cannot clone the private repo, or cannot
  push, so no artifact exists to grade. A BLOCKED verdict names which of the
  two halves failed.
- Q3 alone passing while Q1/Q2/Q4 fail is **FAIL, and specifically evidence
  of prior-knowledge contamination**, not a partial pass -- Q3 is the only
  answer reachable without the file.

## Stop rule

Inherited verbatim from KT-3, which is where the previous run broke down: a
session finishing `IDLE` proves it produced *an* answer, not a correct one.
**No verdict is written from session status alone.** If the branch is not
readable from this session, the verdict is BLOCKED and says so -- no excerpt
is reconstructed, paraphrased, or assumed.

## What a PASS here does not mean

- It does **not** unblock KT-3. Bare routines still get zero `mcp__` tools.
- It does **not** mean the content is real. Everything in `repo-kiban.md` is
  still Sprint K1's fixture corpus (P-0, checked fresh in K1 and K2 alike).
- It does **not** remove the connector work. `source_url` proves a session
  *with a repo handed to it* can read the file; it says nothing about a
  surface that must go find the repo itself.
