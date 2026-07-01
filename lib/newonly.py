"""newonly: report only net-new scanner findings versus a base ref.

This is the engine behind the `konjo-newonly` CLI and every `repo:*` gate in
konjo-gates that shells out to an external scanner (ruff, cargo clippy, cargo deny,
...). It runs the scanner on the current working tree (HEAD plus any local changes)
and on the merge-base of HEAD and a given base ref, then diffs the two finding sets
line-insensitively (line numbers normalized away). Only findings present at HEAD and
absent at the merge-base are net-new.

konjo-gates imports `net_new` directly and runs it in-process. It used to shell out to
the `bin/konjo-newonly` script instead, resolved via a path computed from the installed
package location -- a path that only exists in a source checkout. Once kiban ships as a
pip package (the root distribution, see pyproject.toml), that script is not on disk at
the computed path, so every repo-native gate crashed instantly (python's own missing
file error, `returncode != 0`, empty stdout) and got folded into a generic "net-new
findings" failure regardless of the real diff. Importing this module directly removes
the vanished-path failure mode entirely: `lib` is part of the installed distribution.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

_LOCATION_RE = re.compile(r"^([^\s:]+):\d+(?::\d+)?")
_NUM_RE = re.compile(r"\b\d+\b")


def _normalize(line: str) -> str:
    line = line.rstrip("\n")
    line = _LOCATION_RE.sub(lambda m: m.group(1) + ":N", line)
    line = _NUM_RE.sub("N", line)
    return line.strip()


def _run(cmd: list[str], cwd: str | None = None) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return proc.stdout + proc.stderr


def _git(args: list[str]) -> str:
    proc = subprocess.run(["git", *args], capture_output=True, text=True)
    return proc.stdout.strip()


def _git_ok(args: list[str]) -> bool:
    return subprocess.run(["git", *args], capture_output=True, text=True).returncode == 0


def _worktree_supported() -> bool:
    return _git_ok(["worktree", "list"])


def _tree_is_dirty() -> bool:
    return bool(_git(["status", "--porcelain"]))


def _findings_at_head(scanner: list[str]) -> set[str]:
    """Scan the current working tree (HEAD plus any local changes) in place."""
    out = _run(scanner)
    return {_normalize(line) for line in out.splitlines() if line.strip()}


def _findings_at_base(ref: str, scanner: list[str]) -> set[str]:
    """Scan the base ref WITHOUT touching the user's working tree (C3).

    Preferred path: check the ref out into a throwaway `git worktree` and run the
    scanner there. The caller's tree is never modified, so this is safe even with
    uncommitted changes. If worktrees are unavailable, the caller has already gated on
    a clean tree, so this falls back to an in-place checkout-and-restore.
    """
    if _worktree_supported():
        tmp = tempfile.mkdtemp(prefix="konjo-newonly-")
        try:
            if not _git_ok(["worktree", "add", "--quiet", "--detach", tmp, ref]):
                return set()
            out = _run(scanner, cwd=tmp)
            return {_normalize(line) for line in out.splitlines() if line.strip()}
        finally:
            _git(["worktree", "remove", "--force", tmp])
            shutil.rmtree(tmp, ignore_errors=True)

    # Fallback: in-place checkout. Only reached on a clean tree (gated by the caller).
    original = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    if original == "HEAD":
        original = _git(["rev-parse", "HEAD"])
    try:
        _git(["checkout", "--quiet", ref])
        out = _run(scanner)
        return {_normalize(line) for line in out.splitlines() if line.strip()}
    finally:
        _git(["checkout", "--quiet", original])


@dataclass
class NetNewResult:
    """Outcome of a net-new scan.

    `ok` is False only when the *comparison itself* could not be established (no
    merge-base, dirty tree with no worktree support) -- never merely because the
    scanner found something or exited nonzero. A scanner that finds nothing still
    produces `ok=True, net_new=[]`; a scanner that finds only pre-existing issues also
    produces `ok=True, net_new=[]`.
    """

    ok: bool
    net_new: list[str] = field(default_factory=list)
    error: str = ""


def net_new(scanner: list[str], base: str) -> NetNewResult:
    """Run `scanner` at HEAD and at the merge-base of HEAD and `base`; return the
    findings present at HEAD and absent at the merge-base."""
    if not scanner:
        return NetNewResult(ok=False, error="no scanner command given")

    merge_base = _git(["merge-base", "HEAD", base])
    if not merge_base:
        return NetNewResult(ok=False, error=f"could not find merge-base of HEAD and {base}")

    if not _worktree_supported() and _tree_is_dirty():
        return NetNewResult(
            ok=False,
            error="working tree is dirty and git worktree is unavailable; "
            "commit or stash your changes, or use a git version with worktree support",
        )

    head_findings = _findings_at_head(scanner)
    base_findings = _findings_at_base(merge_base, scanner)
    return NetNewResult(ok=True, net_new=sorted(head_findings - base_findings))
