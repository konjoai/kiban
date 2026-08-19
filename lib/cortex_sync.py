"""Best-effort fold-commit-push into the local Cortex clone.

Runs after a Ledger write (`konjo-decision decide` / `supersede` / `redact`) so any
surface with `konjo-cortex` cloned -- laptop, cloud session, phone routine -- pushes
what it just wrote without a separate manual step. The event is already durably
written to disk by the time this runs, so a fold, commit, or push failure here must
never make the write itself look like it failed: every failure is caught and
reported to stderr, never raised. This is the same contract
`plugins/konjo/hooks/cortex_fold_push.sh` has always had; this module is what lets
that contract run inline, at write time, on surfaces (cloud, phone) that never fire
a Claude Code session-end hook at all.

Fold and push are kept as separate steps on purpose (Sprint K5 Phase 2): a push
failure must not undo, retry, or block on the fold, and a fold failure must not
attempt to commit half-rendered pages.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ledger.engine import Ledger
from lib import cortex


def _warn(msg: str) -> None:
    print(f"cortex_sync: {msg}", file=sys.stderr)


def fold(ledger: Ledger, dest_dir: Path) -> bool:
    """Re-render every scope into dest_dir. Returns True on success, never raises."""
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        for scope in ledger.scopes():
            page = cortex.render_scope(ledger, scope)
            (dest_dir / f"{cortex.scope_slug(scope)}.md").write_text(page, encoding="utf-8")
        return True
    except Exception as exc:  # noqa: BLE001 -- must never propagate, see module docstring
        _warn(f"fold failed -- Cortex not re-folded, left as-is ({exc})")
        return False


def commit_and_push(dest_dir: Path) -> None:
    """Commit and push dest_dir if it has changes. Every failure is swallowed."""
    if not (dest_dir / ".git").is_dir():
        return
    try:
        status = subprocess.run(
            ["git", "-C", str(dest_dir), "status", "--porcelain"],
            capture_output=True, text=True, timeout=30,
        )
        if status.returncode != 0 or not status.stdout.strip():
            return
        subprocess.run(["git", "-C", str(dest_dir), "add", "-A"], check=True, timeout=30)
        commit = subprocess.run(
            ["git", "-C", str(dest_dir), "commit", "-q", "-m", "cortex: re-fold from Ledger"],
            capture_output=True, text=True, timeout=30,
        )
        if commit.returncode != 0:
            _warn(f"commit failed -- left uncommitted in {dest_dir} for manual review")
            return
    except Exception as exc:  # noqa: BLE001
        _warn(f"commit failed -- left uncommitted in {dest_dir} for manual review ({exc})")
        return
    try:
        push = subprocess.run(
            ["git", "-C", str(dest_dir), "push"], capture_output=True, text=True, timeout=60,
        )
        if push.returncode != 0:
            _warn(f"push failed -- commit is local in {dest_dir}, push manually")
    except Exception as exc:  # noqa: BLE001
        _warn(f"push failed -- commit is local in {dest_dir}, push manually ({exc})")


def sync(ledger: Ledger, dest_dir: Path) -> None:
    """Fold then commit-and-push, best-effort. No-op if dest_dir isn't a git clone."""
    if not (dest_dir / ".git").is_dir():
        return
    if not fold(ledger, dest_dir):
        return
    commit_and_push(dest_dir)
