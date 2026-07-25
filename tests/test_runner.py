"""Tests for the eval harness's fail-closed propagation (evals/runner.py).

review_diff's INCOMPLETE state must survive the harness the same way it survives the
live gate (bin/konjo-review) -- one function, two callers, one failure contract. An
incomplete fixture must fail the run without being misreported as a missed bug or a
control that fired (both would point a session at the wrong fix).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from evals import runner
from lib.review import ScriptedBackend

_DIFF = """diff --git a/squish/kv_cache.py b/squish/kv_cache.py
--- a/squish/kv_cache.py
+++ b/squish/kv_cache.py
@@ -1,3 +1,3 @@
-self.k = mx.concatenate([self.k, keys], axis=2)
+self.k = mx.concatenate([self.k, keys.astype(mx.float32)], axis=2)
"""


def _write_fixture(corpus_dir: Path, name: str, expect: dict) -> None:
    fixture = corpus_dir / name
    fixture.mkdir(parents=True)
    (fixture / "diff.patch").write_text(_DIFF)
    (fixture / "expect.json").write_text(json.dumps(expect))


def _write_profile(tmp_path: Path) -> Path:
    profile_path = tmp_path / "profile.yml"
    profile_path.write_text(
        yaml.dump({"stack": ["python", "mlx"], "specialists": ["numerics"]})
    )
    return profile_path


def test_incomplete_specialist_fails_a_must_flag_fixture_without_a_false_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "fixtures"
    _write_fixture(corpus, "bug", {"must_flag": {"category": "numerics", "severity": "CRITICAL"}})
    # evaluate_fixture names a fixture relative to the module-level FIXTURES_DIR
    # regardless of the corpus_dir passed in; point it at our scratch corpus.
    monkeypatch.setattr(runner, "FIXTURES_DIR", corpus)
    backend = ScriptedBackend({}, fail_always={"numerics"})

    report = runner.run(
        _write_profile(tmp_path), runs=1, backend=backend, corpus_dir=corpus
    )

    assert not report["ok"]
    assert report["summary"]["incomplete_fixtures"] == ["bug"]
    # An incomplete review is not a "missed bug": that label points a session at the
    # wrong fix (tune the lane) instead of the right one (the dispatch failed).
    assert report["summary"]["missed_bugs"] == []
    fixture = next(f for f in report["fixtures"] if f["name"] == "bug")
    assert fixture["incomplete"]
    assert not fixture["passed"]


def test_incomplete_specialist_fails_a_control_fixture_without_a_false_positive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "fixtures"
    _write_fixture(corpus, "control", {"must_be_silent": True})
    monkeypatch.setattr(runner, "FIXTURES_DIR", corpus)
    backend = ScriptedBackend({}, fail_always={"numerics"})

    report = runner.run(
        _write_profile(tmp_path), runs=1, backend=backend, corpus_dir=corpus
    )

    assert not report["ok"]
    assert report["summary"]["incomplete_fixtures"] == ["control"]
    # Likewise not a "control fired": the control was never actually evaluated.
    assert report["summary"]["false_positive_controls"] == []


def test_clean_run_has_no_incomplete_fixtures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "fixtures"
    _write_fixture(corpus, "control", {"must_be_silent": True})
    monkeypatch.setattr(runner, "FIXTURES_DIR", corpus)
    backend = ScriptedBackend({})

    report = runner.run(
        _write_profile(tmp_path), runs=1, backend=backend, corpus_dir=corpus
    )

    assert report["ok"]
    assert report["summary"]["incomplete_fixtures"] == []
