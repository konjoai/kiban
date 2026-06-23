"""The prove gate: a paired Wilcoxon signed-rank perf test with a real-effect rule.

This module runs LOCALLY on the bench hardware, never in CI. It computes the verdict
from a paired measurement artifact the repo's own benchmark produced; it does not run the
benchmark. The CI gate (konjo-gates) only checks for a recorded MERGE trailer and never
imports anything here, so the stats stay off the CI runner by construction.

The house rule, load-bearing: statistical significance alone never merges. With 30+ runs
a trivial effect can clear p < 0.05. MERGE requires p < 0.05 AND a median improvement at
or above the minimum effect size AND the correct direction. A significant but
sub-threshold change is NOISE, recorded as plainly as a MERGE.

The Wilcoxon signed-rank test is implemented in pure Python (normal approximation with
continuity and tie corrections), so there is no scipy dependency to leak toward CI. It
matches scipy.stats.wilcoxon(..., correction=True, mode="approx") for n at the default
floor of 30.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

from lib import oneway

MERGE = "MERGE"
NOISE = "NOISE"
REGRESSION = "REGRESSION"

PROVE_TRAILER = oneway.PROVE_MERGE_TRAILER
DEFAULT_RUN_FLOOR = 30
DEFAULT_ALPHA = 0.05


class InsufficientRuns(Exception):
    """Fewer paired runs than the floor; refuse a verdict rather than guess on noise."""


@dataclass
class WilcoxonResult:
    n: int  # number of paired runs
    n_nonzero: int  # pairs with a nonzero difference (zeros dropped, Wilcoxon standard)
    w_plus: float
    z: float
    p_value: float
    median_baseline: float
    median_candidate: float
    median_delta: float  # candidate - baseline (signed, raw)
    median_improvement: float  # positive means better, per lower_is_better
    percent_change: float  # improvement as a percent of the baseline median


@dataclass
class Verdict:
    label: str  # MERGE | NOISE | REGRESSION
    reason: str
    result: WilcoxonResult
    min_effect: float
    alpha: float

    @property
    def is_merge(self) -> bool:
        return self.label == MERGE


def _avg_ranks(values: list[float]) -> list[float]:
    """Average ranks (1-based) for the magnitudes, ties share the mean of their ranks."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1  # mean of ranks i+1..j+1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _normal_sf(z: float) -> float:
    """Survival function 1 - Phi(z) via erfc."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def paired_wilcoxon(
    baseline: list[float],
    candidate: list[float],
    *,
    run_floor: int = DEFAULT_RUN_FLOOR,
    lower_is_better: bool = True,
) -> WilcoxonResult:
    """Paired Wilcoxon signed-rank over the measurement pairs.

    Raises InsufficientRuns below the floor. Zero-difference pairs are dropped (the
    standard Wilcoxon treatment). Ties in the magnitudes get a variance correction.
    """
    if len(baseline) != len(candidate):
        raise ValueError("baseline and candidate must have equal length (paired)")
    n = len(baseline)
    if n < run_floor:
        raise InsufficientRuns(
            f"{n} paired runs is below the floor of {run_floor}; run more before proving"
        )

    diffs = [c - b for b, c in zip(baseline, candidate, strict=True)]
    nonzero = [d for d in diffs if d != 0]
    n_nz = len(nonzero)

    median_baseline = statistics.median(baseline)
    median_candidate = statistics.median(candidate)
    median_delta = statistics.median(diffs)
    median_improvement = -median_delta if lower_is_better else median_delta
    percent_change = (
        100.0 * median_improvement / median_baseline if median_baseline else 0.0
    )

    if n_nz == 0:
        # Every pair identical: no evidence of any effect.
        return WilcoxonResult(
            n=n, n_nonzero=0, w_plus=0.0, z=0.0, p_value=1.0,
            median_baseline=median_baseline, median_candidate=median_candidate,
            median_delta=median_delta, median_improvement=median_improvement,
            percent_change=percent_change,
        )

    mags = [abs(d) for d in nonzero]
    ranks = _avg_ranks(mags)
    w_plus = sum(r for d, r in zip(nonzero, ranks, strict=True) if d > 0)

    mean_w = n_nz * (n_nz + 1) / 4
    var_w = n_nz * (n_nz + 1) * (2 * n_nz + 1) / 24

    # Tie correction: subtract sum(t^3 - t)/48 over groups of equal magnitudes.
    counts: dict[float, int] = {}
    for m in mags:
        counts[m] = counts.get(m, 0) + 1
    tie_term = sum(t**3 - t for t in counts.values() if t > 1)
    var_w -= tie_term / 48

    if var_w <= 0:
        return WilcoxonResult(
            n=n, n_nonzero=n_nz, w_plus=w_plus, z=0.0, p_value=1.0,
            median_baseline=median_baseline, median_candidate=median_candidate,
            median_delta=median_delta, median_improvement=median_improvement,
            percent_change=percent_change,
        )

    # Continuity-corrected z, two-sided p.
    diff_from_mean = abs(w_plus - mean_w)
    z = (diff_from_mean - 0.5) / math.sqrt(var_w)
    z = max(z, 0.0)
    p_value = 2 * _normal_sf(z)
    p_value = min(1.0, p_value)

    return WilcoxonResult(
        n=n, n_nonzero=n_nz, w_plus=w_plus, z=z, p_value=p_value,
        median_baseline=median_baseline, median_candidate=median_candidate,
        median_delta=median_delta, median_improvement=median_improvement,
        percent_change=percent_change,
    )


def verdict(
    result: WilcoxonResult,
    *,
    min_effect: float,
    lower_is_better: bool = True,
    alpha: float = DEFAULT_ALPHA,
) -> Verdict:
    """Render MERGE / NOISE / REGRESSION.

    MERGE needs significance AND a median improvement at or above min_effect in the right
    direction. A significant but sub-threshold effect is NOISE; a p-value alone never
    merges. A significant effect beyond min_effect in the wrong direction is REGRESSION.
    """
    significant = result.p_value < alpha
    improvement = result.median_improvement

    if not significant:
        return Verdict(
            NOISE, f"not significant (p={result.p_value:.4g} >= {alpha})",
            result, min_effect, alpha,
        )
    if improvement >= min_effect:
        return Verdict(
            MERGE,
            f"significant (p={result.p_value:.4g}) and improvement "
            f"{improvement:.4g} >= min_effect {min_effect:.4g}",
            result, min_effect, alpha,
        )
    if improvement <= -min_effect:
        return Verdict(
            REGRESSION,
            f"significant (p={result.p_value:.4g}) and regression "
            f"{improvement:.4g} <= -min_effect {-min_effect:.4g}",
            result, min_effect, alpha,
        )
    return Verdict(
        NOISE,
        f"significant (p={result.p_value:.4g}) but effect {improvement:.4g} is below "
        f"min_effect {min_effect:.4g}; significance alone never merges",
        result, min_effect, alpha,
    )


def min_effect_from_percent(pct: float, baseline: list[float]) -> float:
    """Convert a percent min-effect into absolute metric units via the baseline median."""
    return abs(pct) / 100.0 * statistics.median(baseline)


def prove_trailer(fp: str) -> str:
    """The MERGE commit trailer CI checks. Reuses the one-way record-and-check path."""
    return oneway.make_trailer(PROVE_TRAILER, fp)


def find_merge(messages: str, fp: str) -> bool:
    """True if a commit carries the MERGE trailer for this change."""
    return oneway.find_trailer(messages, PROVE_TRAILER, fp)
