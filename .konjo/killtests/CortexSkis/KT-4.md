# KT-4 — Portable skill viability (gates Phase 3)

**Verdict: PASS.** A CLI-free `recall` variant answers real recall questions
correctly with zero local binaries and no `~/.konjo` -- confirmed both as a
subprocess-level no-CLI proof and as a 30-question sweep against the same KT-1
corpus. `konjo-skis` gets created (staged this sprint; see Phase 3 below for what
actually shipped and what didn't).

## Command

```
env -i PATH=/usr/local/bin:/usr/bin:/bin HOME=/nonexistent_home \
  python3 evals/fixtures/ledger/kt4_portable_recall.py \
  evals/fixtures/ledger/kt1_projected_scope.md \
  "If a review specialist times out or crashes mid-PR, does the merge still go green?"

python3 evals/fixtures/ledger/run_kt4.py   # full 30-question sweep
```

## Part 1: the literal no-CLI proof

`evals/fixtures/ledger/kt4_portable_recall.py` imports nothing from `ledger` or
`lib` -- standard library only. Run in a scrubbed subprocess: `PATH` stripped to
`/usr/local/bin:/usr/bin:/bin` (no kiban `bin/` on it, confirmed `which
konjo-decision` exits 1), `HOME=/nonexistent_home` (confirmed `~/.konjo` does not
exist). Given only the projected markdown page, it answered correctly, citing
`projected-at` in every response (risk #4's stated-freshness requirement):

```
[cortex as of 2026-08-06T12:00:00Z] Make review incompleteness block the merge
instead of passing silently. (`48aa4a0b7344`)
...
```

Correct decision id, no CLI, no state dir. **This is KT-4's literal threshold,
and it is met.**

## Part 2: 30-question sweep, and two real bugs found building it

`run_kt4.py` runs the full KT-1 question set through the same script.
**25/30 (83.3%) correct.** Two real retrieval bugs were found and fixed live
while building this, both worth recording:

1. **Naive token-overlap ties toward a superseded block.** A superseded and its
   active replacement share most of their vocabulary (same topic); on a tied
   hit count the predecessor (rendered first on the page) won by default.
   Fixed with an active-first two-pass search (search active blocks first, fall
   back to the full set only if nothing active matches) -- not just a
   tiebreak, since bug 2 showed ties weren't even the whole problem.
2. **A superseded block can outscore its active replacement outright, not just
   tie.** `review_diff defaults to runs=1` literally contains "per PR"; its
   real replacement ("Default review_diff to runs=3 instead of runs=1")
   doesn't repeat that phrase, so raw overlap favored the stale block 5-to-2
   even after fix 1's tiebreak. The two-pass fix (active set searched
   exclusively unless empty) resolves this case too, since the replacement's 2
   hits are the only candidate in pass 1.

**Remaining 5 misses** (Q6, Q24, Q28, Q29, Q30) share one shape: each question's
vocabulary overlaps more strongly with a *different* active decision on a
related topic than with its own correct (sometimes redacted, no active
sibling) answer -- e.g. Q29/Q30 ask about now-redacted topics whose vocabulary
also appears in a live, unrelated active decision, so the active-first fallback
never reaches the correct redacted block. This is naive keyword-overlap's real
ceiling, not a bug: it has no notion of topical relevance beyond raw word
counts.

## Design conclusion carried into Phase 3

The standalone script is a convenience fallback for non-LLM/scripted contexts,
**not the mechanism `konjo-skis/recall`'s `SKILL.md` should rely on.** The
skill's real mechanism is Claude reading the projected page directly (a few KB
of markdown, well inside any surface's context) and reasoning over it --
exactly what a semantic retriever would buy you, at zero marginal cost, which
is the same conclusion KT-1 reached from the other direction (embeddings lose
to keyword search on this corpus shape; here, an LLM reading the whole small
page beats a naive keyword script on the cases the script gets wrong). The
script ships in `evals/fixtures/ledger/` as what proved the no-CLI claim, not
as `konjo-skis/recall`'s runtime path.
