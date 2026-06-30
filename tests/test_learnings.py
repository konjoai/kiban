"""Tests for the learnings log (lib/learnings).

Mirrors the Ledger tests: a temp state dir via KONJO_STATE_DIR keeps these off the real
store. The load-bearing new behavior is the enforcement guardrail: a learning with no
enforcement target is refused.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.learnings import LearningsLog, MissingEnforcement


def _log(tmp_path: Path) -> LearningsLog:
    return LearningsLog(path=str(tmp_path / "learnings.jsonl"))


def test_learn_writes_and_folds_active(tmp_path: Path) -> None:
    log = _log(tmp_path)
    lid = log.learn(
        "Reworded a moved prompt during a refactor",
        "Move lane prompts verbatim; assert byte-equality",
        "tests/test_packs.py frozen prompt-hash",
        scope="org",
        author="t",
    )
    got = log.get(lid)
    assert got is not None
    assert got.active and not got.redacted
    assert got.mistake.startswith("Reworded")
    assert got.enforcement.startswith("tests/")


def test_learn_refuses_without_enforcement(tmp_path: Path) -> None:
    log = _log(tmp_path)
    with pytest.raises(MissingEnforcement):
        log.learn("a mistake", "a rule", "   ")
    # Nothing was written: a refused learning is not a note in the log.
    assert log.active() == []


def test_learn_requires_mistake_and_rule(tmp_path: Path) -> None:
    log = _log(tmp_path)
    with pytest.raises(ValueError):
        log.learn("", "a rule", "a gate")
    with pytest.raises(ValueError):
        log.learn("a mistake", "", "a gate")


def test_redact_retires_learning(tmp_path: Path) -> None:
    log = _log(tmp_path)
    lid = log.learn("m", "r", "CLAUDE.md line")
    log.redact_learning(lid, reason="superseded by a gate")
    got = log.get(lid)
    assert got is not None and got.redacted and not got.active
    assert log.active() == []


def test_redact_unknown_id_raises(tmp_path: Path) -> None:
    log = _log(tmp_path)
    with pytest.raises(KeyError):
        log.redact_learning("deadbeef", reason="x")


def test_search_matches_mistake_rule_and_enforcement(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.learn("dropped error context", "carry context through ?", "error-handling lane")
    log.learn("needless clone in a loop", "reuse a reference", "perf-alloc lane")
    # match on the enforcement target
    hits = log.search("perf-alloc")
    assert len(hits) == 1 and hits[0].mistake.startswith("needless")
    # match on the rule text
    assert any("context" in h.rule for h in log.search("context"))
    # empty query returns all active
    assert len(log.search("")) == 2


def test_search_is_active_first(tmp_path: Path) -> None:
    log = _log(tmp_path)
    keep = log.learn("m1", "r1", "gate-a")
    drop = log.learn("m2", "r2", "gate-b")
    log.redact_learning(drop, reason="obsolete")
    results = log.search("")
    # active item sorts before the redacted one
    assert results[0].id == keep
    assert results[-1].id == drop


def test_scope_filter(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.learn("m-org", "r", "g", scope="org")
    log.learn("m-repo", "r", "g", scope="repo:squish")
    assert {x.scope for x in log.active(scope="repo:squish")} == {"repo:squish"}
    assert len(log.search("", scope="org")) == 1
