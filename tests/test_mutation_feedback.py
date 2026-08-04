"""Tests for the surviving-mutant feedback formatter (lib/mutation_feedback.py).

Synthetic repo + outcomes.json shaped exactly like a real `cargo mutants --output`
report (Sprint P2 pre-flight PF-2 confirmed this schema against a live run) -- no
dependency on any other repo being checked out alongside kiban.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib import mutation_feedback as mf

SRC = '''pub struct Bucket;

impl Bucket {
    /// Deduct `n` from the bucket.
    pub fn take(&mut self, n: u32) -> u32 {
        self.remaining -= n;
        self.remaining
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn take_returns_something() {
        let mut b = Bucket::default();
        b.take(1);
    }

    #[test]
    fn another_test() {
        assert!(true);
    }
}
'''


def _outcomes(missed: bool) -> dict:
    mutant = {
        "name": "src/lib.rs:6:9: replace -= with += in Bucket::take",
        "package": "demo",
        "file": "src/lib.rs",
        "function": {
            "function_name": "Bucket::take",
            "return_type": "-> u32",
            "span": {"start": {"line": 5, "column": 5}, "end": {"line": 8, "column": 6}},
        },
        "span": {"start": {"line": 6, "column": 9}, "end": {"line": 6, "column": 11}},
        "replacement": "+=",
        "genre": "BinaryOperator",
    }
    return {
        "outcomes": [
            {"scenario": "Baseline", "summary": "Success"},
            {
                "scenario": {"Mutant": mutant},
                "summary": "MissedMutant" if missed else "CaughtMutant",
                "log_path": "log/x.log",
                "diff_path": "diff/x.diff",
            },
        ],
        "total_mutants": 1,
    }


def _write_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "lib.rs").write_text(SRC, encoding="utf-8")
    return repo


def test_load_missed_mutants_filters_to_missed_only(tmp_path: Path) -> None:
    out_dir = tmp_path / "mutants.out"
    out_dir.mkdir()
    (out_dir / "outcomes.json").write_text(json.dumps(_outcomes(missed=True)))
    missed = mf.load_missed_mutants(out_dir)
    assert len(missed) == 1
    assert missed[0]["function"]["function_name"] == "Bucket::take"


def test_load_missed_mutants_excludes_caught(tmp_path: Path) -> None:
    out_dir = tmp_path / "mutants.out"
    out_dir.mkdir()
    (out_dir / "outcomes.json").write_text(json.dumps(_outcomes(missed=False)))
    assert mf.load_missed_mutants(out_dir) == []


def test_build_record_resolves_real_item_and_mutation(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path)
    mutant = _outcomes(missed=True)["outcomes"][1]["scenario"]["Mutant"]
    record = mf.build_record(repo, mutant)
    assert record.file == "src/lib.rs"
    assert record.line == 6
    assert record.function == "Bucket::take"
    assert record.original == "self.remaining -= n;"
    assert record.replacement == "+="
    assert "pub fn take" in record.item_source
    assert "self.remaining -= n;" in record.item_source
    # The full enclosing item, not just the mutated line.
    assert record.item_source.count("\n") >= 2


def test_build_record_finds_tests_in_the_same_file(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path)
    mutant = _outcomes(missed=True)["outcomes"][1]["scenario"]["Mutant"]
    record = mf.build_record(repo, mutant)
    assert set(record.tests_still_passing) == {"take_returns_something", "another_test"}


def test_build_record_rationale_is_one_line(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path)
    mutant = _outcomes(missed=True)["outcomes"][1]["scenario"]["Mutant"]
    record = mf.build_record(repo, mutant)
    assert "\n" not in record.rationale


def test_format_feedback_caps_output(tmp_path: Path) -> None:
    repo = _write_repo(tmp_path)
    out_dir = tmp_path / "mutants.out"
    out_dir.mkdir()
    data = _outcomes(missed=True)
    # Duplicate the missed mutant entry to simulate more than `cap` survivors.
    data["outcomes"] = data["outcomes"] + [data["outcomes"][1]] * 5
    (out_dir / "outcomes.json").write_text(json.dumps(data))
    records = mf.format_feedback(repo, out_dir, cap=3)
    assert len(records) == 3


def test_format_feedback_missing_outcomes_raises(tmp_path: Path) -> None:
    with pytest.raises(mf.MutationFeedbackError):
        mf.format_feedback(tmp_path, tmp_path / "does-not-exist")


def test_build_record_missing_source_file_raises(tmp_path: Path) -> None:
    repo = tmp_path / "empty_repo"
    repo.mkdir()
    mutant = _outcomes(missed=True)["outcomes"][1]["scenario"]["Mutant"]
    with pytest.raises(mf.MutationFeedbackError):
        mf.build_record(repo, mutant)
