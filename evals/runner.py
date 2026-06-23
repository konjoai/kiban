"""evals/runner.py: the meta-gate harness.

STUB (phase 1). Reads each fixture (diff.patch + expect.json), runs the gate against the
diff, compares the result to the expectation, and records detection_rate,
false_positives, and missed_bugs. Fails the build if the gate regresses below the prove
baseline.

Contract for the phase-1 implementation:
  run(corpus_dir, profile) -> Report
    - for each fixture: apply the gate to diff.patch, compare to expect.json
      (must_flag -> the gate must flag that category/severity;
       must_be_silent -> the gate must produce no finding)
    - aggregate detection_rate = caught / total must_flag
                false_positives = flags on must_be_silent fixtures
                missed_bugs = uncaught must_flag fixtures
    - the prove gate compares against the baseline with a 30-run paired Wilcoxon
      (p < 0.05); that statistical step is itself referenced as a stub this sprint.
"""

from __future__ import annotations

TODO_PHASE = 1


def run(corpus_dir: str, profile: str) -> object:
    # TODO(phase-1): load fixtures, run the gate, aggregate the metrics.
    raise NotImplementedError("evals/runner.py is a phase-1 stub")
