"""Review-log writer: one structured record per review run, on the jsonl store.

The log is the input specialist_stats folds. It records, per run, which specialists were
dispatched and how many findings each raised, the findings themselves, the gate summary,
the branch, and a timestamp. Because it goes through jsonl_store it inherits the
injection-reject and HIGH-secret block for free; a review that somehow captured a secret
cannot be written.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from typing import Any

from lib import jsonl_store
from lib.review import ReviewResult


def _branch() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        )
        name = proc.stdout.strip()
        return name or "detached"
    except OSError:
        return "unknown"


def _safe(branch: str) -> str:
    return branch.replace("/", "-").replace(" ", "-")


def log_path_for(branch: str) -> str:
    return f"review/{_safe(branch)}-reviews.jsonl"


def record(result: ReviewResult, *, branch: str | None = None, label: str | None = None) -> str:
    """Append one record for a completed review. Returns the log path used."""
    branch = branch or _branch()
    path = log_path_for(branch)
    payload: dict[str, Any] = {
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "branch": branch,
        "label": label,
        "runs": result.runs,
        "mode": result.mode,
        "threshold": result.threshold,
        "selected": result.selected,
        "scope_flags": {k: v for k, v in result.scope_flags.items() if v},
        "specialists": [
            {
                "name": r.name,
                "dispatched": r.dispatched,
                "dispatches": r.dispatches,
                "n_findings": r.n_findings,
                "latency": round(r.latency, 3),
                "model": r.model,
            }
            for r in result.specialist_reports
        ],
        "findings": [f.to_record() for f in result.findings],
        "gates": {
            "n_findings": len(result.findings),
            "categories": sorted({f.category for f in result.findings}),
        },
    }
    jsonl_store.append(path, payload)
    return path
