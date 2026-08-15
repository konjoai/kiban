#!/usr/bin/env python3
"""KT-4 candidate: a CLI-free `recall` core -- reads only a projected Cortex
markdown page. No import of `ledger`, `lib.jsonl_store`, or anything else that
would need `~/.konjo` or a `konjo-*` binary on PATH. Standard library only, so it
runs anywhere Python does: a phone-side tool runner, a cloud routine, this
container.

Every answer states the page's own `projected-at` stamp (KT-4's stated-freshness
requirement) -- a stale-but-plausible answer with no date on it is worse than one
that visibly names how old it is.
"""

from __future__ import annotations

import re
import sys

_WORD = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "is", "are", "did", "we", "do", "does", "to", "of", "and",
    "or", "for", "in", "on", "at", "it", "its", "this", "that", "was", "were",
    "still", "now", "right", "today", "if", "not", "with", "without", "any",
}


def _tokenize(s: str) -> set[str]:
    return {w for w in _WORD.findall(s.lower()) if w not in _STOPWORDS}


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm_block = text[4:end]
    body = text[end + 5 :]
    fm: dict[str, str] = {}
    for line in fm_block.splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, body


def split_blocks(body: str) -> list[tuple[str, str]]:
    """Return (heading, block_text) for every `### ` block in the page."""
    blocks: list[tuple[str, str]] = []
    parts = re.split(r"(?m)^### ", body)
    for part in parts[1:]:
        heading = part.splitlines()[0]
        blocks.append((heading, part))
    return blocks


def answer(page_text: str, question: str) -> str:
    fm, body = parse_frontmatter(page_text)
    projected_at = fm.get("projected-at", "unknown")
    blocks = split_blocks(body)
    q_terms = _tokenize(question)

    def _score(candidates: list[tuple[str, str]]) -> list[tuple[int, str, str]]:
        out = []
        for heading, block in candidates:
            hits = len(q_terms & _tokenize(block))
            if hits:
                out.append((hits, heading, block))
        out.sort(key=lambda x: -x[0])
        return out

    # Two-pass, active-first -- matching ledger.search()'s own default (inactive
    # excluded unless --all). A soft tiebreak is not enough: found live in KT-4's
    # smoke test that a superseded block can *outscore* its active replacement on
    # raw token overlap alone (e.g. a predecessor's literal "per PR" phrasing beat
    # the successor's reworded text, 5 hits to 2) -- not just tie with it. A
    # plausible-but-stale answer is worse than a correct one, so the active set is
    # searched first and only falls through to the full set (superseded/redacted
    # included) when nothing active matches -- the case a genuinely retired-only
    # topic (no active replacement) still needs to stay findable.
    active_blocks = [(h, b) for h, b in blocks if "(superseded)" not in h and "(REDACTED)" not in h]
    scored = _score(active_blocks)
    if not scored:
        scored = _score(blocks)

    if not scored:
        return f"[cortex as of {projected_at}] no matching decision found."

    _, heading, block = scored[0]
    return f"[cortex as of {projected_at}] {heading}\n{block.strip()}"


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: kt4_portable_recall.py <cortex_page.md> <question>", file=sys.stderr)
        return 2
    page_path, question = sys.argv[1], sys.argv[2]
    with open(page_path, encoding="utf-8") as f:
        page_text = f.read()
    print(answer(page_text, question))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
