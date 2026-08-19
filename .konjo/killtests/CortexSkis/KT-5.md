# KT-5 — `konjo-skis/recall` closes the loop against the real, published `konjo-cortex` repo (fixture-scoped)

**Verdict: PASS, fixture-scoped.** Reading `konjo-skis/recall`'s own
`SKILL.md` procedure against the *actual pushed* `wesleyscholl/konjo-cortex`
repo (not a local fixture copy invented for this test) produces correct,
freshness-cited answers on a supersede chain and a redacted item. All
underlying content is Sprint K1's fixture corpus, folded and pushed to
`konjo-cortex` at `8aef317` — **not real Ledger usage data**. This test
proves the mechanism closes the loop end-to-end on real infrastructure; it
does not and cannot claim the content itself is real, per Sprint K2's own
P-0 finding (0 real events this sprint either) and its explicit "no
fabricated events to clear P-0" constraint.

## Why this test, and why now

KT-4 (`.konjo/killtests/CortexSkis/KT-4.md`, PASS) already established the
design conclusion: `recall`'s real mechanism is Claude reading the projected
page directly and reasoning over it, not a standalone keyword script — and
validated that conclusion against a *local* fixture file
(`evals/fixtures/ledger/kt1_projected_scope.md`). What KT-4 could not test,
because `konjo-cortex` did not exist yet when it ran, is whether the same
procedure works against the repo `konjo-skis/README.md`'s own "Prerequisite"
section names as the real target: a private GitHub repo, reached the way a
portable surface (phone, cloud routine, claude.ai account skill) would
actually reach it. That repo now exists and carries a real, pushed
`repo-kiban.md` (confirmed during this session's KT-3 work, `8aef317`,
decision `4d26cb337b09` present and active). KT-5 closes that gap.

## Method

1. Cloned `wesleyscholl/konjo-cortex` at `/workspace/konjo-cortex`
   (pre-existing clone from this session's KT-3 work; re-confirmed `git log`
   shows a single commit `8aef317`, remote is `wesleyscholl/konjo-cortex`).
2. Read `konjo-skis/recall/SKILL.md`'s "How to answer" procedure (4 steps:
   read the whole page, not just the first match; find Active for the
   topic; follow `chain:` to the current entry; check Retired before
   answering "no record"), and its "Every answer states its own freshness"
   requirement.
3. Followed that procedure by hand against `repo-kiban.md`'s actual
   rendered content — reading the file directly, the same access pattern a
   CLI-free surface has, not running any `konjo-*` binary or querying
   `~/.konjo` (this container has no local Ledger state loaded for this
   scope beyond what KT-3's session already confirmed is the K1 fixture, so
   nothing here could accidentally leak real data even if a binary were
   run).
4. Asked two real questions chosen from the page's actual content — one
   exercising the `chain:` traversal, one exercising the Retired-before-
   "no record" check — and recorded the answers verbatim below.

## Q&A (real content, `repo-kiban.md` lines as pushed to `main`)

**Q1 (chain):** "What's the current default review pass count for
`review_diff`, and did it change from something else?"

> As of the last Cortex refresh (**2026-08-06T12:00:00Z**), the active call
> is: **`review_diff` defaults to `runs=3`** (`4d26cb337b09`). It has a
> chain: it used to default to `runs=1` — one pass per PR (`d1f4131159dc`,
> superseded) — before being changed, because "one pass was not enough for
> the single most consequential judgment in the framework."

Correct: matches `repo-kiban.md:87-94` exactly, cites the `chain:
d1f4131159dc -> 4d26cb337b09` line, names the superseded predecessor rather
than only the current entry, and states the page's freshness stamp per the
skill's own "never answer without stating that date" requirement.

**Q2 (Retired, not "no record"):** "Did we ever try to mechanically classify
`raw_index_external_input` the same way as the other defect taxonomy
classes?"

> As of **2026-08-06T12:00:00Z**: this isn't an active decision, but it *is*
> real history — it's in Retired, redacted (`b75046fe0b29`). The attempt was
> made and then withdrawn: "confirmed genuinely not mechanically
> classifiable this way; recorded honestly as a gap rather than forced."

Correct: matches `repo-kiban.md:300-306`, does not answer "no record" (the
failure mode the skill's step 4 exists to prevent), and quotes the real
`reason` field rather than only noting that a redaction happened.

## What this does and doesn't prove

**Proves:** the `recall` procedure, followed against the real pushed
`konjo-cortex` repo rather than a local fixture path, correctly surfaces a
chain's current entry with its predecessor, correctly distinguishes a
redacted-but-real item from "no record," and correctly cites freshness —
closing the loop KT-4 left open (mechanism validated on a local fixture
file; not yet on the real repo target `konjo-skis/README.md` names).

**Does not prove:** that any of this content is real Ledger usage data. It
is the same K1 fixture corpus KT-1/KT-2/KT-4 have used throughout, per
Sprint K2's own P-0 finding (`LEDGER.md`'s `Sprint-K2-Close-The-Loop` entry:
0 real events, 0 scopes this sprint either). Every claim above is
fixture-scoped and should be read as "the mechanism works," not "kiban's
real architecture history now flows through this."

**Also not (re-)proven here, and not attempted:** the GitHub-connector /
routine-reachability question KT-3 (BLOCKED) already covers — this test read
the repo via a local clone, not via a Claude Code routine with zero `mcp__`
tools and no connector. KT-3's blocker is a distinct, unresolved
infrastructure gap; KT-5 tests the skill's reasoning procedure once content
is reachable by *some* means, not the reachability mechanism itself.

## Publishing status (unchanged)

Per `konjo-skis/README.md`'s own "Publishing" section: no MCP tool available
in this or any prior session can upload a skill to claude.ai's account-skill
surface. `konjo-skis/recall` and `konjo-skis/longrun` remain staged in this
repo, validated by KT-4 and now KT-5, awaiting a manual publish step by a
human with claude.ai Settings access.
