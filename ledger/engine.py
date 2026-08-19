"""Event-sourced decision ledger on top of the jsonl store.

The Ledger is append-only. Nothing is ever mutated. The current picture is computed by
folding the event stream:

  decide     a durable call, with rationale and rejected alternatives.
  supersede  a later decide that replaces an earlier one by id, with its own rationale.
  redact     retires a decision (it stops being active) without rewriting history.

"active" is derived, never stored: a decide whose id is not the target of a later
supersede or redact. Every free-text field is redact-scanned on write; a HIGH secret
blocks the write (the store enforces this).

Scope is "org" or "repo:<name>". Org-scope decisions are the cross-repo memory; repo
scope is local to one consuming repo.

Two timestamps, deliberately distinct. `date` is when the event was appended and is
never settable -- the staleness gate and Cortex's `projected-at` clock off it, so it
has to stay monotonic with append order. `decided_at` is when the call was actually
made, and defaults to `date`. They diverge only for a seeded past decision: real
content and a real write, entered long after the fact. That gap is what makes
"decisions captured as work happens" countable separately from "decisions transcribed
from memory" -- see `CHANGELOG.md` [1.19.0]'s P-0a/P-0b split.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from lib import jsonl_store

LEDGER_FILE = "ledger/decisions.jsonl"

EventType = Literal["decide", "supersede", "redact"]


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _validate_decided_at(value: str) -> str:
    """Accept only a strict UTC `YYYY-MM-DDTHH:MM:SSZ` stamp, not in the future.

    `decided_at` records when a call was actually made, which for a seeded past
    decision is long before the event is appended. A future stamp is always an
    error: nothing can have been decided after the moment it was written down.
    """
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError(
            f"decided_at must be UTC 'YYYY-MM-DDTHH:MM:SSZ', got {value!r}"
        ) from exc
    if parsed > datetime.now(UTC):
        raise ValueError(f"decided_at {value!r} is in the future")
    return value


@dataclass
class Decision:
    """A folded, active-or-not view of a decide event plus its supersede chain."""

    id: str
    scope: str
    decision: str
    rationale: str
    alternatives_considered: list[str]
    confidence: int
    date: str
    author: str
    decided_at: str = ""
    active: bool = True
    superseded_by: str | None = None
    redacted: bool = False
    chain: list[str] = field(default_factory=list)


class Ledger:
    def __init__(self, path: str | Path = LEDGER_FILE) -> None:
        self.path = str(path)

    # ----- write paths -------------------------------------------------------

    def decide(
        self,
        decision: str,
        rationale: str,
        *,
        scope: str = "org",
        alternatives_considered: list[str] | None = None,
        confidence: int = 5,
        author: str = "unknown",
        decision_id: str | None = None,
        decided_at: str | None = None,
    ) -> str:
        """Append a decide event. Returns the new decision id."""
        if not 0 <= confidence <= 10:
            raise ValueError("confidence must be 0-10")
        did = decision_id or _new_id()
        recorded = _now_iso()
        event: dict[str, Any] = {
            "event": "decide",
            "id": did,
            "scope": scope,
            "decision": decision,
            "rationale": rationale,
            "alternatives_considered": alternatives_considered or [],
            "confidence": confidence,
            "date": recorded,
            "decided_at": _validate_decided_at(decided_at) if decided_at else recorded,
            "author": author,
        }
        jsonl_store.append(self.path, event)
        return did

    def supersede(
        self,
        target_id: str,
        new_decision: str,
        rationale: str,
        *,
        alternatives_considered: list[str] | None = None,
        confidence: int = 5,
        author: str = "unknown",
        decided_at: str | None = None,
    ) -> str:
        """Append a supersede event that replaces target_id with a new decision."""
        existing = {d.id for d in self._fold()}
        if target_id not in existing:
            raise KeyError(f"cannot supersede unknown decision id {target_id!r}")
        new_id = _new_id()
        recorded = _now_iso()
        prior = self._raw_decide(target_id)
        scope = prior["scope"] if prior else "org"
        event = {
            "event": "supersede",
            "id": new_id,
            "supersedes": target_id,
            "scope": scope,
            "decision": new_decision,
            "rationale": rationale,
            "alternatives_considered": alternatives_considered or [],
            "confidence": confidence,
            "date": recorded,
            "decided_at": _validate_decided_at(decided_at) if decided_at else recorded,
            "author": author,
        }
        jsonl_store.append(self.path, event)
        return new_id

    def redact_decision(self, target_id: str, reason: str, *, author: str = "unknown") -> None:
        """Append a redact event that retires target_id. History is preserved."""
        existing = {d.id for d in self._fold()}
        if target_id not in existing:
            raise KeyError(f"cannot redact unknown decision id {target_id!r}")
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

    def _raw_decide(self, target_id: str) -> dict[str, Any] | None:
        for ev in self._events():
            if ev.get("id") == target_id and ev.get("event") in ("decide", "supersede"):
                return ev
        return None

    def _fold(self) -> list[Decision]:
        """Fold the event stream into the current set of decisions."""
        decisions: dict[str, Decision] = {}
        order: list[str] = []
        superseded_by: dict[str, str] = {}
        redacted: set[str] = set()
        chains: dict[str, list[str]] = {}

        for ev in self._events():
            etype = ev.get("event")
            if etype in ("decide", "supersede"):
                did = ev["id"]
                decisions[did] = Decision(
                    id=did,
                    scope=ev.get("scope", "org"),
                    decision=ev.get("decision", ""),
                    rationale=ev.get("rationale", ""),
                    alternatives_considered=ev.get("alternatives_considered", []),
                    confidence=ev.get("confidence", 0),
                    date=ev.get("date", ""),
                    decided_at=ev.get("decided_at", ev.get("date", "")),
                    author=ev.get("author", "unknown"),
                )
                order.append(did)
                if etype == "supersede":
                    target = ev.get("supersedes")
                    if target:
                        superseded_by[target] = did
                        chains[did] = chains.get(target, []) + [target]
            elif etype == "redact":
                target = ev.get("redacts")
                if target:
                    redacted.add(target)

        result: list[Decision] = []
        for did in order:
            d = decisions[did]
            d.superseded_by = superseded_by.get(did)
            d.redacted = did in redacted
            d.active = d.superseded_by is None and not d.redacted
            d.chain = chains.get(did, [])
            result.append(d)
        return result

    def active(self, scope: str | None = None) -> list[Decision]:
        return [
            d
            for d in self._fold()
            if d.active and (scope is None or d.scope == scope)
        ]

    def get(self, decision_id: str) -> Decision | None:
        for d in self._fold():
            if d.id == decision_id:
                return d
        return None

    def scopes(self) -> list[str]:
        """Every distinct scope with at least one decide/supersede event, sorted."""
        return sorted({d.scope for d in self._fold()})

    def search(self, query: str, scope: str | None = None) -> list[Decision]:
        """Substring/keyword search over decision + rationale, active-first.

        Scope-filtered when scope is given. Supersede chains stay visible: a matching
        superseded decision is still returned so the chain reads end to end.
        """
        q = query.lower().strip()
        matched: list[Decision] = []
        for d in self._fold():
            if scope is not None and d.scope != scope:
                continue
            haystack = f"{d.decision}\n{d.rationale}".lower()
            if not q or q in haystack:
                matched.append(d)
        matched.sort(key=lambda d: (not d.active, d.date), reverse=False)
        # active-first: active items (False sorts before True) then by date.
        return matched
