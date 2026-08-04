"""Tests for lib/mutation_hunt_loop.py (section 3): loop mechanics, offline.

No live model calls and no real cargo-mutants runs (matching this repo's test
convention) -- `_run_round_generation`, `check_clean_tree`, and
`run_cargo_mutants_in_diff` are the seams, monkeypatched per test. A real end-to-end
run against a real fixture crate is this sprint's separate, live verify step (see
LEDGER.md), not a unit test.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lib import gen_runner, mutation_feedback, oneway, uncovered_items
from lib import mutation_hunt_loop as mhl


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "scratch_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "src.rs").write_text("fn a() {}\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def _one_uncovered_item(monkeypatch: pytest.MonkeyPatch) -> None:
    item = uncovered_items.UncoveredItem(
        file="src.rs", qualified_name="a", start_line=1, end_line=1, uncovered_lines=[1]
    )
    monkeypatch.setattr(uncovered_items, "extract_uncovered_items", lambda *a, **k: [item])


def _fake_generation_writes_a_file(worktree: Path, prompt: str, **kwargs):
    (worktree / "touched.rs").write_text("fn touched() {}\n")
    subprocess.run(["git", "add", "-A"], cwd=worktree, capture_output=True, text=True)
    diff = subprocess.run(
        ["git", "diff", "--cached"], cwd=worktree, capture_output=True, text=True
    ).stdout
    return diff, ["touched.rs"], True, (100, 50, 0, 0.01)


def _missed_mutant(file="src.rs", line=1, replacement="0"):
    return {
        "file": file,
        "span": {"start": {"line": line}, "end": {"line": line}},
        "function": {"function_name": "a", "span": {"start": {"line": 1}, "end": {"line": 1}}},
        "replacement": replacement,
    }


def test_loop_terminates_on_zero_surviving_first_round(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _init_repo(tmp_path)
    _one_uncovered_item(monkeypatch)
    monkeypatch.setattr(mhl, "_run_round_generation", _fake_generation_writes_a_file)
    monkeypatch.setattr(mhl, "check_clean_tree", lambda *a, **k: mhl.CleanTreeCheck(ok=True))
    monkeypatch.setattr(mhl, "run_cargo_mutants_in_diff", lambda *a, **k: Path("unused"))
    monkeypatch.setattr(mutation_feedback, "load_missed_mutants", lambda *a, **k: [])
    monkeypatch.setattr(mutation_feedback, "format_feedback", lambda *a, **k: [])

    result = mhl.run_mutation_hunt_loop(
        repo, _head(repo), uncovered_by_file={"src.rs": {1}}, ast_diff_binary=None,
    )
    assert result.terminated_reason == "zero_surviving"
    assert result.gate_pass is True
    assert len(result.rounds) == 1
    assert result.rounds[0].prompt_kind == "uncovered_item"
    assert result.rounds[0].surviving_count_after == 0
    assert result.waiver_trailer_suggestion is None


def test_loop_uses_feedback_shape_from_round_two_onward(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _init_repo(tmp_path)
    _one_uncovered_item(monkeypatch)
    monkeypatch.setattr(mhl, "_run_round_generation", _fake_generation_writes_a_file)
    monkeypatch.setattr(mhl, "check_clean_tree", lambda *a, **k: mhl.CleanTreeCheck(ok=True))
    monkeypatch.setattr(mhl, "run_cargo_mutants_in_diff", lambda *a, **k: Path("unused"))

    calls = {"n": 0}

    def fake_load_missed(*a, **k):
        calls["n"] += 1
        return [] if calls["n"] >= 2 else [_missed_mutant()]

    def fake_format_feedback(*a, **k):
        return [] if calls["n"] >= 2 else [{
            "file": "src.rs", "line": 1, "function": "a", "original": "1",
            "replacement": "0", "item_source": "fn a() {}", "tests_still_passing": [],
            "rationale": "x",
        }]

    monkeypatch.setattr(mutation_feedback, "load_missed_mutants", fake_load_missed)
    monkeypatch.setattr(mutation_feedback, "format_feedback", fake_format_feedback)

    result = mhl.run_mutation_hunt_loop(
        repo, _head(repo), uncovered_by_file={"src.rs": {1}}, ast_diff_binary=None, round_cap=3,
    )
    assert result.terminated_reason == "zero_surviving"
    assert len(result.rounds) == 2
    assert result.rounds[0].prompt_kind == "uncovered_item"
    assert result.rounds[1].prompt_kind == "mutation_feedback"  # arm-B shape, not a fresh item prompt
    assert result.rounds[0].mutants_killed is None  # no prior round to diff against
    assert result.rounds[1].mutants_killed == 1


def test_loop_hits_round_cap_with_mutants_still_surviving_and_suggests_waiver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo = _init_repo(tmp_path)
    _one_uncovered_item(monkeypatch)
    monkeypatch.setattr(mhl, "_run_round_generation", _fake_generation_writes_a_file)
    monkeypatch.setattr(mhl, "check_clean_tree", lambda *a, **k: mhl.CleanTreeCheck(ok=True))
    monkeypatch.setattr(mhl, "run_cargo_mutants_in_diff", lambda *a, **k: Path("unused"))
    monkeypatch.setattr(mutation_feedback, "load_missed_mutants", lambda *a, **k: [_missed_mutant()])
    monkeypatch.setattr(mutation_feedback, "format_feedback", lambda *a, **k: [{
        "file": "src.rs", "line": 1, "function": "a", "original": "1",
        "replacement": "0", "item_source": "fn a() {}", "tests_still_passing": [],
        "rationale": "x",
    }])

    result = mhl.run_mutation_hunt_loop(
        repo, _head(repo), uncovered_by_file={"src.rs": {1}}, ast_diff_binary=None, round_cap=2,
    )
    assert result.terminated_reason == "round_cap"
    assert len(result.rounds) == 2
    assert result.gate_pass is False
    assert result.waiver_trailer_suggestion is not None
    assert oneway.MUTATION_WAIVED_TRAILER in result.waiver_trailer_suggestion


def test_existing_waiver_trailer_satisfies_the_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _init_repo(tmp_path)
    _one_uncovered_item(monkeypatch)
    monkeypatch.setattr(mhl, "_run_round_generation", _fake_generation_writes_a_file)
    monkeypatch.setattr(mhl, "check_clean_tree", lambda *a, **k: mhl.CleanTreeCheck(ok=True))
    monkeypatch.setattr(mhl, "run_cargo_mutants_in_diff", lambda *a, **k: Path("unused"))
    feedback = [{
        "file": "src.rs", "line": 1, "function": "a", "original": "1",
        "replacement": "0", "item_source": "fn a() {}", "tests_still_passing": [],
        "rationale": "x",
    }]
    monkeypatch.setattr(mutation_feedback, "load_missed_mutants", lambda *a, **k: [_missed_mutant()])
    monkeypatch.setattr(mutation_feedback, "format_feedback", lambda *a, **k: feedback)

    fp = mhl._mutant_fingerprint(feedback)
    trailer_msg = oneway.make_trailer(oneway.MUTATION_WAIVED_TRAILER, fp) + " — accepted risk"

    result = mhl.run_mutation_hunt_loop(
        repo, _head(repo), uncovered_by_file={"src.rs": {1}}, ast_diff_binary=None, round_cap=1,
        commit_messages_for_waiver_check=trailer_msg,
    )
    assert result.gate_pass is True
    assert result.waiver_trailer_suggestion is None


def test_loop_stops_on_token_ceiling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _init_repo(tmp_path)
    _one_uncovered_item(monkeypatch)

    def big_usage_generation(worktree, prompt, **kwargs):
        (worktree / "touched.rs").write_text("fn touched() {}\n")
        subprocess.run(["git", "add", "-A"], cwd=worktree, capture_output=True, text=True)
        diff = subprocess.run(["git", "diff", "--cached"], cwd=worktree, capture_output=True, text=True).stdout
        return diff, ["touched.rs"], True, (500_000, 500_000, 0, 5.0)

    monkeypatch.setattr(mhl, "_run_round_generation", big_usage_generation)

    result = mhl.run_mutation_hunt_loop(
        repo, _head(repo), uncovered_by_file={"src.rs": {1}}, ast_diff_binary=None,
        token_ceiling_per_round=1000,
    )
    assert result.terminated_reason == "token_ceiling"
    assert len(result.rounds) == 1
    assert result.gate_pass is False


def test_loop_reports_generation_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _init_repo(tmp_path)
    _one_uncovered_item(monkeypatch)
    monkeypatch.setattr(mhl, "_run_round_generation", lambda *a, **k: ("", [], False, gen_runner._NO_USAGE))

    result = mhl.run_mutation_hunt_loop(
        repo, _head(repo), uncovered_by_file={"src.rs": {1}}, ast_diff_binary=None,
    )
    assert result.terminated_reason == "generation_failed"
    assert result.gate_pass is False


def test_clean_tree_failure_retries_within_round_cap_without_running_mutants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo = _init_repo(tmp_path)
    _one_uncovered_item(monkeypatch)
    monkeypatch.setattr(mhl, "_run_round_generation", _fake_generation_writes_a_file)

    calls = {"n": 0}

    def flaky_clean_tree(*a, **k):
        calls["n"] += 1
        return mhl.CleanTreeCheck(ok=(calls["n"] >= 2), failed_tests=[] if calls["n"] >= 2 else ["test x"])

    mutants_called = {"n": 0}

    def track_mutants(*a, **k):
        mutants_called["n"] += 1
        return Path("unused")

    monkeypatch.setattr(mhl, "check_clean_tree", flaky_clean_tree)
    monkeypatch.setattr(mhl, "run_cargo_mutants_in_diff", track_mutants)
    monkeypatch.setattr(mutation_feedback, "load_missed_mutants", lambda *a, **k: [])
    monkeypatch.setattr(mutation_feedback, "format_feedback", lambda *a, **k: [])

    result = mhl.run_mutation_hunt_loop(
        repo, _head(repo), uncovered_by_file={"src.rs": {1}}, ast_diff_binary=None, round_cap=3,
    )
    assert result.rounds[0].clean_tree.ok is False
    assert result.rounds[0].prompt_kind == "uncovered_item"
    assert result.rounds[1].prompt_kind == "clean_tree_failure"
    assert mutants_called["n"] == 1  # round 1's failed clean tree never reached cargo-mutants
    assert result.terminated_reason == "zero_surviving"


def test_section_2b_flags_truncation_when_feedback_is_capped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _init_repo(tmp_path)
    _one_uncovered_item(monkeypatch)
    monkeypatch.setattr(mhl, "_run_round_generation", _fake_generation_writes_a_file)
    monkeypatch.setattr(mhl, "check_clean_tree", lambda *a, **k: mhl.CleanTreeCheck(ok=True))
    monkeypatch.setattr(mhl, "run_cargo_mutants_in_diff", lambda *a, **k: Path("unused"))
    monkeypatch.setattr(mutation_feedback, "load_missed_mutants", lambda *a, **k: [_missed_mutant()] * 25)
    monkeypatch.setattr(mutation_feedback, "format_feedback", lambda *a, **k: [{
        "file": "src.rs", "line": 1, "function": "a", "original": "1",
        "replacement": "0", "item_source": "fn a() {}", "tests_still_passing": [],
        "rationale": "x",
    }] * 20)

    result = mhl.run_mutation_hunt_loop(
        repo, _head(repo), uncovered_by_file={"src.rs": {1}}, ast_diff_binary=None, round_cap=1,
    )
    assert result.rounds[0].surviving_total_before_cap == 25
    assert len(result.rounds[0].feedback) == 20
    assert result.rounds[0].truncated is True
