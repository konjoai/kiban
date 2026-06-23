"""Test konjo-newonly: only net-new findings block.

Drives the CLI against a throwaway git repo with a scanner that reports findings from a
file, so the base has a pre-existing finding and HEAD adds one.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "bin" / "konjo-newonly"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                  capture_output=True, text=True)


def _make_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    # Base commit: one pre-existing finding.
    (repo / "findings.txt").write_text("file.py:10:1 PREEXISTING bad thing\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    _git(repo, "checkout", "-qb", "work")
    return repo, base


def _run(repo: Path, base: str) -> subprocess.CompletedProcess[str]:
    # Scanner just prints the findings file. Different line numbers must not matter.
    scanner = [sys.executable, "-c",
              "import pathlib,sys;"
              "p=pathlib.Path('findings.txt');"
              "sys.stdout.write(p.read_text() if p.exists() else '')"]
    return subprocess.run(
        [sys.executable, str(BIN), "--base", base, "--", *scanner],
        cwd=str(repo), capture_output=True, text=True,
    )


def test_net_new_finding_blocks(tmp_path: Path) -> None:
    repo, base = _make_repo(tmp_path)
    # HEAD adds a new finding on top of the pre-existing one.
    (repo / "findings.txt").write_text(
        "file.py:12:1 PREEXISTING bad thing\nother.py:5:1 NEWLY introduced bug\n"
    )
    _git(repo, "commit", "-qam", "add new finding")
    result = _run(repo, base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "NEWLY introduced bug" in result.stdout
    assert "PREEXISTING" not in result.stdout


def test_dirty_tree_is_not_clobbered(tmp_path: Path) -> None:
    # C3: a base scan must not touch the working tree. With an uncommitted change to a
    # tracked file present, konjo-newonly must still report the net-new finding AND
    # leave the dirty change intact (the worktree path scans the base out-of-place).
    repo, base = _make_repo(tmp_path)
    (repo / "findings.txt").write_text(
        "file.py:12:1 PREEXISTING bad thing\nother.py:5:1 NEWLY introduced bug\n"
    )
    _git(repo, "commit", "-qam", "add new finding")
    # Introduce an uncommitted edit to a tracked file.
    sentinel = repo / "tracked.py"
    sentinel.write_text("# committed\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "add tracked file")
    sentinel.write_text("# committed\n# UNCOMMITTED LOCAL EDIT\n")

    result = _run(repo, base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "NEWLY introduced bug" in result.stdout
    # The dirty edit survived untouched.
    assert "UNCOMMITTED LOCAL EDIT" in sentinel.read_text()


def test_no_new_finding_passes(tmp_path: Path) -> None:
    repo, base = _make_repo(tmp_path)
    # HEAD only shifts the line of the pre-existing finding; nothing new.
    (repo / "findings.txt").write_text("file.py:99:1 PREEXISTING bad thing\n")
    (repo / "pad.txt").write_text("x\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qam", "shift line only")
    result = _run(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no net-new findings" in result.stdout
