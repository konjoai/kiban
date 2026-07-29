"""Generation fixtures (Phase 13, Phase 4): does the authoring context prevent a bad
diff, not just catch one already written.

`evals/fixtures/` (via `evals/runner.py`) tests whether the review gate *detects* a
planted bug in a diff that already exists. Nothing tests whether the always-on context
(the umbrella skill, `craft`, and any Phase 2 candidate invariant under evaluation)
*prevents* an agent from writing the bug in the first place -- that gap is why Phase 2
needs building before it can measure anything (see `.konjo/killtests/P13/KT-13.1.md`).

A generation fixture is a directory with:

  task.json      {"id": str, "prompt": str, "context_label": str, "source": str}
                  -- prompt: the implementation task, verbatim, as given to the generator
                  -- context_label: which always-on context this fixture was run under
                     (e.g. "baseline", "candidate:no_unconfigured_permit")
                  -- source: where the task came from (a real commit/PR, not invented --
                     KT-13.1's "git log is the source, not invention")

  candidate.diff  the diff the generator actually produced for this task. Recorded, not
                  regenerated on every eval run -- the same "cassette" discipline
                  `evals/cassettes.py` uses for review fixtures, for the same reason
                  (deterministic, offline, no repeat model cost). `run_generation`
                  (below) is how a NEW candidate.diff gets produced, as a distinct step
                  from evaluating one that already exists.

Distinct fixture shape from `evals/fixtures/*/{diff.patch,expect.json}`: a review
fixture's `diff.patch` is the INPUT (a pre-existing diff to review); a generation
fixture's `candidate.diff` is the OUTPUT (what the authoring context produced) and there
is no single "expect.json" -- the taxonomy classification IS the result, not a pass/fail
against one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from lib import polarity, redact, threat

GEN_FIXTURES_DIR = Path(__file__).resolve().parent / "gen_fixtures"

# The eight-class defect taxonomy from KT-13.1's own procedure. Distinct from (but
# related to) `lib.threat.TAXONOMY` -- threat.TAXONOMY names trust *boundaries* a change
# might cross; DEFECT_TAXONOMY names *defect shapes* a diff might contain. A change can
# cross the subprocess_exec boundary correctly (mitigated) or land the
# untrusted_input_reaching_exec defect (unmitigated) -- the taxonomies are siblings, not
# the same list twice.
DEFECT_TAXONOMY = (
    "unconfigured_permit_branch",
    "unbounded_queue",
    "missing_timeout",
    "raw_index_external_input",
    "untyped_error_boundary",
    "secret_in_source",
    "untrusted_input_reaching_exec",
    "missing_test_failure_path",
)

# Classes this harness classifies mechanically today, by reusing an existing kiban
# detector against the candidate diff. `None` in a ClassificationResult (not an empty
# list) marks a class this harness does NOT check -- distinct from "checked, zero
# findings." Silently defaulting an unclassified class to zero would misreport an
# unmeasured class as a clean one, exactly the false-precision KT-13.1 exists to refuse.
MECHANICALLY_CLASSIFIED = (
    "secret_in_source",       # lib.redact.scan_diff
    "unconfigured_permit_branch",  # lib.polarity (approximate: added-line text, not a
                               # full post-change file -- see classify_diff's docstring)
    "untrusted_input_reaching_exec",  # lib.threat.classify (heuristic hint, not proof)
)


@dataclass
class GenFixtureTask:
    id: str
    prompt: str
    context_label: str
    source: str


@dataclass
class ClassificationResult:
    # class -> list of finding descriptions, or None if this harness doesn't classify
    # that class mechanically (see MECHANICALLY_CLASSIFIED).
    findings: dict[str, list[str] | None] = field(default_factory=dict)

    def count(self, taxonomy_class: str) -> int | None:
        hits = self.findings.get(taxonomy_class)
        return None if hits is None else len(hits)

    def unclassified(self) -> list[str]:
        return [c for c, v in self.findings.items() if v is None]


def discover_gen_fixtures(corpus_dir: Path = GEN_FIXTURES_DIR) -> list[Path]:
    """Every subdirectory carrying both task.json and candidate.diff."""
    if not corpus_dir.exists():
        return []
    return sorted(
        p for p in corpus_dir.iterdir()
        if p.is_dir() and (p / "task.json").exists() and (p / "candidate.diff").exists()
    )


def load_task(fixture_dir: Path) -> GenFixtureTask:
    data = json.loads((fixture_dir / "task.json").read_text())
    return GenFixtureTask(
        id=data["id"],
        prompt=data["prompt"],
        context_label=data.get("context_label", "baseline"),
        source=data.get("source", "unknown"),
    )


def _added_lines(diff_text: str) -> str:
    """The added-line text of a diff, stripped of the leading '+'. An approximation of
    "the new file content" -- good enough for a line-shaped regex scan (redact, the
    threat heuristics), not a substitute for parsing the real post-change file."""
    return "\n".join(
        line[1:] for line in diff_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


def classify_diff(diff_text: str, changed_paths: list[str]) -> ClassificationResult:
    """Classify a candidate diff against DEFECT_TAXONOMY, mechanically where possible.

    Reuses existing kiban detectors for the classes where one already exists and
    genuinely overlaps, rather than writing a sixth pattern library:
      - secret_in_source: lib.redact.scan_diff (diff-shaped already, exact reuse).
      - unconfigured_permit_branch: lib.polarity.lint_text over the added-line text per
        changed path. Approximate: polarity's real shape detectors expect a full file
        (to see the surrounding conditional), so a diff-only scan under-detects a defect
        split across changed and unchanged lines. Named as a limit, not hidden.
      - untrusted_input_reaching_exec: lib.threat.classify's diff heuristics. A hint, not
        a proof -- the same limit `lib.threat`'s own module docstring states.
    The remaining five classes (unbounded_queue, missing_timeout,
    raw_index_external_input, untyped_error_boundary, missing_test_failure_path) have no
    mechanical detector in kiban today and are left `None` -- a future sprint's job, per
    Phase 2's own "keep only what's measured" discipline applied to the harness itself.
    """
    added = _added_lines(diff_text)
    result: dict[str, list[str] | None] = {c: None for c in DEFECT_TAXONOMY}

    secrets = redact.scan_diff(diff_text)
    result["secret_in_source"] = [f"{f.pattern_name}:{f.tier}" for f in secrets]

    permit_hits: list[str] = []
    for path in changed_paths:
        permit_hits.extend(f.format() for f in polarity.lint_text(added, path))
    result["unconfigured_permit_branch"] = permit_hits

    threat_cls = threat.classify(changed_paths, diff_text)
    result["untrusted_input_reaching_exec"] = list(
        threat_cls.reasons.get(threat.SUBPROCESS_EXEC, [])
    )

    return ClassificationResult(findings=result)


def run_gen_corpus(corpus_dir: Path = GEN_FIXTURES_DIR) -> dict[str, object]:
    """Classify every recorded generation fixture and return a per-class summary.

    Report-only by construction: there is no pass/fail here, only counts (see
    `templates/repo-ci.yml`'s report-only job, which never fails the build on this
    step's output). Mirrors `evals/runner.py::run`'s report shape loosely, but a
    generation fixture has no single expectation to check against, so the summary is
    counts, not a detection rate.
    """
    fixtures = discover_gen_fixtures(corpus_dir)
    per_fixture: list[dict[str, object]] = []
    totals: dict[str, int] = {c: 0 for c in DEFECT_TAXONOMY}
    unclassified_classes: set[str] = set()

    for fixture_dir in fixtures:
        task = load_task(fixture_dir)
        diff_text = (fixture_dir / "candidate.diff").read_text()
        changed_paths = sorted({
            line.split()[-1].removeprefix("b/")
            for line in diff_text.splitlines()
            if line.startswith("+++ ")
        })
        classification = classify_diff(diff_text, changed_paths)
        counts = {c: classification.count(c) for c in DEFECT_TAXONOMY}
        for c, n in counts.items():
            if n is None:
                unclassified_classes.add(c)
            else:
                totals[c] += n
        per_fixture.append({
            "id": task.id,
            "context_label": task.context_label,
            "source": task.source,
            "counts": counts,
        })

    return {
        "n_fixtures": len(fixtures),
        "totals": totals,
        "unclassified_classes": sorted(unclassified_classes),
        "fixtures": per_fixture,
    }
