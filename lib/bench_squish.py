"""Adapter from squish's thermal head-to-head bench output to the prove artifact.

squish's benchmarks/ollama_vs_squish/bench_thermal_h2h.py writes
results/benchmarks_v5_1_1/thermal/<UTC>.json with this shape (the fields this adapter
reads):

  {
    "host": "Apple M3 16 GB",
    "runs_per_metric": 5,                      # bench_v5_1.RUNS == 5
    "configs": {
      "<config_id>": {
        "label": "...", "quant": "...",
        "phases": {
          "p4000": { "e2e_runs": [ {"total_s": float, "ttft_s": float,
                                    "tokens_per_sec": float, ...}, ... ] }
        }
      }
    }
  }

It maps one config's per-run measurements at a phase into the flat list konjo-prove
ingests. A single bench run yields only RUNS (5) measurements, which is below the prove
floor of 30, so the adapter concatenates measurements across several bench JSON files;
the activation checklist in profiles/squish.yml documents this.

This reads bench OUTPUT only. It does not run the benchmark and does not import squish.
"""

from __future__ import annotations

import json
from pathlib import Path

# Prove metric name -> the per-run key in an e2e_runs entry, and its direction.
METRIC_KEYS: dict[str, tuple[str, bool]] = {
    "e2e_200tok_s": ("total_s", True),  # end-to-end wall clock, lower is better
    "ttft_s": ("ttft_s", True),  # time to first token, lower is better
    "warm_tps": ("tokens_per_sec", False),  # throughput, higher is better
}


class BenchFormatError(Exception):
    """The bench JSON did not have the expected config/phase/run structure."""


def extract_runs(
    bench: dict, *, config_id: str, phase: str, metric: str = "e2e_200tok_s"
) -> list[float]:
    """Pull one config's per-run measurements at a phase into a flat list of floats."""
    if metric not in METRIC_KEYS:
        raise BenchFormatError(f"unknown metric {metric!r}; known: {sorted(METRIC_KEYS)}")
    run_key = METRIC_KEYS[metric][0]
    try:
        runs = bench["configs"][config_id]["phases"][phase]["e2e_runs"]
    except (KeyError, TypeError) as exc:
        raise BenchFormatError(
            f"bench JSON missing configs[{config_id!r}].phases[{phase!r}].e2e_runs"
        ) from exc
    out: list[float] = []
    for r in runs:
        if run_key not in r:
            raise BenchFormatError(f"run entry missing {run_key!r}")
        out.append(float(r[run_key]))
    return out


def build_artifact(
    candidate_bench_paths: list[str],
    *,
    config_id: str,
    phase: str = "p4000",
    metric: str = "e2e_200tok_s",
    baseline_bench_paths: list[str] | None = None,
) -> dict:
    """Build the konjo-prove artifact from one or more squish bench JSON files.

    candidate measurements come from candidate_bench_paths; if baseline_bench_paths is
    given, the baseline field is filled too (otherwise konjo-prove pairs against a
    captured golden baseline tag). Concatenating several bench files is how you reach the
    30-run floor when each run only produces RUNS measurements.
    """
    run_key, lower_is_better = METRIC_KEYS[metric]
    candidate: list[float] = []
    host = None
    for p in candidate_bench_paths:
        bench = json.loads(Path(p).read_text(encoding="utf-8"))
        host = host or bench.get("host")
        candidate.extend(extract_runs(bench, config_id=config_id, phase=phase, metric=metric))

    artifact: dict = {
        "metric": metric,
        "unit": "s" if lower_is_better else "tok/s",
        "lower_is_better": lower_is_better,
        "hardware": host,
        "thermal_controlled": True,
        "candidate": candidate,
    }
    if baseline_bench_paths:
        baseline: list[float] = []
        for p in baseline_bench_paths:
            bench = json.loads(Path(p).read_text(encoding="utf-8"))
            baseline.extend(
                extract_runs(bench, config_id=config_id, phase=phase, metric=metric)
            )
        artifact["baseline"] = baseline
    return artifact
