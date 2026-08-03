"""Regression tests for lib/bench.py's Rust adapters, both bugs found live during
Sprint P2's PF-0 baseline run against lopi (see LEDGER.md).

1. `_tests_rust`'s nextest-missing fallback checked `code == 127`, the shell's own
   "command not found" convention -- but `cargo <unknown-subcommand>` prints its own
   "error: no such command: ..." and exits 101, not 127 (confirmed live on cargo
   1.88.0). The fallback to `cargo test --workspace` never fired.
2. `_mutation_rust`'s per-crate breakdown crashed on the Baseline outcome entry, whose
   `scenario` field is the bare string `"Baseline"` rather than `{"Mutant": {...}}`
   like every real mutant entry -- `.get("Mutant", {})` on a string raised
   `AttributeError`, caught and reported as "per-crate mutation breakdown unavailable"
   on every real run.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from lib import bench


def test_tests_rust_falls_back_to_cargo_test_when_nextest_missing(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, cwd, timeout=None):
        calls.append(cmd)
        if cmd[:2] == ["cargo", "nextest"]:
            return (101, "error: no such command: `nextest`\n\nhelp: ...", 0.05)
        assert cmd == ["cargo", "test", "--workspace"]
        return (0, "test result: ok. 3 passed; 0 failed", 1.23)

    result = bench.BenchResult(repo="lopi", repo_kind="rust", sha="abc123", started_at="2026-08-03T00:00:00Z")
    with mock.patch.object(bench, "_run", side_effect=fake_run):
        bench._tests_rust(tmp_path, result)

    assert calls[0][:2] == ["cargo", "nextest"]
    assert calls[1] == ["cargo", "test", "--workspace"]
    assert result.tests_ok is True
    assert result.test_count == 3
    assert result.errors == []


def test_tests_rust_records_real_failure_without_masking_as_missing_tool(
    tmp_path: Path,
) -> None:
    def fake_run(cmd, cwd, timeout=None):
        if cmd[:2] == ["cargo", "nextest"]:
            return (101, "test result: FAILED. 37 passed; 1 failed", 120.1)
        raise AssertionError("should not fall back on a real test failure")

    result = bench.BenchResult(repo="lopi", repo_kind="rust", sha="abc123", started_at="2026-08-03T00:00:00Z")
    with mock.patch.object(bench, "_run", side_effect=fake_run):
        bench._tests_rust(tmp_path, result)

    assert result.tests_ok is False
    assert result.errors == ["test run exit 101 in 120.1s"]


def test_mutation_rust_per_crate_breakdown_skips_baseline_entry(tmp_path: Path) -> None:
    out_dir = tmp_path / ".cargo-mutants-bench"
    mutants_out = out_dir / "mutants.out"
    mutants_out.mkdir(parents=True)
    (mutants_out / "outcomes.json").write_text(
        json.dumps(
            {
                "outcomes": [
                    {"scenario": "Baseline", "summary": "Success"},
                    {
                        "scenario": {"Mutant": {"file": "crates/lopi-ratelimit/src/lib.rs"}},
                        "summary": "CaughtMutant",
                    },
                    {
                        "scenario": {"Mutant": {"file": "crates/lopi-ratelimit/src/lib.rs"}},
                        "summary": "MissedMutant",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    result = bench.BenchResult(repo="lopi", repo_kind="rust", sha="abc123", started_at="2026-08-03T00:00:00Z")
    with mock.patch.object(
        bench, "_run", return_value=(0, "2 mutants tested in 0s: 1 missed, 1 caught", 1.0)
    ):
        bench._mutation_rust(tmp_path, result, timeout_s=60)

    assert result.errors == []
    assert result.mutation_per_crate == {
        "crates": {"caught": 1, "missed": 1, "unviable": 0}
    }
