"""Tests for the prove stats engine (lib/prove.py).

Deterministic synthetic paired data, no RNG, so p-values are reproducible. The
load-bearing assertion is that a significant but sub-threshold effect is NOISE: a
p-value alone never merges.
"""

from __future__ import annotations

import pytest

from lib import prove

# A baseline of 30 distinct values around 100 (seconds, lower is better).
BASE = [100.0 + (i % 7) - 3 for i in range(30)]


def _shift(values: list[float], delta: float) -> list[float]:
    return [v + delta for v in values]


def test_significant_above_threshold_is_merge() -> None:
    # Candidate is 10s faster on every run: large, consistent improvement.
    cand = _shift(BASE, -10.0)
    res = prove.paired_wilcoxon(BASE, cand, lower_is_better=True)
    v = prove.verdict(res, min_effect=2.0, lower_is_better=True)
    assert res.p_value < 0.05
    assert v.label == prove.MERGE
    assert res.median_improvement == pytest.approx(10.0)


def test_significant_but_sub_threshold_is_noise() -> None:
    # Candidate is consistently 0.2s faster: highly significant (every run same sign),
    # but far below a 2.0s minimum effect. A p-value alone never merges.
    cand = _shift(BASE, -0.2)
    res = prove.paired_wilcoxon(BASE, cand, lower_is_better=True)
    v = prove.verdict(res, min_effect=2.0, lower_is_better=True)
    assert res.p_value < 0.05  # significant
    assert v.label == prove.NOISE  # but sub-threshold
    assert "never merges" in v.reason


def test_non_significant_is_noise() -> None:
    # Alternating +/-1s diffs: signs balance, the test is not significant.
    cand = [b + (1.0 if i % 2 == 0 else -1.0) for i, b in enumerate(BASE)]
    res = prove.paired_wilcoxon(BASE, cand, lower_is_better=True)
    v = prove.verdict(res, min_effect=0.1, lower_is_better=True)
    assert res.p_value >= 0.05
    assert v.label == prove.NOISE


def test_significant_wrong_direction_is_regression() -> None:
    # Candidate is 10s slower on every run (lower is better): a real regression.
    cand = _shift(BASE, 10.0)
    res = prove.paired_wilcoxon(BASE, cand, lower_is_better=True)
    v = prove.verdict(res, min_effect=2.0, lower_is_better=True)
    assert res.p_value < 0.05
    assert v.label == prove.REGRESSION


def test_run_floor_refuses_below_30() -> None:
    with pytest.raises(prove.InsufficientRuns):
        prove.paired_wilcoxon(BASE[:10], _shift(BASE[:10], -5.0))


def test_zero_differences_are_dropped() -> None:
    # Half the pairs are identical (dropped); the rest are a clear improvement.
    base = [100.0] * 30
    cand = [100.0] * 15 + [90.0] * 15
    res = prove.paired_wilcoxon(base, cand, lower_is_better=True)
    assert res.n == 30
    assert res.n_nonzero == 15
    assert res.p_value < 0.05


def test_higher_is_better_direction() -> None:
    # Throughput-style metric: candidate is higher, which is better.
    cand = _shift(BASE, 10.0)
    res = prove.paired_wilcoxon(BASE, cand, lower_is_better=False)
    v = prove.verdict(res, min_effect=2.0, lower_is_better=False)
    assert v.label == prove.MERGE
    assert res.median_improvement == pytest.approx(10.0)


def test_min_effect_from_percent() -> None:
    # 1 percent of a ~100s baseline is ~1.0s.
    assert prove.min_effect_from_percent(1.0, BASE) == pytest.approx(1.0, abs=0.05)


def test_merge_trailer_roundtrip() -> None:
    fp = "abc123def456"
    assert prove.find_merge(f"x\n\n{prove.prove_trailer(fp)}\n", fp)
    assert not prove.find_merge("no trailer", fp)
