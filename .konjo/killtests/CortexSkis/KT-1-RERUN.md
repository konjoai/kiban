# KT-1 re-run (real corpus) — DEFERRED, not run as a graded kill-test

**Verdict: DEFERRED. n = 20 active decisions.** The re-run KT-1 was queued for
across three sprints is not run here, and the reason is not scheduling: as
written, the test cannot produce a reversal on this corpus. The `>= 20` point
absolute threshold is arithmetically unreachable against a keyword baseline
that saturates, and this content class saturates it. `Cortex-Projection-1`'s
no-index decision therefore stands unchanged and unre-litigated, on the
original K1 evidence rather than on a weak second measurement.

## Why this is a deferral and not a result

Three reasons, strongest first.

**1. The threshold is arithmetically unreachable.** KT-1's rule is "embeddings
must show `>= 20` points absolute improvement over the better keyword
baseline." K1 measured that baseline at **100.0%** (`konjo-decision search`
and rg over the projection, both 30/30). A 20-point absolute improvement over
100% requires a retriever scoring 120%. The threshold can only ever be met
when the keyword baseline sits **below 80%**, and nothing in this corpus's
construction pushes it there: every decision carries a unique rare identifier
(`github_installations`, `INT3`, `TaskSource::Telegram`, `squish-ai`,
`fastembed`, `gate_claude_contract`), which is close to the best case for
keyword search and, as K1's own prior stated up front, close to the worst case
for embeddings. This holds on K1's number alone, independent of anything
measured this sprint.

**2. n is smaller than the test being re-run.** The real seeded corpus is 24
events / **20 active decisions** across 4 scopes. K1's fixture corpus was 35
events / 30 topics. A re-run with a third fewer retrievable topics than the
original cannot be more decisive than the original; it can only be noisier.
The point of the re-run was "does this hold on real content" — real, here,
also means smaller.

**3. Pre-registration is impossible in this sprint's own phase order.** The
brief requires the 30 questions be written "before looking at the projected
pages" (Phase 3), and separately requires reading those pages as a human
(Phase 2, whose stated value is that no test covers it). One session cannot
both read the pages and not have read them. Beyond that, the corpus author and
the question author are again the same session — and worse than K1, which
transcribed pre-existing `LEDGER.md` prose, this sprint's entries were composed
hours before the questions would have been. K1 already recorded that limitation
honestly; repeating it with less separation and calling the output a graded
re-run would be a downgrade in method, not a confirmation.

## Headroom probe (not a graded run, and not evidence for a verdict)

To check reason 1 against the real corpus rather than only against K1's number,
a deliberately-labelled probe measured **only** the keyword baseline's top-3 hit
rate. Embeddings were not scored and no verdict was derived from it.

- 15 natural recall questions, one short realistic keyword each
- `konjo-decision search` top-3: **15/15 = 100.0%**
- maximum possible embedding improvement: **0.0 points** (threshold: 20.0)

**This probe is contaminated and is reported as such.** The same session authored
the corpus, the questions, and the keywords, so a 100% keyword score is partly an
artifact of choosing keywords known to be distinctive. It is included because it
is consistent with K1's independent 100.0%, not because it independently
establishes anything. The structural argument in reason 1 does not rest on it.

## Absence-of-evidence check

The claim "embeddings cannot win here" rests on the keyword baseline scoring at
or near 100%, which is a *positive* measurement (K1's 30/30), not a tool
returning nothing. The one place absence could mislead: `fastembed` is **not
installed on this machine** (`ModuleNotFoundError`), so no embedding number was
produced this sprint. That absence is **not** used as evidence for the verdict —
the deferral would read identically if fastembed were installed and scored 100%,
because the threshold is unreachable regardless of the embedding score. Not
installing it is a consequence of the deferral, not a cause.

## Positive control

Does the harness detect a *miss* at all, or would it report 100% on anything?
The probe's scorer requires the target decision id to appear in the top 3 of
`konjo-decision search`'s own output; ids come from the folded stream, not from
the question file. Two questions returned multi-result top-3 lists (`private` →
3 results, `embedding` → 2, `github_installations` → 2), so the retriever is
genuinely ranking rather than returning a single trivially-correct row, and a
target ranked 4th or absent would score MISS. The scorer was not run against a
known-absent target this sprint, which is the honest limit of this control.

## What would make the re-run decisive

- **A corpus where keyword search stops saturating.** That is the natural
  consequence of P-0b capture: many decisions about the *same* subsystem,
  sharing vocabulary, where the distinguishing signal is semantic rather than a
  unique rare token. This corpus has 20 decisions and almost no vocabulary
  overlap between them.
- **A threshold that is reachable.** `>= 20` points absolute is unmeetable above
  an 80% baseline. An error-reduction framing (halve the top-3 miss rate) stays
  measurable at any baseline. Changing it is a real decision, not a tweak, and
  is not made here.
- **Blind question authorship** by a session that did not write the corpus.

## Stop rule honored

KT-1's own stop rule said: below threshold, the no-index decision is confirmed
and logged as such; above it, a reversal is a new sprint's work, not an in-flight
change. Neither branch is taken. No index was built, no embedding dependency was
added, and `Cortex-Projection-1` is not reopened.
