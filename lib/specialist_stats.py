"""specialist_stats: fold the review log into per-specialist gate verdicts.

Evidence-first. A specialist earns or loses its place by its record across reviews, not
by a hunch. We count dispatches and findings per specialist across the log, then tag:

  INSUFFICIENT_DATA  fewer than the sample-size floor (default 10 dispatches). We never
                     recommend dropping a gate on thin evidence.
  NEVER_GATE         in the insurance set (default security, supply-chain). Kept on
                     regardless of hit rate, even at zero hits, because the cost of a
                     miss is too high to let a quiet streak retire it.
  GATE_CANDIDATE     at or above the floor with zero findings. Not pulling its weight;
                     a candidate to prune or demote to advisory. Surfaced for review,
                     not dropped automatically.
  ACTIVE             at or above the floor with findings. Earning its place.

hit_rate is findings per dispatch. It is reported for every specialist but only drives a
tag at or above the floor.
"""

from __future__ import annotations

from dataclasses import dataclass

from lib import jsonl_store

GATE_CANDIDATE = "GATE_CANDIDATE"
NEVER_GATE = "NEVER_GATE"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
ACTIVE = "ACTIVE"

DEFAULT_FLOOR = 10
DEFAULT_NEVER_GATE = ("security", "supply-chain")


@dataclass
class SpecialistStat:
    name: str
    dispatches: int
    findings: int
    tag: str

    @property
    def hit_rate(self) -> float:
        return self.findings / self.dispatches if self.dispatches else 0.0


def _iter_records(review_log_path: str) -> list[dict]:
    return jsonl_store.read(review_log_path)


def compute(
    review_log_path: str,
    *,
    floor: int = DEFAULT_FLOOR,
    never_gate: tuple[str, ...] = DEFAULT_NEVER_GATE,
) -> dict[str, SpecialistStat]:
    """Aggregate one review-log file into per-specialist stats and tags."""
    dispatches: dict[str, int] = {}
    findings: dict[str, int] = {}

    for rec in _iter_records(review_log_path):
        for s in rec.get("specialists", []):
            name = s.get("name")
            if not name:
                continue
            dispatches[name] = dispatches.get(name, 0) + int(s.get("dispatches", 0))
            findings[name] = findings.get(name, 0) + int(s.get("n_findings", 0))

    stats: dict[str, SpecialistStat] = {}
    for name in sorted(dispatches):
        d = dispatches[name]
        f = findings.get(name, 0)
        if name in never_gate:
            tag = NEVER_GATE
        elif d < floor:
            tag = INSUFFICIENT_DATA
        elif f == 0:
            tag = GATE_CANDIDATE
        else:
            tag = ACTIVE
        stats[name] = SpecialistStat(name=name, dispatches=d, findings=f, tag=tag)
    return stats


def format_table(stats: dict[str, SpecialistStat]) -> str:
    """Render a plain table for the CLI."""
    if not stats:
        return "no review history yet"
    rows = ["specialist          dispatches  findings  hit_rate  tag",
            "-----------------------------------------------------------------"]
    for s in stats.values():
        rows.append(
            f"{s.name:<18}  {s.dispatches:>10}  {s.findings:>8}  {s.hit_rate:>8.2f}  {s.tag}"
        )
    return "\n".join(rows)
