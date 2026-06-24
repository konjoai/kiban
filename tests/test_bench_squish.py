"""Tests for the squish bench adapter (lib/bench_squish.py).

Synthetic bench JSON shaped exactly like bench_thermal_h2h.py output (configs ->
phases -> e2e_runs with total_s/ttft_s/tokens_per_sec per run).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib import bench_squish


def _bench(total_s_values: list[float]) -> dict:
    return {
        "host": "Apple M3 16 GB",
        "runs_per_metric": len(total_s_values),
        "configs": {
            "squish_int4": {
                "label": "squish INT4",
                "quant": "int4",
                "phases": {
                    "p4000": {
                        "e2e_runs": [
                            {"total_s": v, "ttft_s": 0.2, "tokens_per_sec": 80.0}
                            for v in total_s_values
                        ]
                    }
                },
            }
        },
    }


def test_extract_runs_e2e() -> None:
    runs = bench_squish.extract_runs(
        _bench([12.7, 12.9, 13.1]), config_id="squish_int4", phase="p4000"
    )
    assert runs == [12.7, 12.9, 13.1]


def test_extract_runs_throughput_direction() -> None:
    _key, lower_is_better = bench_squish.METRIC_KEYS["warm_tps"]
    assert lower_is_better is False


def test_build_artifact_concatenates_bench_files(tmp_path: Path) -> None:
    # Each bench file has 5 runs; two files reach 10 (the real flow concatenates to 30+).
    p1 = tmp_path / "a.json"
    p2 = tmp_path / "b.json"
    p1.write_text(json.dumps(_bench([12.0, 12.1, 12.2, 12.3, 12.4])))
    p2.write_text(json.dumps(_bench([12.5, 12.6, 12.7, 12.8, 12.9])))
    art = bench_squish.build_artifact(
        [str(p1), str(p2)], config_id="squish_int4", phase="p4000", metric="e2e_200tok_s"
    )
    assert art["metric"] == "e2e_200tok_s"
    assert art["unit"] == "s"
    assert art["lower_is_better"] is True
    assert art["hardware"] == "Apple M3 16 GB"
    assert len(art["candidate"]) == 10


def test_bad_format_raises(tmp_path: Path) -> None:
    with pytest.raises(bench_squish.BenchFormatError):
        bench_squish.extract_runs({"configs": {}}, config_id="nope", phase="p4000")
