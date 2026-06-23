"""Recorded cassettes: a deterministic, offline backend for the eval gate.

The Phase 1 eval defaulted to the live Claude CLI, which CI cannot run (no auth, no
network) and which is non-deterministic. Cassettes fix that: record each specialist's
reply once from the real backend, key it by (specialist, prompt-hash), and replay those
replies in CI with no model and no network.

  RecordingBackend  wraps the live backend, captures every reply into a dict.
  ReplayBackend     serves captured replies; a miss is a hard error (stale cassette),
                    so a drifted prompt cannot silently pass as zero findings.

The key is a hash of (specialist, system_prompt, user_prompt). The red-team prompt
embeds the other specialists' findings, but in replay those are themselves deterministic
replays, so the red-team prompt-hash is stable too.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lib.review import ReviewBackend

CASSETTE_DIR = Path(__file__).resolve().parent / "cassettes"


class CassetteMiss(KeyError):
    """A replay had no recorded reply for a prompt. The cassette is stale."""


def cassette_key(specialist: str, system_prompt: str, user_prompt: str) -> str:
    raw = f"{specialist}\n--SYS--\n{system_prompt}\n--USR--\n{user_prompt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class RecordingBackend:
    """Wrap a live backend and capture every reply keyed by prompt-hash."""

    def __init__(self, inner: ReviewBackend) -> None:
        self.inner = inner
        self.data: dict[str, str] = {}

    def dispatch(
        self, specialist: str, system_prompt: str, user_prompt: str, *, model: str | None = None
    ) -> str:
        reply = self.inner.dispatch(specialist, system_prompt, user_prompt, model=model)
        self.data[cassette_key(specialist, system_prompt, user_prompt)] = reply
        return reply


class ReplayBackend:
    """Serve recorded replies. No network, no process. A miss is a hard error."""

    def __init__(self, data: dict[str, str]) -> None:
        self.data = data

    def dispatch(
        self, specialist: str, system_prompt: str, user_prompt: str, *, model: str | None = None
    ) -> str:
        key = cassette_key(specialist, system_prompt, user_prompt)
        if key not in self.data:
            raise CassetteMiss(
                f"no recorded reply for specialist {specialist!r} (key {key}). "
                "Re-record with: konjo-eval record"
            )
        return self.data[key]


def _safe(name: str) -> str:
    return name.replace("/", "__").replace(" ", "_")


def save_cassette(
    fixture_name: str, data: dict[str, str], cassette_dir: Path = CASSETTE_DIR
) -> Path:
    cassette_dir.mkdir(parents=True, exist_ok=True)
    path = cassette_dir / f"{_safe(fixture_name)}.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_cassettes(cassette_dir: Path = CASSETTE_DIR) -> dict[str, str]:
    """Merge every cassette file in the directory into one key -> reply map."""
    merged: dict[str, str] = {}
    if not cassette_dir.exists():
        return merged
    for path in sorted(cassette_dir.glob("*.json")):
        try:
            merged.update(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return merged


def cassettes_present(cassette_dir: Path = CASSETTE_DIR) -> bool:
    return cassette_dir.exists() and any(cassette_dir.glob("*.json"))
