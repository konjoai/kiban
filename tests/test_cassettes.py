"""Tests for the cassette record/replay backend (C-A)."""

from __future__ import annotations

import json

import pytest

from evals import cassettes
from lib.review import ScriptedBackend, review_diff

SQUISH = {
    "stack": ["python", "mlx"],
    "specialists": ["numerics", "memory-bandwidth", "concurrency", "api-surface"],
}

MLX_DIFF = """diff --git a/squish/kv.py b/squish/kv.py
--- a/squish/kv.py
+++ b/squish/kv.py
@@ -1 +1 @@
-self.k = mx.concatenate([self.k, keys], axis=2)
+self.k = mx.concatenate([self.k, keys.astype(mx.float32)], axis=2)
"""

NUMERICS_REPLY = json.dumps(
    [{"severity": "CRITICAL", "confidence": 9, "path": "squish/kv.py", "line": 1,
      "category": "numerics", "summary": "fp16 cache promoted to fp32", "fix": "keep fp16"}]
)


def test_recording_then_replay_is_deterministic() -> None:
    # Record from a scripted "live" backend, then replay with no live backend at all.
    live = ScriptedBackend({"numerics": NUMERICS_REPLY})
    recorder = cassettes.RecordingBackend(live)
    review_diff(MLX_DIFF, SQUISH, backend=recorder, mode="deep")
    assert recorder.data  # captured something

    replay = cassettes.ReplayBackend(dict(recorder.data))
    r1 = review_diff(MLX_DIFF, SQUISH, backend=replay, runs=3, mode="deep")
    r2 = review_diff(MLX_DIFF, SQUISH, backend=replay, runs=3, mode="deep")
    assert r1.has("numerics", "CRITICAL")
    # Identical across runs and across invocations.
    assert [len(run) for run in r1.per_run] == [len(run) for run in r2.per_run]
    assert all(any(f.category == "numerics" for f in run) for run in r1.per_run)


def test_replay_miss_is_hard_error() -> None:
    replay = cassettes.ReplayBackend({})  # empty cassette
    with pytest.raises(cassettes.CassetteMiss):
        review_diff(MLX_DIFF, SQUISH, backend=replay, mode="deep")


def test_save_and_load_roundtrip(tmp_path: object) -> None:
    from pathlib import Path
    d = Path(str(tmp_path))
    cassettes.save_cassette("squish/dtype", {"k1": "reply"}, cassette_dir=d)
    loaded = cassettes.load_cassettes(d)
    assert loaded == {"k1": "reply"}
    assert cassettes.cassettes_present(d)
