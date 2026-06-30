"""Tests for the long-run checkpoint helper (lib/packs/longrun/konjo_longrun)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from lib.packs.longrun import konjo_longrun as kl


def _ckpt(tmp_path: Path, **kw: object) -> kl.Checkpoint:
    return kl.Checkpoint(str(tmp_path / "progress.jsonl"), **kw)


def test_mark_done_and_completed(tmp_path: Path) -> None:
    c = _ckpt(tmp_path)
    assert not c.done("u1")
    c.mark("u1", "r1")
    c.mark("u2", "r2")
    assert c.done("u1") and c.done("u2")
    assert c.completed() == {"u1", "u2"}
    assert c.results() == {"u1": "r1", "u2": "r2"}


def test_resume_reads_prior_progress(tmp_path: Path) -> None:
    c = _ckpt(tmp_path)
    c.mark("u1", "r1")
    c.mark("u2", "r2")
    # A second Checkpoint over the same file resumes: it sees the prior units.
    resumed = _ckpt(tmp_path)
    assert resumed.completed() == {"u1", "u2"}
    assert not resumed.done("u3")


def test_unit_idempotency_latest_wins(tmp_path: Path) -> None:
    c = _ckpt(tmp_path)
    c.mark("u1", "first")
    c.mark("u1", "second")
    # The fold keeps the latest result; the unit is not duplicated in the view.
    assert c.results() == {"u1": "second"}
    assert list(c.completed()) == ["u1"]


def test_fresh_clears_prior(tmp_path: Path) -> None:
    c = _ckpt(tmp_path)
    c.mark("u1", "r1")
    fresh = _ckpt(tmp_path, fresh=True)
    assert fresh.completed() == set()


def test_mark_requires_nonempty_string_key(tmp_path: Path) -> None:
    c = _ckpt(tmp_path)
    with pytest.raises(ValueError):
        c.mark("", "r")


def test_resume_tolerates_a_corrupt_line(tmp_path: Path) -> None:
    c = _ckpt(tmp_path)
    c.mark("u1", "r1")
    c.mark("u2", "r2")
    # Append a garbage line directly, as a partial write would leave.
    path = tmp_path / "progress.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{ this is not valid json\n")
    # Resume still reads the valid units; the corrupt line is skipped, not fatal.
    resumed = _ckpt(tmp_path)
    assert resumed.completed() == {"u1", "u2"}


def test_resumed_run_equals_fresh_run(tmp_path: Path) -> None:
    units = [f"u{i}" for i in range(5)]

    def run(c: kl.Checkpoint) -> None:
        for u in units:
            if c.done(u):
                continue
            c.mark(u, u.upper())

    # Interrupted run: only the first three units complete.
    partial = kl.Checkpoint(str(tmp_path / "a.jsonl"))
    for u in units[:3]:
        partial.mark(u, u.upper())
    # Resume completes the rest.
    resumed = kl.Checkpoint(str(tmp_path / "a.jsonl"))
    run(resumed)

    # A clean fresh run in a separate file.
    fresh = kl.Checkpoint(str(tmp_path / "b.jsonl"), fresh=True)
    run(fresh)

    assert resumed.results() == fresh.results()


def test_is_fresh_resolution() -> None:
    # resume-by-default script
    p = argparse.ArgumentParser()
    kl.add_resume_args(p, default_fresh=False)
    assert kl.is_fresh(p.parse_args([])) is False
    assert kl.is_fresh(p.parse_args(["--fresh"])) is True
    assert kl.is_fresh(p.parse_args(["--resume"])) is False

    # fresh-by-default script
    q = argparse.ArgumentParser()
    kl.add_resume_args(q, default_fresh=True)
    assert kl.is_fresh(q.parse_args([])) is True
    assert kl.is_fresh(q.parse_args(["--resume"])) is False


def test_resume_and_fresh_are_mutually_exclusive() -> None:
    p = argparse.ArgumentParser()
    kl.add_resume_args(p)
    with pytest.raises(SystemExit):
        p.parse_args(["--resume", "--fresh"])
