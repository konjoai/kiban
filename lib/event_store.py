"""Injection-hardened, atomic, redact-scanned one-event-per-file store.

Sibling to `lib/jsonl_store` for the Konjo Ledger's per-file event format (Sprint
K5). A shared append-only JSONL file conflicts at the last line on every concurrent
write -- exactly the one place a merge tool cannot resolve safely. This store makes
that conflict structurally impossible: every event is its own file, named by the
event's own id, inside a directory. Two writers adding two events add two files;
there is nothing left for git to merge.

Append-only semantics carry over unchanged: an event file is never edited or
deleted by this module. `supersede` and `redact` are still just events that
reference an earlier id -- the fold (`ledger/engine.py`) does the interpreting, not
this layer.

Directory listing replaces line reading. That is fine at the sizes this store is
used at today; see `ledger/schema.md` for the stated ceiling. This module does not
attempt to solve for it.

Atomicity is write-tmp-then-link, not O_APPEND (jsonl_store's guarantee does not
carry over for free -- a per-file writer has a different failure mode: two writers
racing on the *same id* rather than two writers racing on the *same line*). A temp
file is written and fsynced in the target directory, then `os.link`'d into place
under its final name: `os.link` is an atomic create-only operation on POSIX -- it
raises `FileExistsError` rather than silently overwriting, which is what makes this
append-only rather than merely atomic. The temp file is unlinked either way.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from . import jsonl_store

logger = logging.getLogger("kiban.event_store")


class EventExists(jsonl_store.StoreError):
    """An event file with this id already exists -- the store is append-only."""


def _resolve(path: str | os.PathLike[str]) -> Path:
    return jsonl_store._resolve(path)


def write_event(dir_path: str | os.PathLike[str], event_id: str, obj: dict[str, Any]) -> Path:
    """Atomically write one event as `<event_id>.json` inside dir_path.

    Raises SecretRejected / InjectionRejected (same gate as `jsonl_store.append`,
    via `jsonl_store.check_payload`) and `EventExists` if the id is already on disk.
    """
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    jsonl_store.check_payload(payload)

    target_dir = _resolve(dir_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / f"{event_id}.json"

    fd, tmp_name = tempfile.mkstemp(dir=str(target_dir), prefix=f".{event_id}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_name, 0o600)
        try:
            os.link(tmp_name, dest)
        except FileExistsError:
            raise EventExists(f"event {event_id!r} already exists at {dest}") from None
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return dest


def iter_events(dir_path: str | os.PathLike[str]) -> Iterator[dict[str, Any]]:
    """Stream valid events from dir_path. Tolerant of one corrupt file, like jsonl_store."""
    target_dir = _resolve(dir_path)
    if not target_dir.exists():
        return
    for entry in sorted(target_dir.iterdir()):
        if entry.suffix != ".json" or entry.name.startswith("."):
            continue
        try:
            obj = json.loads(entry.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("skipping corrupt event file %s", entry)
            continue
        if isinstance(obj, dict):
            yield obj
        else:
            logger.warning("skipping non-object event file %s", entry)


def read_events(dir_path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Read all valid events. One corrupt file is skipped with a warning, not fatal."""
    return list(iter_events(dir_path))
