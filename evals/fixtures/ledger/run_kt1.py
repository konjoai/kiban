#!/usr/bin/env python3
"""KT-1: does semantic retrieval beat konjo-decision search on real recall questions?

Runs three retrievers over the same 30-topic corpus (evals/fixtures/ledger/
k1_corpus.jsonl, evals/fixtures/ledger/kt1_questions.jsonl) and scores top-3 hit rate:

  1. konjo-decision search  -- ledger.search(), the shipped keyword baseline,
     invoked with a realistic short keyword query per question.
  2. rg over projected markdown -- ripgrep-style keyword scan over the folded Cortex
     page, blocks ranked by keyword-hit count, same keyword query as (1).
  3. embedding retriever -- fastembed (BAAI/bge-small-en-v1.5) dense embeddings,
     cosine similarity, given the full natural-language question (its native
     interface -- nobody types keyword fragments into a semantic search box).

Stop rule (Phase 0 brief): embeddings must beat the better keyword baseline by
>= 20 points absolute top-3 hit rate, or no index is ever built.

Usage: KONJO_STATE_DIR=<fixture dir with k1_corpus.jsonl loaded> python3 run_kt1.py
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

_KIBAN_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
if str(_KIBAN_ROOT) not in sys.path:
    sys.path.insert(0, str(_KIBAN_ROOT))

from ledger.engine import Ledger  # noqa: E402
from lib import cortex  # noqa: E402

HERE = pathlib.Path(__file__).parent
SCOPE = "repo:kiban"


def load_questions() -> list[dict]:
    with open(HERE / "kt1_questions.jsonl") as f:
        return [json.loads(line) for line in f]


def retriever_search(ledger: Ledger, keywords: str, k: int = 3) -> list[str]:
    """konjo-decision search, --all (inactive included, matching real recall usage)."""
    results = ledger.search(keywords, scope=SCOPE)
    return [d.id for d in results[:k]]


_WORD = re.compile(r"[a-z0-9]+")


def _tokenize(s: str) -> set[str]:
    return set(_WORD.findall(s.lower()))


def retriever_rg(blocks: list[tuple[str, str]], keywords: str, k: int = 3) -> list[str]:
    """rg-style: rank projected-markdown decision blocks by keyword-token hit count."""
    terms = _tokenize(keywords)
    scored = []
    for did, text in blocks:
        text_terms = _tokenize(text)
        hits = len(terms & text_terms)
        if hits > 0:
            scored.append((hits, did))
    scored.sort(key=lambda x: (-x[0]))
    return [did for _, did in scored[:k]]


def retriever_embedding(blocks: list[tuple[str, str]], question: str, k: int = 3) -> list[str]:
    import numpy as np
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    ids = [b[0] for b in blocks]
    texts = [b[1] for b in blocks]
    doc_vecs = np.array(list(model.embed(texts)))
    q_vec = np.array(list(model.embed([question])))[0]
    sims = doc_vecs @ q_vec / (
        np.linalg.norm(doc_vecs, axis=1) * np.linalg.norm(q_vec) + 1e-9
    )
    ranked = sorted(zip(ids, sims, strict=True), key=lambda x: -x[1])
    return [did for did, _ in ranked[:k]]


def main() -> None:
    ledger = Ledger("ledger/decisions.jsonl")
    questions = load_questions()

    all_decisions = {d.id: d for d in ledger._fold() if d.scope == SCOPE}
    blocks = [(did, f"{d.decision}\n{d.rationale}") for did, d in all_decisions.items()]

    page = cortex.render_scope(ledger, SCOPE)
    (HERE / "kt1_projected_scope.md").write_text(page)

    print("Loading embedding model (BAAI/bge-small-en-v1.5, one-time download)...")
    import numpy as np
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    ids = [b[0] for b in blocks]
    texts = [b[1] for b in blocks]
    doc_vecs = np.array(list(model.embed(texts)))
    q_texts = [q["question"] for q in questions]
    q_vecs = np.array(list(model.embed(q_texts)))

    results: dict[str, list[bool]] = {"search": [], "rg": [], "embedding": []}
    rows = []
    for i, q in enumerate(questions):
        answer = q["answer_id"]
        kw = q["keywords"]

        top3_search = retriever_search(ledger, kw)
        top3_rg = retriever_rg(blocks, kw)

        q_vec = q_vecs[i]
        sims = doc_vecs @ q_vec / (
            np.linalg.norm(doc_vecs, axis=1) * np.linalg.norm(q_vec) + 1e-9
        )
        ranked = sorted(zip(ids, sims, strict=True), key=lambda x: -x[1])
        top3_emb = [did for did, _ in ranked[:3]]

        hit_search = answer in top3_search
        hit_rg = answer in top3_rg
        hit_emb = answer in top3_emb

        results["search"].append(hit_search)
        results["rg"].append(hit_rg)
        results["embedding"].append(hit_emb)
        rows.append((q["n"], hit_search, hit_rg, hit_emb))

    n = len(questions)
    rate_search = 100 * sum(results["search"]) / n
    rate_rg = 100 * sum(results["rg"]) / n
    rate_emb = 100 * sum(results["embedding"]) / n

    def _mark(hit: bool) -> str:
        return "HIT" if hit else "."

    print(f"\n{'q#':>3}  {'search':>7}  {'rg':>7}  {'embed':>7}")
    for n_, hs, hr, he in rows:
        print(f"{n_:>3}  {_mark(hs):>7}  {_mark(hr):>7}  {_mark(he):>7}")

    print(f"\ntop-3 hit rate over {n} questions:")
    print(f"  konjo-decision search : {rate_search:.1f}%")
    print(f"  rg over projected md  : {rate_rg:.1f}%")
    print(f"  embedding (bge-small) : {rate_emb:.1f}%")

    best_keyword = max(rate_search, rate_rg)
    delta = rate_emb - best_keyword
    verdict = (
        "PASS -- index justified" if delta >= 20.0 else "FAIL -- stop rule applies, no index built"
    )
    print(f"\nbest keyword baseline : {best_keyword:.1f}%")
    print(f"embedding delta       : {delta:+.1f} points")
    print(f"threshold (>= +20.0)  : {verdict}")


if __name__ == "__main__":
    main()
