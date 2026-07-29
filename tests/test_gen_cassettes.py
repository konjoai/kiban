"""evals/gen_cassettes.py: record/replay round trip for the task-to-diff loop."""

from __future__ import annotations

from pathlib import Path

import pytest

from evals import gen_cassettes
from lib.gen_runner import GenerationResult, GenTask


class _FakeBackend:
    def __init__(self, diff: str) -> None:
        self.diff = diff
        self.calls = 0

    def generate(
        self, task: GenTask, context_text: str, *, model: str | None = None
    ) -> GenerationResult:
        self.calls += 1
        return GenerationResult(
            task_id=task.id, context_label=task.context_label, diff_text=self.diff,
            changed_paths=["x.py"], returncode=0, ok=True, stdout_tail="",
            model=model, duration_s=1.0, worktree="/tmp/should-not-be-recorded",
        )


def _task(**over: object) -> GenTask:
    base = dict(
        id="t1", prompt="do the thing", context_label="baseline",
        source="unit-test", repo="/repo", base_ref="HEAD",
    )
    base.update(over)
    return GenTask(**base)  # type: ignore[arg-type]


def test_recording_backend_captures_result_keyed_by_task_and_context() -> None:
    inner = _FakeBackend("diff-content")
    recorder = gen_cassettes.RecordingGenBackend(inner)
    task = _task()
    result = recorder.generate(task, context_text="ctx")

    assert result.diff_text == "diff-content"
    key = gen_cassettes.gen_cassette_key("t1", "baseline", "ctx", "do the thing")
    assert key in recorder.data
    # worktree paths never persist into a cassette
    assert recorder.data[key]["worktree"] is None


def test_replay_backend_serves_recorded_result_without_calling_inner() -> None:
    inner = _FakeBackend("diff-content")
    recorder = gen_cassettes.RecordingGenBackend(inner)
    task = _task()
    recorder.generate(task, context_text="ctx")

    replay = gen_cassettes.ReplayGenBackend(recorder.data)
    result = replay.generate(task, context_text="ctx")
    assert result.diff_text == "diff-content"
    assert result.task_id == "t1"


def test_replay_miss_is_a_hard_error() -> None:
    replay = gen_cassettes.ReplayGenBackend({})
    with pytest.raises(gen_cassettes.GenCassetteMiss):
        replay.generate(_task(), context_text="ctx")


def test_different_context_text_is_a_different_key() -> None:
    key_a = gen_cassettes.gen_cassette_key("t1", "baseline", "context A", "prompt")
    key_b = gen_cassettes.gen_cassette_key("t1", "baseline", "context B", "prompt")
    assert key_a != key_b


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    inner = _FakeBackend("diff-content")
    recorder = gen_cassettes.RecordingGenBackend(inner)
    recorder.generate(_task(), context_text="ctx")

    gen_cassettes.save_gen_cassette("my-fixture", recorder.data, cassette_dir=tmp_path)
    assert gen_cassettes.gen_cassettes_present(tmp_path)
    loaded = gen_cassettes.load_gen_cassettes(tmp_path)
    assert loaded == recorder.data
