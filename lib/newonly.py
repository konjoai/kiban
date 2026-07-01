"""newonly: report only net-new scanner findings versus a base ref.

This is the engine behind the `konjo-newonly` CLI and every `repo:*` gate in
konjo-gates that shells out to an external scanner (ruff, cargo clippy, cargo deny,
...). It runs the scanner on the current working tree (HEAD plus any local changes)
and on the merge-base of HEAD and a given base ref, then diffs the two finding sets
line-insensitively (line numbers normalized away, and each scan's own root directory
stripped away). Only findings present at HEAD and absent at the merge-base are net-new.

konjo-gates imports `net_new` directly and runs it in-process. It used to shell out to
the `bin/konjo-newonly` script instead, resolved via a path computed from the installed
package location -- a path that only exists in a source checkout. Once kiban ships as a
pip package (the root distribution, see pyproject.toml), that script is not on disk at
the computed path, so every repo-native gate crashed instantly (python's own missing
file error, `returncode != 0`, empty stdout) and got folded into a generic "net-new
findings" failure regardless of the real diff. Importing this module directly removes
the vanished-path failure mode entirely: `lib` is part of the installed distribution.

Fixing that unmasked a second, independent bug: tools that print absolute
paths (`cargo fmt --check`, `cargo clippy`, `cargo deny check`) root those paths at the
scanner's cwd. HEAD is scanned in the real checkout; the base ref is scanned in a
throwaway `git worktree` under a random `tempfile.mkdtemp()` path -- a different root
every run. A finding on an untouched file at an identical line was therefore never
recognized as pre-existing: its HEAD-side and base-side strings differed only in the
leading absolute path, so `head - base` kept it forever, and every Rust PR failed on
the *entire* repo's pre-existing lint backlog, not its own diff. `_normalize` now takes
the root each scan actually ran from and strips it before comparing.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

_LOCATION_RE = re.compile(r"^([^\s:]+):\d+(?::\d+)?")
# \b requires a boundary on BOTH sides of the digit run, but a digit immediately
# followed by a letter (a unit suffix: "12.94s", "1s build + 5s test", "12m") is
# word-to-word -- no boundary, no match -- so the trailing \b\d+\b alone leaves
# compile/test durations untouched. cargo's own build output prints exactly these
# ("Finished ... in 12.94s"; cargo-mutants' "in 1s build + 5s test" is part of every
# finding line), so a nondeterministic wall-clock duration made otherwise-identical
# HEAD/base output compare as different -- a false net-new on every run for any tool
# that compiles (clippy, cargo-mutants), never for one that doesn't (fmt-check,
# cargo-deny). The unit suffix is consumed as part of the match so the trailing \b is
# checked after it, not immediately after the bare digits.
_NUM_RE = re.compile(r"\b\d+(?:\.\d+)?(?:ms|min|ns|s|m|h)?\b")

# Matches a CSI (ANSI SGR) escape sequence, e.g. "\x1b[0m", "\x1b[1;94m". `dtolnay/
# rust-toolchain` forces CARGO_TERM_COLOR=always whenever the caller hasn't already
# set it, so every `cargo clippy` diagnostic ships pretty-printed with color codes
# wrapped around the source-snippet line-number gutter: "\x1b[94m221\x1b[0m | ...".
# Left in place, these sequences defeat `_NUM_RE`'s own \b boundary check -- "94" in
# "\x1b[94m221" is glued to the preceding "m" (word-to-word, no \b) so it is never
# consumed as part of a unit suffix or stripped, and the *actual* line number ("221")
# immediately follows a "m" too, so `_NUM_RE` cannot normalize it away either. That is
# exactly the number `_NUM_RE` exists to normalize: a pre-existing, byte-for-byte
# unchanged clippy finding whose line merely shifted because the PR added or removed
# lines earlier in the same file. Stripping ANSI sequences first, before any other
# normalization, restores plain "221 | ..." so the existing numeric normalization can
# do its job.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# cargo (and tools built on cargo's `Shell::status`, like cargo-deny/cargo-mutants)
# prints its own build/fetch progress as a right-justified verb + message, e.g.
# "   Compiling foo v1.2.3" / "    Checking bar v0.4.0 (crates.io)" / "    Finished
# dev profile ...". This is not a diagnostic -- it carries no finding -- but the raw
# stdout+stderr capture treats every non-blank line as a candidate finding. The HEAD
# scan runs in the real checkout (a warm, possibly cache-restored `target/`); the
# base-ref scan runs in a throwaway `git worktree` with no cache at all, so it always
# starts a colder build. Which crates get a fresh "Compiling"/"Checking" line is a
# function of that incremental-build cache state, not of the diff being scanned --
# so for any tool that compiles, this noise can differ between the two scans on
# genuinely unmodified source and shows up as a permanent false net-new. Filtered out
# entirely rather than normalized, since it carries no content worth comparing.
_CARGO_STATUS_RE = re.compile(
    r"^(?:Compiling|Checking|Downloading|Downloaded|Fresh|Ignored|Updating|Adding|"
    r"Removing|Fetching|Packaging|Verifying|Archiving|Publishing|Uploading|Signing|"
    r"Testing|Doc-tested|Documenting|Running|Finished|Replacing|Unpacking|Blocking|"
    r"Waiting|Locking|Installing|Compiled|Summary|Created|Migrating)\b"
)


def _strip_ansi(line: str) -> str:
    return _ANSI_RE.sub("", line)


def _is_build_noise(line: str) -> bool:
    return bool(_CARGO_STATUS_RE.match(_strip_ansi(line).strip()))


# Vars that point a build tool at a cache/output directory outside the scan's own cwd.
# If CI sets one of these globally (a common caching optimization), the HEAD scan (the
# real checkout) and the base-ref scan (a throwaway worktree at an unrelated path) would
# both write into it -- sharing one crate's incremental compilation state across two
# different git states scanned back-to-back. Unlike the root-stripping fix above, this
# isn't cosmetic: a shared cache can make a compiling tool (cargo clippy, cargo mutants)
# emit genuinely different diagnostics for the same unmodified source, an unremovable
# false net-new. Non-compiling tools (cargo fmt --check, cargo deny check) never read
# these vars, so scrubbing them is a no-op for those.
_CACHE_DIR_ENV_VARS = ("CARGO_TARGET_DIR",)


def _scan_env() -> dict[str, str]:
    """A subprocess environment with shared build-cache vars scrubbed.

    Removing rather than repointing them lets each tool fall back to its own
    cwd-relative default (e.g. cargo's `<cwd>/target`), which is what actually
    isolates one scan's build state from the other's regardless of `cwd`.
    """
    env = os.environ.copy()
    for var in _CACHE_DIR_ENV_VARS:
        env.pop(var, None)
    return env


def _normalize(line: str, root: str | None = None) -> str:
    line = _strip_ansi(line.rstrip("\n"))
    if root:
        # Both a bare root and a trailing-slash root appear (a path exactly equal to
        # root, vs. root + "/rest/of/path"); strip both so head/base findings for an
        # untouched file compare equal regardless of which absolute directory each
        # scan ran from.
        line = line.replace(root.rstrip("/") + "/", "")
        line = line.replace(root, ".")
    line = _LOCATION_RE.sub(lambda m: m.group(1) + ":N", line)
    line = _NUM_RE.sub("N", line)
    return line.strip()


def _run(cmd: list[str], cwd: str | None = None) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=_scan_env())
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


def _findings_at_head(scanner: list[str], root: str) -> set[str]:
    """Scan the current working tree (HEAD plus any local changes) in place."""
    out = _run(scanner, cwd=root)
    return {
        _normalize(line, root)
        for line in out.splitlines()
        if line.strip() and not _is_build_noise(line)
    }


def _findings_at_base(ref: str, scanner: list[str]) -> set[str] | None:
    """Scan the base ref WITHOUT touching the user's working tree (C3).

    Preferred path: check the ref out into a throwaway `git worktree` and run the
    scanner there. The caller's tree is never modified, so this is safe even with
    uncommitted changes. If worktrees are unavailable, the caller has already gated on
    a clean tree, so this falls back to an in-place checkout-and-restore.

    Returns None (rather than an empty set) when the comparison itself could not be
    established -- e.g. `git worktree add` failed -- so the caller can surface a real
    error instead of silently treating "the scan didn't run" as "nothing was found",
    which would flag every HEAD-side finding as net-new.
    """
    if _worktree_supported():
        tmp = tempfile.mkdtemp(prefix="konjo-newonly-")
        try:
            if not _git_ok(["worktree", "add", "--quiet", "--detach", tmp, ref]):
                return None
            out = _run(scanner, cwd=tmp)
            return {
                _normalize(line, tmp)
                for line in out.splitlines()
                if line.strip() and not _is_build_noise(line)
            }
        finally:
            _git(["worktree", "remove", "--force", tmp])
            shutil.rmtree(tmp, ignore_errors=True)

    # Fallback: in-place checkout. Only reached on a clean tree (gated by the caller).
    # No worktree means no separate root, so head and base share the same cwd and no
    # path-stripping is needed here.
    original = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    if original == "HEAD":
        original = _git(["rev-parse", "HEAD"])
    try:
        _git(["checkout", "--quiet", ref])
        out = _run(scanner)
        return {
            _normalize(line)
            for line in out.splitlines()
            if line.strip() and not _is_build_noise(line)
        }
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

    head_root = _git(["rev-parse", "--show-toplevel"]) or "."
    head_findings = _findings_at_head(scanner, head_root)
    base_findings = _findings_at_base(merge_base, scanner)
    if base_findings is None:
        return NetNewResult(ok=False, error=f"could not scan the base ref ({merge_base})")
    return NetNewResult(ok=True, net_new=sorted(head_findings - base_findings))
