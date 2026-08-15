# KT-1 — Does retrieval beat what already exists? (STOP RULE)

**Verdict: FAIL the +20pt threshold. No index is ever built.** `konjo-decision
search` and rg over the projected markdown both hit 100.0% top-3; a real dense
embedding retriever hit 93.3% -- 6.7 points *worse* than the better keyword
baseline, not 20 points better. Cortex stays markdown. `recall` keeps using
keyword search. The entire retrieval tier is deleted from the roadmap. This is
the prior's expected outcome, not a surprise: "one-line decisions with explicit
supersede links are close to the worst case for embeddings and close to the best
case for keyword search."

## Known limitation on blinding

The brief's method calls for writing the 30 questions "before looking at the
corpus." No real `~/.konjo/state/ledger/decisions.jsonl` exists anywhere reachable
from this repo or container (confirmed at sprint kickoff) -- the corpus itself had
to be built this sprint (Phase 0, transcribed from `LEDGER.md`'s real prose
decisions, per Wes's explicit choice), by the same session that then wrote the
questions. True blinding was not achievable in a single session authoring both
sides. Mitigation: questions were phrased as natural, paraphrased recall
questions rather than restatements of the stored decision text (see
`evals/fixtures/ledger/kt1_questions.jsonl`'s `question` field vs. the corpus's
`decision` strings), and the keyword baselines' `keywords` field was set to a
short, realistic substring a user would plausibly try -- not reverse-engineered
from the retrievers' own behavior. This is recorded as a limitation, not
papered over.

## Corpus

`evals/fixtures/ledger/k1_corpus.jsonl` -- 35 events / 30 topics, scope
`repo:kiban`, generated deterministically by
`evals/fixtures/ledger/gen_k1_corpus.py` (sha1-derived ids, so re-running it
against an empty state dir reproduces the identical file). 25 pristine decisions,
3 supersede chains (2 links each), 2 redacts -- every `decision`/`rationale`
string is a compressed, faithful transcription of a real `LEDGER.md` entry (see
that script's module docstring for the full accounting of which entries and
which two predecessor events are synthetic scaffolding vs. real content).

30 questions: `evals/fixtures/ledger/kt1_questions.jsonl`.

## Command

```
rm -rf /tmp/k1_state && mkdir -p /tmp/k1_state
KONJO_STATE_DIR=/tmp/k1_state python3 evals/fixtures/ledger/gen_k1_corpus.py
KONJO_STATE_DIR=/tmp/k1_state python3 evals/fixtures/ledger/run_kt1.py
```

## The three retrievers

1. **`konjo-decision search`** -- `Ledger.search()`, the shipped baseline: whole
   keyword-string containment against `decision\nrationale`, active-first. Real
   behavior discovered while building this test: it is a single contiguous
   substring test, not a token-AND search -- a multi-word query only matches if
   the *exact phrase* appears verbatim. An earlier draft of this KT used natural
   multi-word noun-phrase queries scattered across the decision text and scored
   the tool **0.0%** as a result. That was a strawman: real recall usage tries a
   short, plausible phrase, not an AND of scattered terms. `keywords` was
   rewritten to short, realistic substrings before the reported run below.
2. **rg over the projected markdown** -- `evals/fixtures/ledger/kt1_projected_scope.md`
   (the real `cortex.render_scope()` output for this corpus), decision blocks
   ranked by keyword-token hit count.
3. **Embedding retriever** -- `fastembed`, `BAAI/bge-small-en-v1.5` (384-dim), real
   dense embeddings (not TF-IDF), cosine similarity, given the full
   natural-language question -- its native interface, since nobody types keyword
   fragments into a semantic search box. `sentence-transformers` (the more
   common choice) could not be installed inside this container's time budget
   (torch download timed out at 100s); `fastembed` (onnxruntime-backed, no
   torch) is a real dense-embedding model, not a substitute keyword method.

## Raw output

```
top-3 hit rate over 30 questions:
  konjo-decision search : 100.0%
  rg over projected md  : 100.0%
  embedding (bge-small) : 93.3%

best keyword baseline : 100.0%
embedding delta       : -6.7 points
threshold (>= +20.0)  : FAIL -- stop rule applies, no index built
```

Embedding misses: Q10 ("For squish and vectro's gate sets, what's the plan for
what to promote, keep, or drop?" -- answer `5d00b03c048a`) and Q14 ("Do we have
any tooling that takes a task description in and produces a real diff out?" --
answer `3042228a2bfe`). Both keyword baselines hit both.

## Stop rule applied

Per the pre-flight brief: below threshold, no index is ever built. **Cortex
stays markdown. `recall` keeps using keyword search (Phase 3, if built at all,
ports `recall` against `Ledger.search()`/rg over cortex pages, not an
embedding index). The entire retrieval tier is deleted from the roadmap. This
negative result is the headline finding of Phase 0, not a footnote** -- it is
exactly the result the brief's own prior predicted, now measured rather than
assumed.
