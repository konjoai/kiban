#!/usr/bin/env python3
"""KT-4: does a CLI-free recall variant answer correctly with no local binary?

Runs all 30 KT-1 questions through the portable retriever (kt4_portable_recall.py,
stdlib-only, no ledger/lib import) against the real projected page, in-process for
convenience -- the actual no-CLI claim is verified separately by
`run_kt4_subprocess_smoke.sh`, which spawns the same script in a scrubbed
environment with no PATH access to any konjo-* binary and no ~/.konjo.
"""

from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import kt4_portable_recall as recall  # noqa: E402


def main() -> None:
    page_text = (HERE / "kt1_projected_scope.md").read_text()
    with open(HERE / "kt1_questions.jsonl") as f:
        questions = [json.loads(line) for line in f]

    hits = 0
    for q in questions:
        out = recall.answer(page_text, q["question"])
        first_line = out.splitlines()[0]
        got_correct = f"`{q['answer_id']}`" in first_line
        hits += got_correct
        status = "HIT" if got_correct else "MISS"
        print(f"{q['n']:>3}  {status:>4}  {first_line}")

    print(f"\n{hits}/{len(questions)} correct ({100 * hits / len(questions):.1f}%)")


if __name__ == "__main__":
    main()
