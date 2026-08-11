"""Adoption-Ramp-1: lib/gate_stats.py classification boundaries.

Mirrors tests/test_specialist_stats.py's shape (if present) / lib/specialist_stats.py's
own doctring convention -- a gate's tag is driven by sample-size floor first, then a
false-positive-rate ceiling.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lib import gate_stats


def _write_events(path: Path, events: list[dict]) -> None:
    with path.open("w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def _record(gate_results: list[dict]) -> dict:
    return {"event": "pr_telemetry", "gate_results": gate_results}


def test_below_floor_is_insufficient_data() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "pr_telemetry.jsonl"
        events = [_record([{"name": "static", "verdict": "PASS"}]) for _ in range(5)]
        _write_events(path, events)
        stats = gate_stats.compute(str(path), floor=20)
        assert stats["static"].tag == gate_stats.INSUFFICIENT_DATA
        assert stats["static"].runs == 5


def test_at_floor_with_zero_false_positives_is_blocking_ready() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "pr_telemetry.jsonl"
        events = [_record([{"name": "static", "verdict": "PASS"}]) for _ in range(20)]
        _write_events(path, events)
        stats = gate_stats.compute(str(path), floor=20, fp_ceiling=0.05)
        assert stats["static"].tag == gate_stats.BLOCKING_READY
        assert stats["static"].false_positive_rate == 0.0


def test_high_false_positive_rate_is_advisory_only() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "pr_telemetry.jsonl"
        events = []
        for i in range(20):
            events.append(_record([{
                "name": "flaky-gate", "verdict": "FAIL", "overridden": i % 2 == 0,
            }]))
        _write_events(path, events)
        stats = gate_stats.compute(str(path), floor=20, fp_ceiling=0.05)
        assert stats["flaky-gate"].tag == gate_stats.ADVISORY_ONLY
        assert stats["flaky-gate"].false_positive_rate == 0.5


def test_false_positive_rate_exactly_at_ceiling_is_advisory_only() -> None:
    # >= ceiling, not > -- a rate exactly at the stated ceiling has not proven itself
    # BELOW it, so it stays on the safe side.
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "pr_telemetry.jsonl"
        events = []
        for i in range(20):
            events.append(_record([{
                "name": "borderline-gate", "verdict": "FAIL", "overridden": i == 0,
            }]))
        _write_events(path, events)
        stats = gate_stats.compute(str(path), floor=20, fp_ceiling=0.05)
        assert stats["borderline-gate"].false_positive_rate == 0.05
        assert stats["borderline-gate"].tag == gate_stats.ADVISORY_ONLY


def test_waived_counts_toward_false_positive_rate_same_as_overridden() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "pr_telemetry.jsonl"
        events = [
            _record([{"name": "polarity", "verdict": "WARN", "waived": True}])
            for _ in range(20)
        ]
        _write_events(path, events)
        stats = gate_stats.compute(str(path), floor=20, fp_ceiling=0.05)
        assert stats["polarity"].false_positive_rate == 1.0
        assert stats["polarity"].tag == gate_stats.ADVISORY_ONLY


def test_pass_verdicts_do_not_count_as_non_pass() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "pr_telemetry.jsonl"
        events = [_record([{"name": "static", "verdict": "PASS"}]) for _ in range(30)]
        _write_events(path, events)
        stats = gate_stats.compute(str(path), floor=20)
        assert stats["static"].non_pass == 0
        assert stats["static"].false_positive_rate == 0.0


def test_multiple_gates_tracked_independently() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "pr_telemetry.jsonl"
        events = []
        for _ in range(20):
            events.append(_record([
                {"name": "clean-gate", "verdict": "PASS"},
                {"name": "flaky-gate", "verdict": "FAIL", "overridden": True},
            ]))
        _write_events(path, events)
        stats = gate_stats.compute(str(path), floor=20, fp_ceiling=0.05)
        assert stats["clean-gate"].tag == gate_stats.BLOCKING_READY
        assert stats["flaky-gate"].tag == gate_stats.ADVISORY_ONLY


def test_empty_telemetry_produces_empty_stats() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "pr_telemetry.jsonl"
        path.write_text("")
        stats = gate_stats.compute(str(path))
        assert stats == {}
        assert gate_stats.format_table(stats) == "no gate telemetry yet"


def test_format_table_renders_all_gates() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "pr_telemetry.jsonl"
        events = [_record([{"name": "static", "verdict": "PASS"}]) for _ in range(20)]
        _write_events(path, events)
        stats = gate_stats.compute(str(path), floor=20)
        table = gate_stats.format_table(stats)
        assert "static" in table
        assert gate_stats.BLOCKING_READY in table
