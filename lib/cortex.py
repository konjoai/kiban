"""Cortex: fold a Ledger scope into a markdown read model.

The JSONL stream (`ledger/engine.py`) stays canonical. This module only renders what
`Ledger._fold()` already computes -- no new write path, no mutation of the event
stream. One page per scope: active decisions first (with prior chain members rendered
inline, full fields preserved), then a Retired section for redacted decisions
(excluded from active, not erased).

Idempotent by construction: `projected-at` is the newest event's own timestamp in
scope, not wall-clock time, so folding the same stream twice produces byte-identical
markdown. This is also exactly what the staleness gate needs: a page is stale once a
newer event lands in its scope than the timestamp stamped on the page
(`lib.doc_staleness.check_projection`).
"""

from __future__ import annotations

from ledger.engine import Decision, Ledger


def _newest_event_at(decisions: list[Decision]) -> str:
    dates = [d.date for d in decisions if d.date]
    return max(dates) if dates else ""


def _redact_reasons(ledger: Ledger) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for ev in ledger._events():
        if ev.get("event") == "redact":
            target = ev.get("redacts")
            if target:
                reasons[target] = ev.get("reason", "")
    return reasons


def _fmt_alts(alts: list[str]) -> str:
    """Quote each alternative so a comma inside one cannot read as a separator.

    Plain ", ".join loses the boundary: two alternatives that each contain a comma
    render as four fragments, and the reader cannot tell which was actually
    rejected. The rejected options are half the value of a decision record at
    recall time, so this is a correctness problem, not a formatting preference.
    """
    return ", ".join(f'"{a}"' for a in alts) if alts else "none"


def _render_member(d: Decision, *, heading_note: str = "") -> list[str]:
    note = f" {heading_note}" if heading_note else ""
    lines = [f"### {d.decision} (`{d.id}`){note}", ""]
    lines.append(f"- **rationale:** {d.rationale}")
    lines.append(f"- **alternatives considered:** {_fmt_alts(d.alternatives_considered)}")
    lines.append(f"- **confidence:** {d.confidence}/10")
    lines.append(f"- **date:** {d.date}")
    if d.decided_at and d.decided_at != d.date:
        # A seeded past decision: recorded now, decided long before. Both are facts
        # worth reading, and only showing the append time would misdate the call.
        lines.append(f"- **decided:** {d.decided_at}")
    lines.append(f"- **author:** {d.author}")
    return lines


def _render_decision_block(
    d: Decision, all_decisions: dict[str, Decision], redact_reasons: dict[str, str]
) -> list[str]:
    """One decision's full block: chain members (oldest first) then the record itself."""
    lines: list[str] = []
    chain_members = [all_decisions[i] for i in d.chain if i in all_decisions]
    for prior in chain_members:
        lines.extend(_render_member(prior, heading_note="(superseded)"))
        lines.append("")
    note = "(REDACTED)" if d.redacted else ""
    lines.extend(_render_member(d, heading_note=note))
    if chain_members:
        chain_ids = " -> ".join([*d.chain, d.id])
        lines.append(f"- **chain:** {chain_ids}")
    if d.redacted:
        lines.append(f"- **reason:** {redact_reasons.get(d.id, '')}")
    lines.append("")
    return lines


def render_scope(ledger: Ledger, scope: str) -> str:
    """Fold `scope` into a single markdown page. Deterministic and idempotent."""
    fold = [d for d in ledger._fold() if d.scope == scope]
    all_decisions = {d.id: d for d in fold}
    # Reading order: decided_at (when the call was actually made), falling back to date
    # for anything that never set it. `_fold()` already resolves that fallback (Decision
    # .decided_at defaults to .date), so this reads chronologically without a second
    # fallback here. `date` still breaks ties and stays the sole input to `projected-at`
    # below -- staleness must keep clocking off append order, not decision order.
    ordered_ids = sorted(
        all_decisions, key=lambda i: (all_decisions[i].decided_at, all_decisions[i].date, i)
    )
    active = [all_decisions[i] for i in ordered_ids if all_decisions[i].active]
    retired = [all_decisions[i] for i in ordered_ids if all_decisions[i].redacted]
    redact_reasons = _redact_reasons(ledger)
    projected_at = _newest_event_at(fold)

    lines: list[str] = []
    lines.append("---")
    lines.append("decays: state")
    lines.append(f"scope: {scope}")
    lines.append(f"projected-at: {projected_at}")
    lines.append("source-events:")
    for eid in ordered_ids:
        lines.append(f"  - {eid}")
    lines.append("---")
    lines.append("")
    lines.append(f"# Cortex — {scope}")
    lines.append("")
    lines.append(
        "_Projected from the Konjo Ledger. Read-only -- edit the source events via "
        "`konjo-decision`, never this page directly._"
    )
    lines.append("")
    lines.append("## Active decisions")
    lines.append("")
    if not active:
        lines.append("_none active_")
        lines.append("")
    for d in active:
        lines.extend(_render_decision_block(d, all_decisions, redact_reasons))

    lines.append("## Retired")
    lines.append("")
    if not retired:
        lines.append("_none retired_")
        lines.append("")
    for d in retired:
        lines.extend(_render_decision_block(d, all_decisions, redact_reasons))

    return "\n".join(lines).rstrip("\n") + "\n"


def scope_slug(scope: str) -> str:
    """`org` -> `org`, `repo:lopi` -> `repo-lopi` -- a filesystem-safe page name."""
    return scope.replace(":", "-").replace("/", "-")
