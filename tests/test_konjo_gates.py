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

from lib import diff_scope  # noqa: E402

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


def test_rust_tools_route_to_cargo() -> None:
    # All Rust tools are SCOPE_RUST and invoke cargo; their argv runs through lib.newonly.
    for tool in ("clippy", "fmt-check", "cargo-deny", "cargo-mutants"):
        assert cli._TOOL_SCOPE[tool] == "SCOPE_RUST"
        assert cli._TOOL_BIN.get(tool, tool) == "cargo"
        assert cli._tool_argv(tool, [])[0] == "cargo"


def _stub_cargo(bin_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake `cargo` on PATH: `clippy` prints `findings.txt` in cwd and exits nonzero
    when it is non-empty (mirroring clippy's real deny-warnings exit code); `deny
    --version` succeeds (present); `mutants` is not installed."""
    stub = bin_dir / "cargo"
    stub.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "deny" ] && [ "$2" = "--version" ]; then echo "cargo-deny 1.0"; exit 0; fi\n'
        'if [ "$1" = "mutants" ]; then\n'
        '  echo "error: no such subcommand: \\`mutants\\`" >&2; exit 101\n'
        "fi\n"
        'if [ "$1" = "clippy" ]; then\n'
        "  cat findings.txt 2>/dev/null\n"
        '  if [ -s findings.txt ]; then exit 101; fi\n'
        "  exit 0\n"
        "fi\n"
        "exit 0\n"
    )
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{__import__('os').environ['PATH']}")


def test_rust_gate_clean_diff_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean Rust diff (no new clippy finding) reports PASS -- the tool actually ran,
    it did not fall back to a generic "net-new findings" failure."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub_cargo(bin_dir, monkeypatch)

    repo = _new_repo(tmp_path)
    (repo / "findings.txt").write_text("src/lib.rs:10:1 warning: preexisting lint\n")
    (repo / "Cargo.toml").write_text("[package]\nname = 'x'\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-q", "-b", "feature")

    cwd = Path.cwd()
    import os as _os
    try:
        _os.chdir(repo)
        (repo / "README.md").write_text("docs only\n")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "unrelated doc change")
        r = cli.gate_repo_native("clippy", {"SCOPE_RUST": True}, ["README.md"], "main")
        assert r.status == cli.PASS, r.detail
    finally:
        _os.chdir(cwd)


def test_rust_gate_dirty_diff_fails_with_real_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A deliberately dirty diff (a net-new clippy finding) reports FAIL with the
    tool's real finding text, not the generic "net-new findings" string."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub_cargo(bin_dir, monkeypatch)

    repo = _new_repo(tmp_path)
    (repo / "findings.txt").write_text("src/lib.rs:10:1 warning: preexisting lint\n")
    (repo / "Cargo.toml").write_text("[package]\nname = 'x'\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-q", "-b", "feature")

    cwd = Path.cwd()
    import os as _os
    try:
        _os.chdir(repo)
        (repo / "findings.txt").write_text(
            "src/lib.rs:10:1 warning: preexisting lint\n"
            "src/new.rs:5:1 warning: newly introduced lint\n"
        )
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "add clippy violation")
        r = cli.gate_repo_native("clippy", {"SCOPE_RUST": True}, ["src/new.rs"], "main")
        assert r.status == cli.FAIL
        assert "newly introduced lint" in r.detail
        assert r.detail != "net-new findings"
    finally:
        _os.chdir(cwd)


def test_cargo_deny_passes_with_no_dependency_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cargo-deny only inspects the dependency tree; a code-only diff must PASS."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub_cargo(bin_dir, monkeypatch)

    repo = _new_repo(tmp_path)
    (repo / "Cargo.toml").write_text("[package]\nname = 'x'\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-q", "-b", "feature")

    cwd = Path.cwd()
    import os as _os
    try:
        _os.chdir(repo)
        (repo / "src").mkdir()
        (repo / "src" / "lib.rs").write_text("pub fn f() {}\n")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "code-only change, no Cargo.toml/lock edit")
        r = cli.gate_repo_native("cargo-deny", {"SCOPE_RUST": True}, ["src/lib.rs"], "main")
        assert r.status == cli.PASS, r.detail
    finally:
        _os.chdir(cwd)


def test_cargo_subcommand_missing_is_distinct_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`cargo` is on PATH but the `mutants` subcommand plugin is not installed: this
    must surface as a distinct tool-unavailable ERROR, never a false "net-new
    findings" FAIL."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub_cargo(bin_dir, monkeypatch)

    repo = _new_repo(tmp_path)
    (repo / "Cargo.toml").write_text("[package]\nname = 'x'\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")

    cwd = Path.cwd()
    import os as _os
    try:
        _os.chdir(repo)
        r = cli.gate_repo_native("cargo-mutants", {"SCOPE_RUST": True}, ["src/lib.rs"], "main")
        assert r.status == cli.ERROR
        assert "net-new findings" not in r.detail
    finally:
        _os.chdir(cwd)


def test_gate_repo_native_does_not_depend_on_bin_konjo_newonly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test for the packaging bug: gate_repo_native used to shell out to
    `KIBAN_ROOT / "bin" / "konjo-newonly"`, a path that does not exist once kiban is
    pip-installed (bin/ ships with no package/scripts declaration). Pointing
    KIBAN_ROOT at an empty directory with no bin/ at all must not break the gate --
    it now calls lib.newonly.net_new in-process."""
    monkeypatch.setattr(cli, "KIBAN_ROOT", tmp_path / "nonexistent-root")
    assert not (cli.KIBAN_ROOT / "bin" / "konjo-newonly").exists()

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub_cargo(bin_dir, monkeypatch)

    repo = _new_repo(tmp_path)
    (repo / "Cargo.toml").write_text("[package]\nname = 'x'\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-q", "-b", "feature")

    cwd = Path.cwd()
    import os as _os
    try:
        _os.chdir(repo)
        (repo / "README.md").write_text("docs only\n")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "unrelated doc change")
        r = cli.gate_repo_native("clippy", {"SCOPE_RUST": True}, ["README.md"], "main")
        assert r.status == cli.PASS, r.detail
    finally:
        _os.chdir(cwd)


def _stub_cargo_fmt_abspath(bin_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake `cargo fmt --check` that prints an absolute path rooted at its OWN cwd,
    exactly like the real tool's `Diff in <abs path>:<line>:` output -- as opposed to
    `_stub_cargo`'s `findings.txt`, which is a repo-relative fixture and does not
    exercise the absolute-path bug."""
    stub = bin_dir / "cargo"
    stub.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "fmt" ]; then\n'
        "  found=0\n"
        "  for f in untouched.rs new.rs; do\n"
        '    if [ -f "$f" ]; then echo "Diff in $(pwd)/$f:12:"; found=1; fi\n'
        "  done\n"
        '  [ "$found" = "1" ] && exit 1\n'
        "  exit 0\n"
        "fi\n"
        "exit 0\n"
    )
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{__import__('os').environ['PATH']}")


def test_rust_gate_ignores_preexisting_finding_with_absolute_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test (kiban#18): a pre-existing finding on a file the PR never
    touched must not become "net-new" merely because the tool prints an absolute
    path and HEAD (the real checkout) and the base ref (a throwaway git worktree)
    have different absolute roots. `cargo fmt --check`, `cargo clippy`, and `cargo
    deny check` all print absolute paths, so this was previously silently broken
    for every one of them: the whole repo's pre-existing lint backlog looked
    net-new on every single Rust PR."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _stub_cargo_fmt_abspath(bin_dir, monkeypatch)

    repo = _new_repo(tmp_path)
    (repo / "untouched.rs").write_text("fn f() {}\n")
    (repo / "Cargo.toml").write_text("[package]\nname = 'x'\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base with a pre-existing (never fixed) fmt violation")
    _git(repo, "checkout", "-q", "-b", "feature")

    cwd = Path.cwd()
    import os as _os
    try:
        _os.chdir(repo)
        (repo / "README.md").write_text("unrelated doc change\n")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "unrelated change; untouched.rs is not part of this diff")
        r = cli.gate_repo_native("fmt-check", {"SCOPE_RUST": True}, ["README.md"], "main")
        assert r.status == cli.PASS, r.detail
    finally:
        _os.chdir(cwd)


def test_unsafe_budget_gate_net_new_blocks() -> None:
    diff = "@@ -1 +1,3 @@\n fn f() {\n+    unsafe {\n+        ptr.read();\n"
    assert cli.gate_unsafe_budget({"SCOPE_RUST": True}, diff).status == cli.FAIL


def test_unsafe_budget_gate_with_safety_passes() -> None:
    diff = (
        "@@ -1 +1,4 @@\n fn f() {\n+    // SAFETY: valid for this call\n"
        "+    unsafe {\n+        ptr.read();\n"
    )
    assert cli.gate_unsafe_budget({"SCOPE_RUST": True}, diff).status == cli.PASS


def test_unsafe_budget_gate_skips_non_rust() -> None:
    assert cli.gate_unsafe_budget({"SCOPE_DOCS": True}, "+anything").status == cli.SKIP


def test_rust_change_activates_rust_lanes_and_tools() -> None:
    flags = diff_scope.scope(["src/lib.rs"])
    assert flags["SCOPE_RUST"] and diff_scope.has_code(flags)
    # A docs-only change activates no code lane and no rust tool.
    docs = diff_scope.scope(["README.md"])
    assert not diff_scope.has_code(docs) and not docs["SCOPE_RUST"]


def test_scope_ts_extensions_are_code() -> None:
    flags = diff_scope.scope(["app/a.ts", "b.tsx", "c.mts"])
    assert flags["SCOPE_TS"] and diff_scope.has_code(flags)
    assert not flags["SCOPE_PYTHON"] and not flags["SCOPE_RUST"]


def test_ts_tools_route_to_npx_and_npm() -> None:
    for tool in ("tsc", "eslint", "stryker"):
        assert cli._TOOL_SCOPE[tool] == "SCOPE_TS"
        assert cli._TOOL_BIN[tool] == "npx"
        assert cli._tool_argv(tool, [])[0] == "npx"
    assert cli._TOOL_SCOPE["npm-audit"] == "SCOPE_TS"
    assert cli._TOOL_BIN["npm-audit"] == "npm"
    assert cli._tool_argv("npm-audit", []) == ["npm", "audit"]


def test_ts_tool_absent_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.shutil, "which", lambda _b: None)
    r = cli.gate_repo_native("tsc", {"SCOPE_TS": True}, ["src/app.ts"], "main")
    assert r.status == cli.ERROR


def test_ts_tool_skipped_when_not_in_scope() -> None:
    assert cli.gate_repo_native("tsc", {"SCOPE_PYTHON": True}, ["m.py"], "main").status == cli.SKIP


def test_mojo_tools_route_to_mojo_under_scope_mojo() -> None:
    for tool in ("mojo-format", "mojo-test"):
        assert cli._TOOL_SCOPE[tool] == "SCOPE_MOJO"
        assert cli._TOOL_BIN[tool] == "mojo"
        assert cli._tool_argv(tool, [])[0] == "mojo"


def test_mojo_extensions_are_code_scope() -> None:
    flags = diff_scope.scope(["src/x.mojo", "k.🔥"])
    assert flags["SCOPE_MOJO"] and diff_scope.has_code(flags)


def test_mojo_tool_absent_is_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.shutil, "which", lambda _b: None)
    r = cli.gate_repo_native("mojo-format", {"SCOPE_MOJO": True}, ["a.mojo"], "main")
    assert r.status == cli.ERROR


def test_longrun_gate_skips_non_longrun_change() -> None:
    assert cli.gate_longrun(["src/app.py", "README.md"], {}).status == cli.SKIP


def test_longrun_gate_fails_script_without_resume(tmp_path: Path) -> None:
    cwd = Path.cwd()
    import os as _os
    try:
        _os.chdir(tmp_path)
        (tmp_path / "benchmarks").mkdir()
        (tmp_path / "benchmarks" / "bench_x.py").write_text(
            "for i in range(5):\n    do(i)\n"
        )
        r = cli.gate_longrun(["benchmarks/bench_x.py"], {})
        assert r.status == cli.FAIL
        assert "resume" in r.detail
    finally:
        _os.chdir(cwd)


def test_longrun_gate_passes_compliant_script(tmp_path: Path) -> None:
    cwd = Path.cwd()
    import os as _os
    try:
        _os.chdir(tmp_path)
        (tmp_path / "benchmarks").mkdir()
        (tmp_path / "benchmarks" / "bench_y.py").write_text(
            "import argparse\n"
            "from lib.packs.longrun import konjo_longrun\n"
            "p = argparse.ArgumentParser()\n"
            "konjo_longrun.add_resume_args(p)\n"
            "c = konjo_longrun.Checkpoint('p.jsonl')\n"
            "for i in range(5):\n"
            "    if c.done(str(i)):\n        continue\n"
            "    c.mark(str(i), i)\n"
        )
        r = cli.gate_longrun(["benchmarks/bench_y.py"], {})
        assert r.status == cli.PASS
    finally:
        _os.chdir(cwd)


def test_longrun_gate_exempts_bench_named_library(tmp_path: Path) -> None:
    # A library that shares a benchmark's prefix (bench_*.py) but is not a runnable script
    # (no __main__, not under benchmarks/) must not be forced to wire resume.
    cwd = Path.cwd()
    import os as _os
    try:
        _os.chdir(tmp_path)
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib" / "bench_adapter.py").write_text(
            "def adapt(x):\n    return x * 2\n"
        )
        r = cli.gate_longrun(["lib/bench_adapter.py"], {})
        assert r.status == cli.SKIP
    finally:
        _os.chdir(cwd)


def test_longrun_glob_matching() -> None:
    globs = list(cli._DEFAULT_LONGRUN_GLOBS)
    assert cli._is_longrun_path("benchmarks/sub/bench.py", globs)
    assert cli._is_longrun_path("bench_main.py", globs)
    assert cli._is_longrun_path("scripts/train_big.py", globs)
    assert not cli._is_longrun_path("src/app.py", globs)


def test_verify_cmd_gate_present_passes() -> None:
    assert cli.gate_verify_cmd({"verify_cmd": "pytest"}).status == cli.PASS


def test_verify_cmd_gate_absent_warns() -> None:
    r = cli.gate_verify_cmd({})
    assert r.status == cli.WARN
    assert "verify_cmd" in r.detail


def test_verify_cmd_gate_blank_or_placeholder_warns() -> None:
    # An empty string, or an honest TODO/UNVERIFIED placeholder, is still a surfaced gap.
    assert cli.gate_verify_cmd({"verify_cmd": "   "}).status == cli.WARN
    assert cli.gate_verify_cmd({"verify_cmd": "TODO-confirm-against-vectro"}).status == cli.WARN
    assert cli.gate_verify_cmd({"verify_cmd": "UNVERIFIED"}).status == cli.WARN


def test_verify_cmd_gate_never_blocks() -> None:
    # Report-only: a WARN is not blocking, so a missing verify_cmd never fails CI.
    assert not cli.gate_verify_cmd({}).blocking


def test_one_way_gate_two_way_passes() -> None:
    r = cli.gate_one_way_door(["notes.py"], "+# a harmless comment\n", "main")
    assert r.status == cli.PASS


def test_one_way_gate_unacknowledged_fails_and_acknowledged_passes(tmp_path: Path) -> None:
    from lib import oneway

    repo = _new_repo(tmp_path)
    (repo / "VERSION").write_text("0.3.0\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-q", "-b", "feature")

    changed = ["VERSION"]
    diff = "-0.3.0\n+0.4.0\n"
    fp = oneway.fingerprint(changed)

    cwd = Path.cwd()
    import os as _os
    try:
        _os.chdir(repo)
        # A one-way change (release VERSION bump) with no ack: the gate fails and never
        # touches stdin.
        (repo / "VERSION").write_text("0.4.0\n")
        _git(repo, "commit", "-aqm", "bump version")
        unacked = cli.gate_one_way_door(changed, diff, "main")
        assert unacked.status == cli.FAIL
        assert fp in unacked.detail

        # Add a commit carrying the acknowledgement trailer: the gate passes.
        (repo / "note.txt").write_text("release prep\n")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", f"ack release\n\n{oneway.ack_trailer(fp)}")
        acked = cli.gate_one_way_door(changed, diff, "main")
        assert acked.status == cli.PASS
    finally:
        _os.chdir(cwd)
