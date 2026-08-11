"""gate_stats: fold PR telemetry's per-gate results into per-gate promotion verdicts.

Mirrors `lib/specialist_stats.py`'s shape (aggregate a jsonl event stream into
per-name stats and a tag), applied to the other half of Adoption-Ramp-1's promotion
question. `lib/specialist_stats.py` already measures whether a review specialist
finds anything (its *yield*). Nothing measured a gate's *cost* -- how often its
FAIL/WARN verdict was later reversed by a human (`gate:override` for a BLOCKING
gate, a `Konjo-*-Waived:` trailer for an advisory finding). This module is that
missing half, fed by `ledger/pr_telemetry.py`'s `gate_results` field.

Tags:
  INSUFFICIENT_DATA  fewer than the sample-size floor (default 20 runs). Promoting a
                     gate to BLOCKING on thin evidence is exactly the failure this
                     sprint (Gate-Tiering-1) exists to prevent from recurring.
  ADVISORY_ONLY      at or above the floor, but the false-positive rate (overridden
                     or waived verdicts, as a fraction of all non-PASS verdicts) is
                     at or above the stated ceiling (default 5%). Not safe to block
                     merge yet.
  BLOCKING_READY     at or above the floor, false-positive rate under the ceiling.
                     Meets the *measurement* half of promotion; the *mechanical*
                     half (a passing `rejects_test`) is checked separately by
                     konjo-gates' `gate_blocking_promotion` meta-gate -- this module
                     has no access to a live rejects_test run, only recorded
                     telemetry, so it does not claim to check both.

false_positive_rate is reported for every gate, at any sample size, but only drives
a tag at or above the floor -- the same convention `specialist_stats.hit_rate`
already uses.
"""

from __future__ import annotations

from dataclasses import dataclass

from lib import jsonl_store

BLOCKING_READY = "BLOCKING_READY"
ADVISORY_ONLY = "ADVISORY_ONLY"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

DEFAULT_FLOOR = 20
DEFAULT_FP_CEILING = 0.05

_NON_PASS_VERDICTS = ("WARN", "FAIL")


@dataclass
class GateStat:
    name: str
    runs: int
    non_pass: int
    overridden: int
    waived: int
    tag: str

    @property
    def false_positive_rate(self) -> float:
        return (self.overridden + self.waived) / self.non_pass if self.non_pass else 0.0


def _iter_gate_results(pr_telemetry_path: str) -> list[dict]:
    """Flatten every `gate_results` entry across every PR telemetry event into one
    list of per-gate-run dicts, each still carrying its own name/verdict/overridden/
    waived fields."""
    out: list[dict] = []
    for rec in jsonl_store.read(pr_telemetry_path):
        for g in rec.get("gate_results") or []:
            if g.get("name"):
                out.append(g)
    return out


def compute(
    pr_telemetry_path: str,
    *,
    floor: int = DEFAULT_FLOOR,
    fp_ceiling: float = DEFAULT_FP_CEILING,
) -> dict[str, GateStat]:
    """Aggregate PR telemetry's gate_results into per-gate promotion stats and tags."""
    runs: dict[str, int] = {}
    non_pass: dict[str, int] = {}
    overridden: dict[str, int] = {}
    waived: dict[str, int] = {}

    for g in _iter_gate_results(pr_telemetry_path):
        name = g["name"]
        runs[name] = runs.get(name, 0) + 1
        verdict = str(g.get("verdict", "")).upper()
        if verdict in _NON_PASS_VERDICTS:
            non_pass[name] = non_pass.get(name, 0) + 1
            if g.get("overridden"):
                overridden[name] = overridden.get(name, 0) + 1
            if g.get("waived"):
                waived[name] = waived.get(name, 0) + 1

    stats: dict[str, GateStat] = {}
    for name in sorted(runs):
        r = runs[name]
        np = non_pass.get(name, 0)
        ov = overridden.get(name, 0)
        wv = waived.get(name, 0)
        stat = GateStat(name=name, runs=r, non_pass=np, overridden=ov, waived=wv, tag="")
        if r < floor:
            stat.tag = INSUFFICIENT_DATA
        elif stat.false_positive_rate >= fp_ceiling:
            stat.tag = ADVISORY_ONLY
        else:
            stat.tag = BLOCKING_READY
        stats[name] = stat
    return stats


def format_table(stats: dict[str, GateStat]) -> str:
    """Render a plain table for the CLI, same convention as
    `specialist_stats.format_table`."""
    if not stats:
        return "no gate telemetry yet"
    rows = ["gate                 runs  non_pass  overridden  waived  fp_rate  tag",
            "---------------------------------------------------------------------------"]
    for s in stats.values():
        rows.append(
            f"{s.name:<20} {s.runs:>5} {s.non_pass:>9} {s.overridden:>11} {s.waived:>7}  "
            f"{s.false_positive_rate:>7.2%}  {s.tag}"
        )
    return "\n".join(rows)
