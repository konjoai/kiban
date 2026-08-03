"""Phase 0 retroactive backfill: populate the git-derivable PR-telemetry fields for every
merge commit in a window, from git alone (Sprint P0 section 3).

Live-capture-only fields (tokens, wall clock, coverage delta, ...) are left null -- they
cannot be recovered for a past PR; see `ledger/pr_telemetry.py`'s module docstring.

AST delta and the syn-based trigger-surface/weakening-marker detectors shell out to the
`konjo-ast-diff` binary (`packages/konjo-ast-diff-rs`) per touched `.rs` file, per commit,
per the plan's explicit instruction: "trigger_surface_hits and weakening_markers need real
detectors, not regex guesses... use syn." Grep is used for exactly one thing, per the same
instruction: `continue-on-error: true` added to workflow YAML, which is not Rust and syn
cannot parse.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_AST_DIFF_BIN_CANDIDATES = (
    "packages/konjo-ast-diff-rs/target/release/konjo-ast-diff",
    "packages/konjo-ast-diff-rs/target/debug/konjo-ast-diff",
)

_PATH_CLASS_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\.github/workflows/"), "gate"),
    (re.compile(r"^\.konjo/|/\.konjo/"), "gate"),
    (re.compile(r"\.md$|^docs/|/docs/"), "docs"),
    (re.compile(r"\.(png|jpg|jpeg|gif|svg|ico|webp|woff2?|ttf)$"), "assets"),
    (re.compile(r"(^|/)(tests?|__tests__)/|_test\.rs$|test_.*\.py$|\.test\.tsx?$"), "test"),
    (re.compile(r"(^|/)(generated|dist|build|target)/|\.lock$|Cargo\.lock$"), "generated"),
    (re.compile(r"^(Cargo|package|pyproject)\.toml$|^requirements.*\.txt$"), "meta"),
    (re.compile(r"^(\.github|\.gitignore|VERSION|LICENSE|CHANGELOG)"), "meta"),
    (re.compile(r"\.(rs|py|ts|tsx|js|jsx|svelte)$"), "src"),
]

_DEP_MANIFEST_FILES = {"Cargo.toml", "package.json", "pyproject.toml", "requirements.txt"}

# Cargo.toml dependency line: `name = "version"` or `name = { version = "...", ... }`
_CARGO_DEP_RE = re.compile(r'^([A-Za-z0-9_-]+)\s*=\s*(?:"|\{)')
_NPM_DEP_LINE_RE = re.compile(r'^\s*"([A-Za-z0-9@/_.-]+)"\s*:\s*"')


def classify_path(path: str) -> str:
    for pattern, cls in _PATH_CLASS_RULES:
        if pattern.search(path):
            return cls
    return "src"


def _git(repo: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)


def list_merge_commits(repo: Path, since: str) -> list[dict]:
    """Merge commits to the default branch's history, first-parent-diffable, since a date.

    `--since` on `git log` filters by commit date; combined with `--merges` this returns
    exactly the population the plan's KT-0B stop rule counts.
    """
    proc = _git(repo, [
        "log", f"--since={since}", "--merges",
        "--format=%H|%P|%cI", "HEAD",
    ])
    out = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        sha, parents, committed_at = line.split("|", 2)
        parent_list = parents.split()
        if not parent_list:
            continue
        out.append({"sha": sha, "parent": parent_list[0], "merged_at": committed_at})
    return out


def numstat(repo: Path, sha: str) -> tuple[list[str], int, int, dict[str, tuple[int, int]]]:
    """First-parent diff numstat for a merge commit: (files, total_added, total_removed,
    per_file). Binary files report `-`/`-` for add/remove; counted as touched, 0/0 lines.
    """
    proc = _git(repo, ["show", "--numstat", "--format=", sha])
    files: list[str] = []
    per_file: dict[str, tuple[int, int]] = {}
    total_add = total_rem = 0
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added_s, removed_s, path = parts
        added = int(added_s) if added_s.isdigit() else 0
        removed = int(removed_s) if removed_s.isdigit() else 0
        files.append(path)
        per_file[path] = (added, removed)
        total_add += added
        total_rem += removed
    return files, total_add, total_rem, per_file


def crates_touched(files: list[str]) -> list[str]:
    crates: set[str] = set()
    for f in files:
        m = re.match(r"^crates/([^/]+)/", f)
        if m:
            crates.add(m.group(1))
    return sorted(crates)


def _file_at(repo: Path, sha: str, path: str) -> str | None:
    proc = _git(repo, ["show", f"{sha}:{path}"])
    if proc.returncode != 0:
        return None
    return proc.stdout


def _find_ast_diff_bin(kiban_root: Path) -> Path | None:
    for cand in _AST_DIFF_BIN_CANDIDATES:
        p = kiban_root / cand
        if p.exists():
            return p
    return None


@dataclass
class AstDeltaAggregate:
    identical: int = 0
    bodies_changed: int = 0
    signatures_changed: int = 0
    files_unparseable: list[str] = field(default_factory=list)
    trigger_surface_hits: list[str] = field(default_factory=list)
    weakening_markers: list[str] = field(default_factory=list)


def ast_delta_for_commit(
    repo: Path, sha: str, parent: str, rust_files: list[str], ast_diff_bin: Path
) -> AstDeltaAggregate:
    agg = AstDeltaAggregate()
    trigger_counts: dict[str, int] = {}
    new_allow = new_ignore = new_unsafe_total = removed_asserts_total = 0
    removed_test_fns_total = new_unwrap_total = 0

    for path in rust_files:
        before = _file_at(repo, parent, path)
        after = _file_at(repo, sha, path)
        payload = json.dumps({"before": before, "after": after})
        try:
            proc = subprocess.run(
                [str(ast_diff_bin)], input=payload, capture_output=True, text=True, timeout=30
            )
        except subprocess.TimeoutExpired:
            agg.files_unparseable.append(f"{path} (timeout)")
            continue
        if proc.returncode != 0 or not proc.stdout.strip():
            agg.files_unparseable.append(f"{path} (exit {proc.returncode})")
            continue
        try:
            delta = json.loads(proc.stdout)
        except json.JSONDecodeError:
            agg.files_unparseable.append(f"{path} (bad json)")
            continue
        if delta.get("parse_error"):
            agg.files_unparseable.append(f"{path} ({delta['parse_error']})")
            continue

        agg.identical += delta.get("identical", 0)
        agg.bodies_changed += delta.get("bodies_changed", 0)
        agg.signatures_changed += delta.get("signatures_changed", 0)
        new_unsafe_total += delta.get("new_unsafe", 0)
        new_unwrap_total += delta.get("new_unwrap", 0)
        new_allow += delta.get("new_attrs_allow", 0)
        new_ignore += delta.get("new_attrs_ignore", 0)
        removed_asserts_total += delta.get("removed_asserts", 0)
        removed_test_fns_total += delta.get("removed_test_fns", 0)
        for cat, n in (delta.get("trigger_surface") or {}).items():
            trigger_counts[cat] = trigger_counts.get(cat, 0) + n

    if new_unsafe_total:
        agg.trigger_surface_hits.append(f"unsafe:{new_unsafe_total}")
    for cat, n in sorted(trigger_counts.items()):
        agg.trigger_surface_hits.append(f"{cat}:{n}")

    if new_allow:
        agg.weakening_markers.append(f"allow:{new_allow}")
    if new_ignore:
        agg.weakening_markers.append(f"ignore:{new_ignore}")
    if removed_asserts_total:
        agg.weakening_markers.append(f"removed_assert:{removed_asserts_total}")
    if removed_test_fns_total:
        agg.weakening_markers.append(f"removed_test_fn:{removed_test_fns_total}")
    if new_unwrap_total:
        # Heuristic, stated as such: a new `.unwrap()`/`.expect()` is not necessarily a
        # `?` converted to an unwrap (it could be new code with no prior `?` at all).
        # Counted as a weakening signal anyway per the plan's marker list, labelled so a
        # reader does not mistake it for a precise "conversion detected" claim.
        agg.weakening_markers.append(f"new_unwrap_or_expect (heuristic):{new_unwrap_total}")

    return agg


_CONTINUE_ON_ERROR_RE = re.compile(r"^\+\s*continue-on-error:\s*true", re.MULTILINE)


def continue_on_error_added(repo: Path, sha: str, workflow_files: list[str]) -> bool:
    """The one grep-based detector the plan permits: `continue-on-error: true` added to
    workflow YAML. Not Rust, so syn does not apply.
    """
    if not workflow_files:
        return False
    proc = _git(repo, ["show", sha, "--", *workflow_files])
    return bool(_CONTINUE_ON_ERROR_RE.search(proc.stdout))


def new_dependencies_for_commit(repo: Path, sha: str, files: list[str]) -> list[str]:
    """New dependency names added to a manifest file, from the added-line text of the
    diff. Best-effort textual scan (manifests are TOML/JSON, not Rust; syn does not apply,
    and this is not one of the two categories the plan restricts to syn/grep-only), so a
    dependency added inside a nested table this regex doesn't anticipate can be missed --
    stated as a known limitation, not silently assumed complete.
    """
    manifest_files = [f for f in files if Path(f).name in _DEP_MANIFEST_FILES]
    if not manifest_files:
        return []
    proc = _git(repo, ["show", sha, "--", *manifest_files])
    names: set[str] = set()
    for line in proc.stdout.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        added = line[1:]
        m = _CARGO_DEP_RE.match(added.strip())
        if m and m.group(1) not in ("version", "edition", "name", "description", "license"):
            names.add(m.group(1))
            continue
        m2 = _NPM_DEP_LINE_RE.match(added)
        if m2:
            names.add(m2.group(1))
    return sorted(names)
