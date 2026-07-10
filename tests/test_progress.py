"""Tests for lib.progress and the konjo-gates heartbeat/verbose wiring.

The bug these guard against is operational, not logical: konjo-gates ran a dozen gates
(several shelling a scanner out twice) with every child's output captured, printed the
result table only at the very end, and so produced a CI log that sat silent for many
minutes and then failed with no clue which gate was to blame. The fix is a stderr
heartbeat that is always on (one line as each gate starts, one when it finishes with its
elapsed time) plus verbose per-scan detail behind --verbose / KONJO_GATES_VERBOSE.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_PKG_SRC = _ROOT / "packages" / "konjo-gates-py" / "src"
for _p in (str(_ROOT), str(_PKG_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from konjo_gates_py import cli  # noqa: E402

from lib import progress  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _new_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "checkout", "-q", "-b", "main")
    return repo


@pytest.fixture(autouse=True)
def _reset_verbose():
    # Each test starts from a known verbosity so env leakage between tests can't flip it.
    before = progress.is_verbose()
    progress.set_verbose(False)
    yield
    progress.set_verbose(before)


def test_log_always_emits_to_stderr_not_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    progress.set_verbose(False)
    progress.log("heartbeat here")
    out = capsys.readouterr()
    assert "heartbeat here" in out.err
    assert "heartbeat here" not in out.out


def test_vlog_is_silent_unless_verbose(capsys: pytest.CaptureFixture[str]) -> None:
    progress.set_verbose(False)
    progress.vlog("detail")
    assert "detail" not in capsys.readouterr().err

    progress.set_verbose(True)
    progress.vlog("detail")
    assert "detail" in capsys.readouterr().err


def test_set_verbose_propagates_to_env() -> None:
    import os

    progress.set_verbose(True)
    assert os.environ["KONJO_GATES_VERBOSE"] == "1"
    progress.set_verbose(False)
    assert os.environ["KONJO_GATES_VERBOSE"] == "0"


def test_fmt_elapsed_reads_at_a_glance() -> None:
    assert progress.fmt_elapsed(0.42) == "0.4s"
    assert progress.fmt_elapsed(12.9) == "12.9s"
    # A 20-minute gate -- the whole reason for this feature -- renders as minutes+seconds.
    assert progress.fmt_elapsed(1204) == "20m04s"


def test_run_gates_emits_a_heartbeat_per_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """run_gates must announce every gate as it runs -- the operator sees which gate is
    in flight, not just the ones that already finished."""
    repo = _new_repo(tmp_path)
    (repo / "note.txt").write_text("hi\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")

    cwd = Path.cwd()
    import os as _os

    try:
        _os.chdir(repo)
        results = cli.run_gates(
            {},
            str(_ROOT / "profiles" / "squish.yml"),
            base="HEAD",
            changed=["note.txt"],
            diff_text="+hi\n",
            mode="daily",
            self_test=False,
        )
    finally:
        _os.chdir(cwd)

    err = capsys.readouterr().err
    # Every gate result appears in a "running..." line and a completion line naming its status.
    for r in results:
        assert f"{r.name}: running..." in err, r.name
        assert f"{r.name}: {r.status}" in err, r.name


def test_repo_native_gate_verbose_shows_both_scan_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Under --verbose the net-new engine must reveal that it scans TWICE (HEAD + base) --
    the concrete answer to 'why is this one gate taking so long'."""
    import shutil as _shutil

    if _shutil.which("ruff") is None:
        pytest.skip("ruff not installed")

    repo = _new_repo(tmp_path)
    (repo / "m.py").write_text("import os\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-q", "-b", "feature")

    cwd = Path.cwd()
    import os as _os

    try:
        _os.chdir(repo)
        (repo / "m.py").write_text("\nimport os\n")
        _git(repo, "commit", "-qam", "shift line")
        progress.set_verbose(True)
        cli.gate_repo_native("ruff", {"SCOPE_PYTHON": True}, ["m.py"], "main")
    finally:
        _os.chdir(cwd)

    err = capsys.readouterr().err
    assert "pass 1/2: scanning HEAD" in err
    assert "pass 2/2: scanning base" in err
