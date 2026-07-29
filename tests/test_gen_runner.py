"""lib/gen_runner.py: the task-to-diff loop's worktree mechanics and result shape.

No live model calls here (matching this repo's test-suite convention -- fast, offline,
no network). `LiveGenerationBackend`'s tests monkeypatch `_run`, the one seam that
actually shells out to `claude`, and exercise everything around it for real: a real
scratch git repo, a real `git worktree add`/`git diff`/`git worktree remove`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lib import gen_runner
from lib.gen_runner import GenTask, LiveGenerationBackend


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "scratch_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


def test_make_worktree_checks_out_base_ref_and_cleans_up(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    worktree = gen_runner._make_worktree(repo, head, "unit-test")
    try:
        assert worktree.exists()
        wt_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=worktree, capture_output=True, text=True, check=True
        ).stdout.strip()
        assert wt_head == head
    finally:
        gen_runner._cleanup_worktree(repo, worktree)
    assert not worktree.exists()


def test_diff_and_paths_captures_new_untracked_file(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    worktree = gen_runner._make_worktree(repo, head, "unit-test-2")
    try:
        (worktree / "new_file.py").write_text("def f():\n    return 1\n")
        diff_text, changed_paths = gen_runner._diff_and_paths(worktree)
        assert "new_file.py" in diff_text
        assert changed_paths == ["new_file.py"]
    finally:
        gen_runner._cleanup_worktree(repo, worktree)


def test_live_backend_captures_diff_from_a_successful_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _init_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    def fake_run(argv: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        # Simulate the agent's edit: a real headless session would write this file
        # itself; here we write it directly to isolate the harness's own mechanics
        # (worktree, diff capture, result shape) from a live model call.
        (cwd / "added_by_task.py").write_text("def handled():\n    return True\n")
        return subprocess.CompletedProcess(argv, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(gen_runner, "_run", fake_run)

    task = GenTask(
        id="t1",
        prompt="add a function",
        context_label="baseline",
        source="unit-test",
        repo=str(repo),
        base_ref=head,
    )
    backend = LiveGenerationBackend()
    result = backend.generate(task, context_text="some org context")

    assert result.ok
    assert result.returncode == 0
    assert "added_by_task.py" in result.diff_text
    assert result.changed_paths == ["added_by_task.py"]
    assert result.worktree is None  # cleaned up by default
    # the worktree itself must actually be gone from disk
    assert not any((repo.parent / ".konjo-gen-worktrees").glob("konjo-gen__t1__*"))


def test_live_backend_reports_timeout_as_not_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _init_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    def fake_run(argv: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    monkeypatch.setattr(gen_runner, "_run", fake_run)

    task = GenTask(
        id="t2",
        prompt="add a function",
        context_label="baseline",
        source="unit-test",
        repo=str(repo),
        base_ref=head,
    )
    result = LiveGenerationBackend(timeout=5).generate(task, context_text="")

    assert not result.ok
    assert result.diff_text == ""
    assert "TIMEOUT" in result.stdout_tail


def test_keep_worktree_true_leaves_it_on_disk_and_reports_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _init_repo(tmp_path)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    def fake_run(argv: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        (cwd / "x.py").write_text("x = 1\n")
        return subprocess.CompletedProcess(argv, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(gen_runner, "_run", fake_run)

    task = GenTask(
        id="t3",
        prompt="p",
        context_label="baseline",
        source="unit-test",
        repo=str(repo),
        base_ref=head,
    )
    backend = LiveGenerationBackend(keep_worktree=True)
    result = backend.generate(task, context_text="")
    try:
        assert result.worktree is not None
        assert Path(result.worktree).exists()
    finally:
        gen_runner._cleanup_worktree(repo, Path(result.worktree))
