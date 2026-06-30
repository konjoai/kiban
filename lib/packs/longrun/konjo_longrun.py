"""konjo_longrun: the checkpoint/resume helper for long-running scripts.

A long run (a benchmark, an ablation, a training loop, an eval matrix) must be able to die
and resume without losing finished work. The protocol, from the evolution plan section 6:

  1. Accept --resume (resume from the latest checkpoint) and --fresh (ignore checkpoints and
     start clean). Exactly one is the script's default; the other is explicit.
  2. Write a checkpoint after each unit of work, not only at the end.
  3. On resume, read the progress file, compute the completed units, and skip them.
  4. Be idempotent at the unit level: re-running a unit overwrites, not duplicates, its
     result.

The progress file is one JSONL on `jsonl_store`: atomic appends, injection-safe,
redact-scanned, and tolerant on read (one corrupt line never bricks the resume, which is
exactly the property `jsonl_store.iter_read` gives). A benchmark adopts resume like this:

    p = argparse.ArgumentParser()
    konjo_longrun.add_resume_args(p, default_fresh=False)   # resume is the default
    args = p.parse_args()
    ckpt = konjo_longrun.Checkpoint(progress_path, fresh=konjo_longrun.is_fresh(args))
    for unit in units:
        key = unit_key(unit)
        if ckpt.done(key):
            continue
        ckpt.mark(key, run_unit(unit))

Pass an absolute progress path to control where the file lands; a relative path resolves
under the konjo state dir (like every other store file).
"""

from __future__ import annotations

import argparse
import os
from typing import Any

from lib import jsonl_store


class Checkpoint:
    """A resumable progress log: one append per completed unit, folded latest-wins on read.

    The fold gives unit-level idempotency: re-marking a unit overwrites its result in the
    derived view, exactly as the Ledger folds supersedes. `done` and `completed` read the
    folded view, so a resumed run skips every unit already finished.
    """

    def __init__(self, path: str | os.PathLike[str], *, fresh: bool = False) -> None:
        self.path = str(path)
        if fresh:
            # Start clean: ignore (and clear) any prior checkpoints for this run.
            jsonl_store.rewrite_atomic(self.path, [])
        self._results: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for rec in jsonl_store.iter_read(self.path):
            key = rec.get("unit")
            if isinstance(key, str):
                results[key] = rec.get("result")  # latest line wins -> idempotent
        return results

    def done(self, unit_key: str) -> bool:
        """True if this unit was already completed in a prior (or this) run."""
        return unit_key in self._results

    def mark(self, unit_key: str, result: Any = None) -> None:
        """Record a unit as complete. Appended to the progress file and reflected at once."""
        if not isinstance(unit_key, str) or not unit_key:
            raise ValueError("unit_key must be a non-empty string")
        jsonl_store.append(self.path, {"unit": unit_key, "result": result})
        self._results[unit_key] = result

    def completed(self) -> set[str]:
        """The set of completed unit keys."""
        return set(self._results)

    def results(self) -> dict[str, Any]:
        """The folded {unit_key: result} view, latest write per unit."""
        return dict(self._results)


_DEFAULT_FRESH_ATTR = "_longrun_default_fresh"


def add_resume_args(
    parser: argparse.ArgumentParser, *, default_fresh: bool = False
) -> argparse.ArgumentParser:
    """Add a mutually exclusive --resume / --fresh pair.

    `default_fresh` declares which mode the script uses when neither flag is given: the
    plan's "exactly one is the default per script; the other is explicit." Pass
    default_fresh=False for a resume-by-default script, True for a fresh-by-default one.
    """
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--resume", action="store_true", help="resume from the latest checkpoint"
    )
    group.add_argument(
        "--fresh", action="store_true", help="ignore checkpoints and start clean"
    )
    parser.set_defaults(**{_DEFAULT_FRESH_ATTR: default_fresh})
    return parser


def is_fresh(args: argparse.Namespace) -> bool:
    """Resolve the run mode from parsed args: an explicit flag wins, else the declared
    default. Returns True for a fresh run, False to resume."""
    if getattr(args, "fresh", False):
        return True
    if getattr(args, "resume", False):
        return False
    return bool(getattr(args, _DEFAULT_FRESH_ATTR, False))
