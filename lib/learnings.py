"""The learnings log: the second half of the lab notebook, on the shared substrate.

The Ledger records decisions (what we chose and why). The learnings log records the other
half the compounding loop needs: when the agent errs, the mistake is turned into a durable
rule so the class of mistake does not recur. A correction that only fixes this run is a
patch; a correction that edits the rules is a fix. This log is where the fix is recorded.

A learning is four things:
  mistake      one-line statement of what went wrong.
  rule         the rule that prevents it from recurring.
  enforcement  where that rule now lives: a CLAUDE.md line, a prose-lint word, a new
               specialist lane, or a gate. THIS IS LOAD-BEARING.
  scope        org (cross-repo) or repo:<name>.

The guardrail that keeps this from becoming a diary: a learning MUST name an enforcement
target. A learning with no enforcement target is not a learning, it is a note, and notes do
not go in the log. `learn` refuses one. This ties every entry to mechanism.

The log is append-only and event-sourced, exactly like the Ledger: nothing is mutated;
"active" is folded from the stream; redact retires an entry without rewriting history. Every
free-text field is redact-scanned on write by the store; a HIGH secret blocks the write.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from lib import jsonl_store

LEARNINGS_FILE = "ledger/learnings.jsonl"

EventType = Literal["learn", "redact"]


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class MissingEnforcement(ValueError):
    """A learning was logged with no enforcement target. It is a note, not a learning."""


@dataclass
class Learning:
    """A folded view of a learn event: a mistake, its preventing rule, and where the rule
    now lives."""

    id: str
    scope: str
    mistake: str
    rule: str
    enforcement: str
    date: str
    author: str
    active: bool = True
    redacted: bool = False


class LearningsLog:
    def __init__(self, path: str | Path = LEARNINGS_FILE) -> None:
        self.path = str(path)

    # ----- write paths -------------------------------------------------------

    def learn(
        self,
        mistake: str,
        rule: str,
        enforcement: str,
        *,
        scope: str = "org",
        author: str = "unknown",
        learning_id: str | None = None,
    ) -> str:
        """Append a learn event. Returns the new learning id.

        Refuses (MissingEnforcement) when the enforcement target is blank: a learning must
        name where its rule lives, or it is a note. The mistake and rule are also required.
        """
        mistake = (mistake or "").strip()
        rule = (rule or "").strip()
        enforcement = (enforcement or "").strip()
        if not mistake:
            raise ValueError("a learning needs a one-line mistake")
        if not rule:
            raise ValueError("a learning needs the rule that prevents the mistake")
        if not enforcement:
            raise MissingEnforcement(
                "a learning must name where its rule lives (the enforcement target: a "
                "CLAUDE.md line, a prose-lint word, a new lane, or a gate). A learning with "
                "no enforcement target is a note, not a learning, and notes do not go in the "
                "log."
            )
        lid = learning_id or _new_id()
        event: dict[str, Any] = {
            "event": "learn",
            "id": lid,
            "scope": scope,
            "mistake": mistake,
            "rule": rule,
            "enforcement": enforcement,
            "date": _now_iso(),
            "author": author,
        }
        jsonl_store.append(self.path, event)
        return lid

    def redact_learning(self, target_id: str, reason: str, *, author: str = "unknown") -> None:
        """Append a redact event that retires target_id. History is preserved."""
        existing = {learning.id for learning in self._fold()}
        if target_id not in existing:
            raise KeyError(f"cannot redact unknown learning id {target_id!r}")
        event = {
            "event": "redact",
            "id": _new_id(),
            "redacts": target_id,
            "reason": reason,
            "date": _now_iso(),
            "author": author,
        }
        jsonl_store.append(self.path, event)

    # ----- read paths --------------------------------------------------------

    def _events(self) -> list[dict[str, Any]]:
        return jsonl_store.read(self.path)

    def _fold(self) -> list[Learning]:
        """Fold the event stream into the current set of learnings."""
        learnings: dict[str, Learning] = {}
        order: list[str] = []
        redacted: set[str] = set()

        for ev in self._events():
            etype = ev.get("event")
            if etype == "learn":
                lid = ev["id"]
                learnings[lid] = Learning(
                    id=lid,
                    scope=ev.get("scope", "org"),
                    mistake=ev.get("mistake", ""),
                    rule=ev.get("rule", ""),
                    enforcement=ev.get("enforcement", ""),
                    date=ev.get("date", ""),
                    author=ev.get("author", "unknown"),
                )
                order.append(lid)
            elif etype == "redact":
                target = ev.get("redacts")
                if target:
                    redacted.add(target)

        result: list[Learning] = []
        for lid in order:
            learning = learnings[lid]
            learning.redacted = lid in redacted
            learning.active = not learning.redacted
            result.append(learning)
        return result

    def active(self, scope: str | None = None) -> list[Learning]:
        return [
            learning
            for learning in self._fold()
            if learning.active and (scope is None or learning.scope == scope)
        ]

    def get(self, learning_id: str) -> Learning | None:
        for learning in self._fold():
            if learning.id == learning_id:
                return learning
        return None

    def search(self, query: str, scope: str | None = None) -> list[Learning]:
        """Substring/keyword search over mistake + rule + enforcement, active-first.

        Scope-filtered when scope is given. A redacted learning still surfaces under --all
        callers (the engine returns it; the CLI filters), so the history reads end to end.
        """
        q = query.lower().strip()
        matched: list[Learning] = []
        for learning in self._fold():
            if scope is not None and learning.scope != scope:
                continue
            haystack = f"{learning.mistake}\n{learning.rule}\n{learning.enforcement}".lower()
            if not q or q in haystack:
                matched.append(learning)
        matched.sort(key=lambda learning: (not learning.active, learning.date))
        return matched
