"""Tests for the konjo-gates orchestrator: routing, net-new discipline, gate outcomes.

The orchestrator imports the real engine; these tests exercise its gate functions
directly. The repo-native net-new test uses ruff (installed) in a scratch git repo.
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

PRIVATE_KEY = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIIBVgIBADANBgkqhkiG9w0BAQEFAASCAUAwggE8AgEAAkEA\n"
    "-----END PRIVATE KEY-----"
)


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


def test_secrets_gate_high_blocks() -> None:
    added = "\n".join("+" + ln for ln in f"key = {PRIVATE_KEY}".splitlines())
    diff = "+++ b/c.txt\n" + added + "\n"
    assert cli.gate_secrets(diff).status == cli.FAIL


def test_secrets_gate_clean_passes() -> None:
    assert cli.gate_secrets("+++ b/c.txt\n+nothing to see\n").status == cli.PASS


def test_self_test_gate_passes_via_replay() -> None:
    # Uses the committed cassettes; deterministic, no network.
    result = cli.gate_self_test(str(_ROOT / "profiles" / "squish.yml"), "daily")
    assert result.status in (cli.PASS, cli.SKIP)
    if result.status == cli.SKIP:
        pytest.skip("no cassettes present in this checkout")


def test_repo_native_netnew_discipline(tmp_path: Path) -> None:
    repo = _new_repo(tmp_path)
    # Base: a python file with a pre-existing ruff finding (unused import).
    (repo / "m.py").write_text("import os\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base with preexisting finding")
    _git(repo, "checkout", "-q", "-b", "feature")

    flags = {"SCOPE_PYTHON": True}
    cwd = Path.cwd()
    try:
        import os as _os
        _os.chdir(repo)

        # Only the pre-existing finding present on a shifted line: net-new wrapper passes.
        (repo / "m.py").write_text("\nimport os\n")
        _git(repo, "commit", "-qam", "shift line only")
        r_clean = cli.gate_repo_native("ruff", flags, ["m.py"], "main")
        assert r_clean.status == cli.PASS, r_clean.detail

        # Add a NET-NEW finding (a second unused import): the gate blocks.
        (repo / "m.py").write_text("\nimport os\nimport sys\n")
        _git(repo, "commit", "-qam", "add net-new finding")
        r_new = cli.gate_repo_native("ruff", flags, ["m.py"], "main")
        assert r_new.status == cli.FAIL, r_new.detail
    finally:
        import os as _os
        _os.chdir(cwd)


def test_absent_tool_is_clear_error() -> None:
    flags = {"SCOPE_PYTHON": True}
    r = cli.gate_repo_native("vulture-not-real", flags, ["m.py"], "main")
    # Unknown tool has no scope mapping -> a clear non-blocking warn, never a crash.
    assert r.status == cli.WARN


def test_python_tool_absent_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # A known tool named in the profile but not installed is a blocking ERROR.
    monkeypatch.setattr(cli.shutil, "which", lambda _b: None)
    r = cli.gate_repo_native("mypy", {"SCOPE_PYTHON": True}, ["m.py"], "main")
    assert r.status == cli.ERROR


def test_docs_only_skips_python_tools() -> None:
    flags = {"SCOPE_DOCS": True}
    r = cli.gate_repo_native("ruff", flags, ["README.md"], "main")
    assert r.status == cli.SKIP
