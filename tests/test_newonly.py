"""Test konjo-newonly: only net-new findings block.

Drives the CLI against a throwaway git repo with a scanner that reports findings from a
file, so the base has a pre-existing finding and HEAD adds one.
"""

from __future__ import annotations

import os
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


def _make_abspath_repo(tmp_path: Path) -> tuple[Path, str]:
    """A repo with an untouched file carrying a pre-existing finding, scanned by a
    tool (like real `cargo fmt --check`) that prints its OWN absolute cwd in the
    finding line rather than a repo-relative path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "untouched.rs").write_text("fn f() {}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    _git(repo, "checkout", "-qb", "work")
    return repo, base


def test_absolute_path_finding_on_untouched_file_is_not_net_new(tmp_path: Path) -> None:
    """Regression test (kiban#18): a scanner that prints an absolute path rooted at
    its own cwd -- exactly what `cargo fmt --check` / `cargo clippy` / `cargo deny
    check` do -- must not have every pre-existing finding look net-new merely
    because HEAD is scanned in the real checkout and the base ref is scanned in a
    throwaway git-worktree tmp directory with a different absolute root."""
    repo, base = _make_abspath_repo(tmp_path)
    # A scanner that prints the finding rooted at its OWN cwd, mirroring `cargo fmt
    # --check`'s `Diff in <abs path>:<line>:` output.
    scanner = [sys.executable, "-c",
              "import pathlib,os,sys;"
              "p=pathlib.Path('untouched.rs');"
              "sys.stdout.write(f'Diff in {os.getcwd()}/{p}:12:\\n') if p.exists() else None"]
    (repo / "README.md").write_text("unrelated doc change\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "unrelated change; untouched.rs's finding is pre-existing")
    result = subprocess.run(
        [sys.executable, str(BIN), "--base", base, "--", *scanner],
        cwd=str(repo), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no net-new findings" in result.stdout


def test_shared_cargo_target_dir_does_not_leak_state_across_scans(tmp_path: Path) -> None:
    """Regression test: cargo-based tools (clippy, cargo-mutants) build the crate, so
    they read $CARGO_TARGET_DIR. CI commonly sets it globally to share a build cache
    across jobs. Left untouched, the HEAD scan (real checkout) and the base-ref scan
    (a throwaway worktree at an unrelated absolute path) would both write into that
    same directory back-to-back -- letting one scan's cached/incremental state leak
    into the other's and produce a different result for genuinely unmodified source, an
    unremovable false net-new. `net_new` must scrub CARGO_TARGET_DIR so each scan gets
    its own cwd-relative default instead.

    The stub scanner below stands in for a compiling tool: it leaves a marker file in
    whatever it resolves as its target dir and reports whether the marker was already
    there from an earlier invocation ("contaminated") or not ("clean"). If
    CARGO_TARGET_DIR leaks across scans, HEAD's scan leaves the marker and the base
    scan -- of genuinely unmodified source -- sees it and reports a different finding
    than HEAD did: a spurious diff on code that never changed.
    """
    repo, base = _make_repo(tmp_path)
    (repo / "findings.txt").write_text("")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qam", "unrelated change; findings.txt scanner output unaffected")

    shared_target = tmp_path / "shared-cargo-target"
    scanner = [
        sys.executable, "-c",
        "import os;"
        "d=os.environ.get('CARGO_TARGET_DIR') or os.path.join(os.getcwd(), 'target');"
        "os.makedirs(d, exist_ok=True);"
        "f=os.path.join(d, 'marker');"
        "contaminated=os.path.exists(f);"
        "open(f, 'w').close();"
        "print('finding-contaminated' if contaminated else 'finding-clean')",
    ]
    env = dict(os.environ, CARGO_TARGET_DIR=str(shared_target))
    result = subprocess.run(
        [sys.executable, str(BIN), "--base", base, "--", *scanner],
        cwd=str(repo), capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no net-new findings" in result.stdout


def test_compile_duration_suffix_does_not_look_net_new(tmp_path: Path) -> None:
    """Regression test (reported from a real `konjoai/pdfree` CI run): `cargo`'s own
    build output prints wall-clock durations with a unit suffix glued directly onto the
    digits -- "Finished `dev` profile [unoptimized + debuginfo] target(s) in 12.94s",
    cargo-mutants' "MISSED ... in 1s build + 5s test" -- and a digit immediately
    followed by a letter is a word-to-word transition, not a `\\b` boundary, so the old
    `\\b\\d+\\b` normalization left the whole token untouched. Since compile/test time
    is never identical between the HEAD scan and the base-ref scan, every line
    containing one of these durations compared as different and was reported as a
    false net-new finding on every single run, for any tool that compiles (clippy,
    cargo-mutants) -- never for one that doesn't (fmt-check, cargo-deny), which matches
    exactly which gates stayed broken after the v1.1.2 root-stripping fix.
    """
    repo, base = _make_repo(tmp_path)
    (repo / "findings.txt").write_text("")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qam", "unrelated change; findings.txt scanner output unaffected")

    # A scanner that reports the same finding every time, but with a different,
    # realistic compile-duration suffix glued onto the digits -- exactly the shape of
    # cargo's own timing output, and different on every invocation as real wall-clock
    # timing would be.
    scanner = [
        sys.executable, "-c",
        "import random;"
        "print(f'Finished `dev` profile [unoptimized + debuginfo] target(s) "
        "in {random.uniform(1, 99):.2f}s')",
    ]
    result = subprocess.run(
        [sys.executable, str(BIN), "--base", base, "--", *scanner],
        cwd=str(repo), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no net-new findings" in result.stdout


def test_ansi_colored_line_number_does_not_defeat_normalization(tmp_path: Path) -> None:
    """Regression test (reported from a real `konjoai/vectro` CI run): `dtolnay/
    rust-toolchain` forces CARGO_TERM_COLOR=always, so a real `cargo clippy` diagnostic
    wraps its source-snippet line-number gutter in ANSI color codes, e.g.
    "\\x1b[94m221\\x1b[0m | ...". `_NUM_RE` requires a `\\b` word boundary on both sides
    of the digit run to normalize a line number away, but a digit glued to the escape
    code's trailing letter ("94m", "0m") is a word-to-word transition -- no boundary, no
    match -- so the ANSI codes silently defeat the very normalization that's supposed to
    make a pre-existing finding whose line merely shifted (because the PR added or
    removed lines earlier in the same file) compare equal at HEAD and base. The result:
    a completely unmodified clippy warning reappears as a false net-new on every PR that
    touches an earlier line in the same file. `_normalize` must strip ANSI escapes
    before the numeric normalization runs.
    """
    repo, base = _make_repo(tmp_path)
    (repo / "findings.txt").write_text("")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qam", "unrelated change; findings.txt scanner output unaffected")

    # A scanner that reports the identical pre-existing diagnostic every time, but at a
    # different line number each run -- the exact shape of a clippy source snippet whose
    # unrelated line shifted, colorized exactly like a real ANSI-enabled cargo run.
    scanner = [
        sys.executable, "-c",
        "import random;"
        "n=random.randint(1, 999);"
        "print(f'\\x1b[0m\\x1b[1;94m{n}\\x1b[0m\\x1b[0m | '"
        "f'        if self.dim == 0 {{\\x1b[0m')",
    ]
    result = subprocess.run(
        [sys.executable, str(BIN), "--base", base, "--", *scanner],
        cwd=str(repo), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no net-new findings" in result.stdout


def test_cargo_build_progress_noise_is_not_a_finding(tmp_path: Path) -> None:
    """Regression test (reported from a real `konjoai/vectro` CI run): `cargo` prints
    its own build/fetch progress as a right-justified verb + message ("   Compiling foo
    v1.2.3", "    Checking bar v0.4.0") to stdout/stderr alongside real diagnostics. The
    HEAD scan runs in the real checkout (a warm, possibly cache-restored `target/`); the
    base-ref scan runs in a throwaway `git worktree` with no cache at all, so it always
    starts colder. Which crates print a fresh "Compiling"/"Checking" line is a function
    of that incremental-build cache state, not of the diff being scanned -- so on a real
    PR the HEAD scan showed "Checking crossbeam-channel v0.8" and "Compiling vectro_py
    v8.17" that the base scan never printed, and konjo-gates reported them as net-new
    lint findings even though they are pure build noise with zero diagnostic content.
    This must be filtered out regardless of whether the two scans agree on it.
    """
    repo, base = _make_repo(tmp_path)
    (repo / "findings.txt").write_text("")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qam", "unrelated change; findings.txt scanner output unaffected")

    # A scanner that prints only cargo-style build-progress noise -- no diagnostic at
    # all -- and varies which crates it names each run, exactly like an asymmetric
    # warm-vs-cold build cache would.
    scanner = [
        sys.executable, "-c",
        "import random;"
        "crates=['crossbeam-channel v0.8', 'num_cpus v1.0', 'numpy v0.1', 'rustc-hash v1.0'];"
        "random.shuffle(crates);"
        "[print(f'   Checking {c}') for c in crates[:random.randint(1, 4)]];"
        "print('   Compiling vectro_py v8.17 (rust/vectro_py)')",
    ]
    result = subprocess.run(
        [sys.executable, str(BIN), "--base", base, "--", *scanner],
        cwd=str(repo), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no net-new findings" in result.stdout
