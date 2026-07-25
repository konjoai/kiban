"""Tests for bin/konjo-review: the live CLI caller of review_diff.

This is the actual production entry point that hits the real Claude CLI
(ClaudeCLIBackend). It must block on an INCOMPLETE review the same way it blocks on a
CRITICAL/HIGH finding -- a specialist that failed to complete carries no signal that
the diff is clean, so it must never let a merge through silently.
"""

from __future__ import annotations

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

from lib.review import DEFAULT_LIVE_RUNS, Finding, ReviewResult, SpecialistReport

_BIN = Path(__file__).resolve().parent.parent / "bin" / "konjo-review"


def _load_konjo_review():
    loader = SourceFileLoader("konjo_review_bin", str(_BIN))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


@pytest.fixture()
def konjo_review():
    return _load_konjo_review()


def _incomplete_result() -> ReviewResult:
    reports = [SpecialistReport(name="numerics", dispatches=2, n_findings=0, failed=True)]
    return ReviewResult(
        findings=[],
        per_run=[[]],
        specialist_reports=reports,
        runs=1,
        mode="daily",
        threshold=8,
        selected=["numerics"],
    )


def _clean_result() -> ReviewResult:
    reports = [SpecialistReport(name="numerics", dispatches=1, n_findings=0)]
    return ReviewResult(
        findings=[],
        per_run=[[]],
        specialist_reports=reports,
        runs=1,
        mode="daily",
        threshold=8,
        selected=["numerics"],
    )


def test_cli_defaults_to_multi_run_live_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, konjo_review
) -> None:
    # The live gate must not be weaker than DEFAULT_LIVE_RUNS without an explicit
    # --runs override -- confirm the CLI actually passes that default through to
    # review_diff, not just that the library default exists.
    diff_file = tmp_path / "d.patch"
    diff_file.write_text("+++ b/x.py\n+pass\n")
    captured: dict[str, object] = {}

    def _fake_review_diff(*_a: object, **kw: object) -> ReviewResult:
        captured.update(kw)
        return _clean_result()

    monkeypatch.setattr(konjo_review.review, "review_diff", _fake_review_diff)
    monkeypatch.setattr(konjo_review.review_log, "record", lambda *a, **kw: "ignored")

    rc = konjo_review.main(["--diff-file", str(diff_file), "--no-log"])
    assert rc == 0
    assert captured["runs"] == DEFAULT_LIVE_RUNS


def test_incomplete_review_blocks_even_with_zero_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, konjo_review
) -> None:
    diff_file = tmp_path / "d.patch"
    diff_file.write_text("+++ b/x.py\n+pass\n")
    monkeypatch.setattr(konjo_review.review, "review_diff", lambda *a, **kw: _incomplete_result())
    monkeypatch.setattr(konjo_review.review_log, "record", lambda *a, **kw: "ignored")

    rc = konjo_review.main(["--diff-file", str(diff_file), "--no-log"])
    assert rc == 1


def test_clean_review_still_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, konjo_review
) -> None:
    diff_file = tmp_path / "d.patch"
    diff_file.write_text("+++ b/x.py\n+pass\n")
    monkeypatch.setattr(konjo_review.review, "review_diff", lambda *a, **kw: _clean_result())
    monkeypatch.setattr(konjo_review.review_log, "record", lambda *a, **kw: "ignored")

    rc = konjo_review.main(["--diff-file", str(diff_file), "--no-log"])
    assert rc == 0


def test_incomplete_review_blocks_even_with_only_low_severity_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, konjo_review
) -> None:
    diff_file = tmp_path / "d.patch"
    diff_file.write_text("+++ b/x.py\n+pass\n")

    def _result() -> ReviewResult:
        reports = [SpecialistReport(name="numerics", dispatches=2, n_findings=0, failed=True)]
        low = Finding("LOW", 9, "x.py", 1, "numerics", "minor nit", "fix", "numerics")
        return ReviewResult(
            findings=[low],
            per_run=[[low]],
            specialist_reports=reports,
            runs=1,
            mode="daily",
            threshold=8,
            selected=["numerics"],
        )

    monkeypatch.setattr(konjo_review.review, "review_diff", lambda *a, **kw: _result())
    monkeypatch.setattr(konjo_review.review_log, "record", lambda *a, **kw: "ignored")

    rc = konjo_review.main(["--diff-file", str(diff_file), "--no-log"])
    assert rc == 1
