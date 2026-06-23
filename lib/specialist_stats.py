"""specialist_stats: turn review history into gate-promotion verdicts.

STUB (phase 1). Reads the review jsonl log, computes a per-specialist hit rate (how
often a specialist's flag corresponded to a real, confirmed defect), and tags each
specialist GATE_CANDIDATE (reliable enough to block) or NEVER_GATE (too noisy, advisory
only). This is the data-driven guard against promoting a noisy reviewer into a blocking
gate.

Contract for the phase-1 implementation:
  compute(review_log_path: str) -> dict[str, SpecialistStat] where each stat carries
    hit_rate, sample_size, and a tag in {GATE_CANDIDATE, NEVER_GATE, INSUFFICIENT_DATA}.
  Promotion needs both a hit rate over the profile threshold and a minimum sample size
  so a single lucky flag cannot promote a specialist.
"""

from __future__ import annotations

GATE_CANDIDATE = "GATE_CANDIDATE"
NEVER_GATE = "NEVER_GATE"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


def compute(review_log_path: str) -> dict[str, object]:
    # TODO(phase-1): fold the review log into per-specialist hit rates and tags.
    raise NotImplementedError("specialist_stats is a phase-1 stub")
