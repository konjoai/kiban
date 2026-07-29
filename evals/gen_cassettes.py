"""Record/replay for the task-to-diff loop (Phase 14, Phase 1) -- the same cassette
discipline `evals/cassettes.py` established for the review gate, applied to
`lib.gen_runner`'s generation backend instead of `lib.review`'s specialist backend.

Two distinct cassette families exist in this repo on purpose, not by duplication:
`evals/cassettes.py` records a specialist's *reply* keyed by (specialist, prompt); this
module records a generation session's *diff* keyed by (task, context). They wrap
different backends with different `dispatch`/`generate` signatures and different
result shapes (a reply string vs a `GenerationResult`), so one generic cassette module
would need a lowest-common-denominator interface neither caller actually has. Reusing
the *pattern* (hash the inputs, record once, replay with a hard miss) is the right
level of reuse; reusing the *code* would force an awkward abstraction over two
genuinely different result shapes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from lib.gen_runner import GenerationBackend, GenerationResult, GenTask

GEN_CASSETTE_DIR = Path(__file__).resolve().parent / "cassettes" / "gen"


class GenCassetteMiss(KeyError):
    """A replay had no recorded generation for this (task, context). The cassette is
    stale -- re-record with `konjo-eval genrun --record`."""


def gen_cassette_key(task_id: str, context_label: str, context_text: str, prompt: str) -> str:
    raw = f"{task_id}\n--CTX--\n{context_label}\n{context_text}\n--PROMPT--\n{prompt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class RecordingGenBackend:
    """Wrap a live `GenerationBackend` and capture every result keyed by (task, context)."""

    def __init__(self, inner: GenerationBackend) -> None:
        self.inner = inner
        self.data: dict[str, dict] = {}

    def generate(
        self, task: GenTask, context_text: str, *, model: str | None = None
    ) -> GenerationResult:
        result = self.inner.generate(task, context_text, model=model)
        key = gen_cassette_key(task.id, task.context_label, context_text, task.prompt)
        record = asdict(result)
        record["worktree"] = None  # never persist a local worktree path into a cassette
        self.data[key] = record
        return result


class ReplayGenBackend:
    """Serve recorded `GenerationResult`s. No worktree, no process. A miss is a hard error."""

    def __init__(self, data: dict[str, dict]) -> None:
        self.data = data

    def generate(
        self, task: GenTask, context_text: str, *, model: str | None = None
    ) -> GenerationResult:
        key = gen_cassette_key(task.id, task.context_label, context_text, task.prompt)
        if key not in self.data:
            raise GenCassetteMiss(
                f"no recorded generation for task {task.id!r} under context "
                f"{task.context_label!r} (key {key}). Re-record with: konjo-eval genrun --record"
            )
        return GenerationResult(**self.data[key])


def save_gen_cassette(
    fixture_name: str, data: dict[str, dict], cassette_dir: Path = GEN_CASSETTE_DIR
) -> Path:
    cassette_dir.mkdir(parents=True, exist_ok=True)
    safe = fixture_name.replace("/", "__").replace(" ", "_")
    path = cassette_dir / f"{safe}.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_gen_cassettes(cassette_dir: Path = GEN_CASSETTE_DIR) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    if not cassette_dir.exists():
        return merged
    for path in sorted(cassette_dir.glob("*.json")):
        try:
            merged.update(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return merged


def gen_cassettes_present(cassette_dir: Path = GEN_CASSETTE_DIR) -> bool:
    return cassette_dir.exists() and any(cassette_dir.glob("*.json"))
