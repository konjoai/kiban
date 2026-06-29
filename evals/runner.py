"""The meta-gate harness: run the real review gate against the planted-bug corpus.

For each fixture (a dir with diff.patch and expect.json) the harness calls the SAME
review_diff the live gate uses, `runs` times, and checks the result against the
expectation:

  must_flag {category, severity}  the gate must produce a matching finding.
  must_be_silent: true            the gate must produce no finding above the gate.

Detection from a single run is noise, so every fixture is run `runs` times (default 3)
and per-run results are recorded alongside the aggregate. The exit policy is strict and
documented in evaluate():
  - a CRITICAL must_flag must be detected on EVERY run (detection_rate == 1.0),
  - a non-CRITICAL must_flag must be detected on at least one run,
  - a must_be_silent control must be silent on EVERY run.

The 30-run paired Wilcoxon prove-baseline comparison is the next step (a later sprint);
this harness records the detection metrics it will consume.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from lib import review
from lib.review import ReviewBackend

DEFAULT_RUNS = 3
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@dataclass
class FixtureResult:
    name: str
    kind: str  # "must_flag" or "must_be_silent"
    expect: dict[str, Any]
    per_run_detected: list[bool] = field(default_factory=list)
    per_run_findings: list[int] = field(default_factory=list)
    latency: float = 0.0
    model: str | None = None

    @property
    def detection_rate(self) -> float:
        if not self.per_run_detected:
            return 0.0
        return sum(self.per_run_detected) / len(self.per_run_detected)

    @property
    def passed(self) -> bool:
        if self.kind == "must_be_silent":
            # Silent on every run: no finding above gate, ever.
            return all(self.per_run_detected)
        severity = str(self.expect.get("must_flag", {}).get("severity", "")).upper()
        if severity == "CRITICAL":
            return self.detection_rate >= 1.0
        return self.detection_rate > 0.0


def discover_fixtures(corpus_dir: Path = FIXTURES_DIR) -> list[Path]:
    """Every dir under the corpus that has both diff.patch and expect.json."""
    found: list[Path] = []
    for expect in sorted(corpus_dir.rglob("expect.json")):
        if (expect.parent / "diff.patch").exists():
            found.append(expect.parent)
    return found


def corpus_fixtures(profile: dict[str, Any], corpus_dir: Path = FIXTURES_DIR) -> list[Path]:
    """Fixtures for a profile. A profile may scope its corpus with `eval_corpus` (a list of
    subdir names under the fixtures root); absent, the whole tree is used (back-compat).

    Scoping is load-bearing: a repo only evaluates fixtures for its own stack, so the Squish
    self-test never tries to review a Rust fixture (which would miss its cassette and error).
    """
    subdirs = profile.get("eval_corpus")
    if not subdirs:
        return discover_fixtures(corpus_dir)
    found: list[Path] = []
    seen: set[Path] = set()
    for sd in subdirs:
        for fx in discover_fixtures(corpus_dir / sd):
            if fx not in seen:
                seen.add(fx)
                found.append(fx)
    return found


def _load_profile(profile_path: str | Path) -> dict[str, Any]:
    with open(profile_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


def evaluate_fixture(
    fixture_dir: Path,
    profile: dict[str, Any],
    *,
    runs: int,
    backend: ReviewBackend | None,
    mode: str,
) -> FixtureResult:
    diff_text = (fixture_dir / "diff.patch").read_text(encoding="utf-8")
    expect = json.loads((fixture_dir / "expect.json").read_text(encoding="utf-8"))
    name = str(fixture_dir.relative_to(FIXTURES_DIR))

    kind = "must_flag" if "must_flag" in expect else "must_be_silent"
    fr = FixtureResult(name=name, kind=kind, expect=expect)

    result = review.review_diff(diff_text, profile, runs=runs, backend=backend, mode=mode)
    fr.model = next((r.model for r in result.specialist_reports), None)
    fr.latency = sum(r.latency for r in result.specialist_reports)

    for run_findings in result.per_run:
        fr.per_run_findings.append(len(run_findings))
        if kind == "must_flag":
            want = expect["must_flag"]
            detected = any(
                f.category.lower() == str(want.get("category", "")).lower()
                and f.severity.upper() == str(want.get("severity", "")).upper()
                for f in run_findings
            )
            fr.per_run_detected.append(detected)
        else:
            # "detected" here means the desired outcome held: the run was silent.
            fr.per_run_detected.append(len(run_findings) == 0)
    return fr


def record_cassettes(
    profile_path: str | Path,
    *,
    mode: str = "daily",
    corpus_dir: Path = FIXTURES_DIR,
) -> list[Path]:
    """Run the live backend once over each fixture and write a cassette per fixture.

    This is the explicit, online path. It uses the real ClaudeCLIBackend, so it needs a
    model and network. The replay path (the CI gate) never does.
    """
    from evals import cassettes

    profile = _load_profile(profile_path)
    written: list[Path] = []
    for fixture in corpus_fixtures(profile, corpus_dir):
        diff_text = (fixture / "diff.patch").read_text(encoding="utf-8")
        name = str(fixture.relative_to(corpus_dir))
        recorder = cassettes.RecordingBackend(review.ClaudeCLIBackend())
        # One run is enough to capture every (specialist, prompt) reply for replay.
        review.review_diff(diff_text, profile, runs=1, backend=recorder, mode=mode)
        written.append(cassettes.save_cassette(name, recorder.data))
    return written


def run(
    profile_path: str | Path,
    *,
    runs: int = DEFAULT_RUNS,
    backend: ReviewBackend | None = None,
    mode: str = "daily",
    corpus_dir: Path = FIXTURES_DIR,
) -> dict[str, Any]:
    """Run the whole corpus and return an eval-store report dict."""
    profile = _load_profile(profile_path)
    results: list[FixtureResult] = []
    for fixture in corpus_fixtures(profile, corpus_dir):
        results.append(
            evaluate_fixture(fixture, profile, runs=runs, backend=backend, mode=mode)
        )

    must_flag = [r for r in results if r.kind == "must_flag"]
    controls = [r for r in results if r.kind == "must_be_silent"]
    ok = all(r.passed for r in results)

    return {
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runs": runs,
        "mode": mode,
        "ok": ok,
        "summary": {
            "n_fixtures": len(results),
            "n_must_flag": len(must_flag),
            "n_controls": len(controls),
            "missed_bugs": [r.name for r in must_flag if not r.passed],
            "false_positive_controls": [r.name for r in controls if not r.passed],
        },
        "fixtures": [
            {
                "name": r.name,
                "kind": r.kind,
                "expect": r.expect,
                "passed": r.passed,
                "per_run_detected": r.per_run_detected,
                "per_run_findings": r.per_run_findings,
                "detection_rate": round(r.detection_rate, 3),
                "false_positive_rate": (
                    round(1.0 - r.detection_rate, 3) if r.kind == "must_be_silent" else None
                ),
                "latency": round(r.latency, 3),
                "model": r.model,
            }
            for r in results
        ],
    }
