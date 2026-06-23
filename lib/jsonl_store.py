"""Injection-hardened, atomic, redact-scanned append-only JSONL store.

This is the shared substrate under the Ledger and any future review/learning log.
Every line is exactly one JSON object. The store is the single choke point where two
classes of bad data are stopped before they ever land on disk:

  1. prompt-injection-shaped payloads (raise InjectionRejected)
  2. HIGH-tier secrets (raise SecretRejected via redact.has_high)

Reads are tolerant: a single corrupt line is skipped with a warning, not fatal, so one
bad write can never brick the whole log.

State files live under the state dir (default ~/.konjo/state). Override with the
KONJO_STATE_DIR env var, which is what the tests use.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from . import redact

logger = logging.getLogger("kiban.jsonl_store")

DEFAULT_STATE_DIR = Path.home() / ".konjo" / "state"


class StoreError(Exception):
    """Base for store write rejections."""


class InjectionRejected(StoreError):
    """The serialized payload looked like instruction injection."""


class SecretRejected(StoreError):
    """The payload carried a HIGH-tier secret."""


# Patterns that signal an attempt to smuggle instructions into the log so a later
# reader (human or model) re-ingests them as commands. Conservative on purpose: these
# match phrasing that has no business inside a structured decision record.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)\bignore\s+(?:all\s+)?(?:your\s+)?previous\s+instructions?\b"),
    re.compile(r"(?i)\bdisregard\s+(?:all\s+)?(?:the\s+)?(?:above|prior|previous)\b"),
    re.compile(r"(?i)\byou\s+are\s+now\s+(?:a|an|in)\b"),
    re.compile(r"(?i)\bnew\s+system\s+prompt\b"),
    # Chat/tool role markers that should never appear verbatim in a record.
    re.compile(r"(?i)<\|(?:im_start|im_end|system|assistant|user)\|>"),
    re.compile(r"(?im)^\s*(?:system|assistant|user|tool)\s*:\s", ),
    re.compile(r"(?i)<\s*/?\s*(?:tool_call|function_call|tool_result)\s*>"),
]


def state_dir() -> Path:
    """The base directory for all store files. Env-overridable for tests."""
    override = os.environ.get("KONJO_STATE_DIR")
    return Path(override) if override else DEFAULT_STATE_DIR


def _resolve(path: str | os.PathLike[str]) -> Path:
    """Relative paths resolve under the state dir; absolute paths are honored as-is."""
    p = Path(path)
    return p if p.is_absolute() else state_dir() / p


def _looks_like_injection(payload: str) -> bool:
    return any(pat.search(payload) for pat in _INJECTION_PATTERNS)


def append(path: str | os.PathLike[str], obj: dict[str, Any]) -> Path:
    """Atomically append one JSON object as a line. Scans before writing.

    Raises SecretRejected if the payload carries a HIGH secret, InjectionRejected if it
    looks like instruction injection. The line is serialized compactly with a trailing
    newline. The append is a single O_APPEND write, which is atomic for one line on
    local filesystems.
    """
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

    if redact.has_high(line):
        raise SecretRejected("payload contains a HIGH-tier secret; write blocked")
    if _looks_like_injection(line):
        raise InjectionRejected("payload looks like instruction injection; write blocked")

    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # O_APPEND guarantees the write lands at end-of-file even under concurrent writers.
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, (line + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    return target


def read(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Read all valid records. One corrupt line is skipped with a warning, not fatal."""
    return list(iter_read(path))


def iter_read(path: str | os.PathLike[str]) -> Iterator[dict[str, Any]]:
    """Stream valid records. Tolerant of corrupt lines."""
    target = _resolve(path)
    if not target.exists():
        return
    with target.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("skipping corrupt line %d in %s", lineno, target)
                continue
            if isinstance(obj, dict):
                yield obj
            else:
                logger.warning("skipping non-object line %d in %s", lineno, target)


def rewrite_atomic(path: str | os.PathLike[str], objs: list[dict[str, Any]]) -> Path:
    """Replace a file's contents atomically via write-tmp-then-rename.

    Used only by maintenance paths (never by the append-only event flow). Each object
    is re-scanned so a rewrite cannot launder a secret or injection in.
    """
    for obj in objs:
        line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        if redact.has_high(line):
            raise SecretRejected("rewrite payload contains a HIGH-tier secret")
        if _looks_like_injection(line):
            raise InjectionRejected("rewrite payload looks like instruction injection")

    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for obj in objs:
                fh.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
                fh.write("\n")
        os.replace(tmp_name, target)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
    return target
