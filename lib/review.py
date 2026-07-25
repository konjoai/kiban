"""The keystone review interface shared by the live gate and the eval harness.

    review_diff(diff_text, profile, specialists=None, *, runs=DEFAULT_LIVE_RUNS) -> ReviewResult

One function, two callers. The live review CLI passes the working diff; the eval harness
passes each fixture's diff.patch. They share this exact path so the eval exercises the
real gate, not a parallel mock.

The reviewer is an LLM: findings vary run to run, so a single pass silently misses
whatever the model didn't catch on that particular sample. `runs` repeats the review
and unions the findings (more runs raise recall, they never hide a finding a smaller
run count would have shown) -- the same self-consistency principle `prove.py` applies
to a noisy perf measurement, applied to the noisiest, highest-stakes judgment in the
framework: is this diff safe to merge. See `DEFAULT_LIVE_RUNS` below for the default
and its cost tradeoff.

Specialists are prompt-driven reviewers invoked through a backend: the Claude CLI in
production, a scripted backend in tests. Findings carry a stable fingerprint (path,
category, normalized summary, never the line number) so the same issue on a shifted line
dedups to one. A confidence gate drops low-confidence noise before anything is shown.

Fail-closed: a backend's `dispatch` returns None (not empty text) when a specialist did
not complete -- a timeout, a launch error, or a non-zero CLI exit. A single failure gets
one retry; if the retry also fails, the specialist is marked failed and
`ReviewResult.incomplete` is True. A caller gating a merge on the review must treat
INCOMPLETE as block-or-retry, never as a pass -- an incomplete review carries no signal
about whether the diff is actually clean, so it must never read the same as
dispatched-with-zero-findings.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Protocol

from lib import diff_scope
from lib.packs.lang import _base

# Stack entries map to language packs when a profile does not name `packs` explicitly. Only
# packs that exist are mapped; an unmapped stack entry contributes no pack (the `_base`
# lanes are always present). This keeps profiles/squish.yml (stack: [python, mlx]) working
# unchanged with no `packs` field.
_STACK_TO_PACK = {
    "python": "lang/python",
    "mlx": "lang/mlx",
    "rust": "lang/rust",
    "ts": "lang/typescript",
    "typescript": "lang/typescript",
    "mojo": "lang/mojo",
}


def packs_for(profile: dict[str, Any]) -> list[str]:
    """The pack list for a profile: explicit `packs`, else derived from `stack`."""
    explicit = profile.get("packs")
    if explicit:
        return list(explicit)
    stack = profile.get("stack", []) or []
    return [_STACK_TO_PACK[s] for s in stack if s in _STACK_TO_PACK]

logger = logging.getLogger("kiban.review")

# Confidence thresholds by mode. Daily keeps only high-confidence findings; deep surfaces
# almost everything for a careful human pass.
MODE_THRESHOLDS = {"daily": 8, "deep": 2}
DEFAULT_MODE = "daily"

# The live gate's default self-consistency pass count. A single pass silently misses
# whatever the reviewer LLM happened not to catch on that one sample -- the same reason
# `prove.py` refuses a verdict from a single trial. Matches `evals/runner.py`'s
# `DEFAULT_RUNS` (3): the blocking merge review must not sample the noisy reviewer
# process less than the eval harness that validates the gate's own detection rate.
# Cost tradeoff, stated so it is a considered decision: each additional run is a full
# extra specialist dispatch per selected specialist -- a real model call in production
# -- so this is a deliberate ~3x cost multiplier on the review. That is acceptable
# because Wall 3 runs on the merge path, not on every keystroke; a `daily` fast mode
# can still override with `runs=1` (see `bin/konjo-review --runs`).
DEFAULT_LIVE_RUNS = 3


# --------------------------------------------------------------------------- backends


class ReviewBackend(Protocol):
    def dispatch(
        self, specialist: str, system_prompt: str, user_prompt: str, *, model: str | None = None
    ) -> str | None: ...


class ClaudeCLIBackend:
    """Production backend: invoke the Claude CLI in headless print mode.

    Reuses the konjo_wall3_cc.sh pattern (a single -p call returning text). The system
    prompt and the diff are combined into one prompt so the call does not depend on a
    specific system-prompt flag. Fail-closed contract: `dispatch` returns `None` (never
    empty text) when the specialist did not complete -- a timeout, an OSError launching
    the CLI, or a non-zero exit -- so the caller can tell "reviewed clean" from "did not
    review" instead of the two being indistinguishable. A non-zero exit is treated as a
    failure even when the process wrote partial stdout: there is no case where a
    specialist that errored out is still trustworthy for findings.
    """

    def __init__(self, model: str | None = None, timeout: int = 180) -> None:
        self.model = model or os.environ.get("KONJO_REVIEW_MODEL")
        self.timeout = timeout

    def dispatch(
        self, specialist: str, system_prompt: str, user_prompt: str, *, model: str | None = None
    ) -> str | None:
        prompt = f"{system_prompt}\n\n{user_prompt}"
        cmd = ["claude", "-p", prompt, "--output-format", "text"]
        chosen = model or self.model
        if chosen:
            cmd += ["--model", chosen]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("specialist %s backend call failed: %s", specialist, exc)
            return None
        if proc.returncode != 0:
            logger.warning(
                "specialist %s backend exit %d; treating as incomplete",
                specialist, proc.returncode,
            )
            return None
        return proc.stdout


class ScriptedBackend:
    """Deterministic backend for tests. Returns canned replies keyed by specialist name.

    `fail_once` simulates a transient failure (a timeout that succeeds on retry):
    dispatch returns None the first time a listed specialist is called, then serves
    its canned reply. `fail_always` simulates a specialist that never completes:
    every call, including the retry, returns None.
    """

    def __init__(
        self,
        by_specialist: dict[str, str],
        default: str = "NO FINDINGS",
        fail_once: set[str] | None = None,
        fail_always: set[str] | None = None,
    ) -> None:
        self.by_specialist = by_specialist
        self.default = default
        self.fail_once = set(fail_once or ())
        self.fail_always = set(fail_always or ())
        self.calls: list[str] = []

    def dispatch(
        self, specialist: str, system_prompt: str, user_prompt: str, *, model: str | None = None
    ) -> str | None:
        self.calls.append(specialist)
        if specialist in self.fail_always:
            return None
        if specialist in self.fail_once:
            self.fail_once.discard(specialist)
            return None
        return self.by_specialist.get(specialist, self.default)


def model_name(backend: ReviewBackend) -> str | None:
    return getattr(backend, "model", None)


# --------------------------------------------------------------------------- data


@dataclass
class Finding:
    severity: str
    confidence: int
    path: str
    line: int | None
    category: str
    summary: str
    fix: str
    specialist: str
    fingerprint: str = ""
    specialists: tuple[str, ...] = ()
    recurrence: int = 1

    def __post_init__(self) -> None:
        if not self.fingerprint:
            self.fingerprint = _fingerprint(self.path, self.category, self.summary)
        if not self.specialists:
            self.specialists = (self.specialist,)

    def to_record(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "severity": self.severity,
            "confidence": self.confidence,
            "category": self.category,
            "path": self.path,
            "line": self.line,
            "summary": self.summary,
            "specialist": self.specialist,
            "specialists": list(self.specialists),
            "recurrence": self.recurrence,
        }


@dataclass
class SpecialistReport:
    name: str
    dispatches: int = 0
    n_findings: int = 0
    latency: float = 0.0
    model: str | None = None
    failed: bool = False

    @property
    def dispatched(self) -> bool:
        """An attempt was made. True even for a specialist that never completed --
        `completed` is the property that distinguishes a clean pass from a failure."""
        return self.dispatches > 0

    @property
    def completed(self) -> bool:
        return self.dispatched and not self.failed


@dataclass
class ReviewResult:
    findings: list[Finding]
    per_run: list[list[Finding]]
    specialist_reports: list[SpecialistReport]
    runs: int
    mode: str
    threshold: int
    selected: list[str]
    scope_flags: dict[str, bool] = field(default_factory=dict)

    @property
    def incomplete(self) -> bool:
        """True if any selected specialist failed to complete (after its retry).

        Wall 3 is the last line of defense; a specialist that did not complete is not
        the same thing as a specialist that reviewed and found nothing. A caller
        gating a merge on the review must treat this as block-or-retry, never pass --
        an INCOMPLETE result carries no information about whether the diff is clean.
        """
        return any(r.failed for r in self.specialist_reports)

    def has(self, category: str, severity: str) -> bool:
        cat = category.lower()
        sev = severity.upper()
        return any(
            f.category.lower() == cat and f.severity.upper() == sev for f in self.findings
        )


# --------------------------------------------------------------------------- helpers

_PATH_RE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)
_GIT_RE = re.compile(r"^diff --git a/.+ b/(.+)$", re.MULTILINE)
_WORD_RE = re.compile(r"[a-z0-9]+")
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n|\n```$")


def changed_files(diff_text: str) -> list[str]:
    """Extract changed file paths from a unified diff."""
    files: list[str] = []
    for m in _PATH_RE.finditer(diff_text):
        if m.group(1) != "/dev/null":
            files.append(m.group(1))
    if not files:
        files = [m.group(1) for m in _GIT_RE.finditer(diff_text)]
    # Preserve order, drop dups.
    seen: set[str] = set()
    out: list[str] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _normalize_summary(summary: str) -> str:
    return " ".join(_WORD_RE.findall(summary.lower()))


def _normalize_path(path: str) -> str:
    return path.strip().lstrip("./")


def _fingerprint(path: str, category: str, summary: str) -> str:
    key = f"{_normalize_path(path)}|{category.lower().strip()}|{_normalize_summary(summary)}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def parse_findings(text: str, specialist: str, default_category: str) -> list[Finding]:
    """Parse a specialist reply into Findings. Defensive: malformed input yields []."""
    if not text:
        return []
    stripped = _FENCE_RE.sub("", text.strip()).strip()
    if "[" not in stripped:
        # NO FINDINGS, or any prose without a JSON array.
        return []
    start = stripped.find("[")
    end = stripped.rfind("]")
    if end <= start:
        return []
    try:
        raw = json.loads(stripped[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        logger.warning("specialist %s returned unparseable JSON", specialist)
        return []
    if not isinstance(raw, list):
        return []

    findings: list[Finding] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            confidence = int(item.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0
        confidence = max(0, min(10, confidence))
        line_val = item.get("line")
        line = int(line_val) if isinstance(line_val, (int, float)) else None
        summary = str(item.get("summary", "")).strip()
        if not summary:
            continue
        findings.append(
            Finding(
                severity=str(item.get("severity", "MEDIUM")).upper(),
                confidence=confidence,
                path=str(item.get("path", "")).strip(),
                line=line,
                category=str(item.get("category") or default_category).strip(),
                summary=summary,
                fix=str(item.get("fix", "")).strip(),
                specialist=specialist,
            )
        )
    return findings


def dedup(findings: list[Finding]) -> list[Finding]:
    """Collapse by fingerprint, keeping the highest-confidence finding and recording
    every specialist that raised it."""
    best: dict[str, Finding] = {}
    raisers: dict[str, list[str]] = {}
    for f in findings:
        raisers.setdefault(f.fingerprint, [])
        for s in f.specialists:
            if s not in raisers[f.fingerprint]:
                raisers[f.fingerprint].append(s)
        cur = best.get(f.fingerprint)
        if cur is None or f.confidence > cur.confidence:
            best[f.fingerprint] = f
    out: list[Finding] = []
    for fp, f in best.items():
        f.specialists = tuple(raisers[fp])
        out.append(f)
    out.sort(key=lambda f: (-f.confidence, f.category, f.path))
    return out


def _gate(findings: list[Finding], threshold: int) -> list[Finding]:
    return [f for f in findings if f.confidence >= threshold]


def _apply_recurrence(
    findings: list[Finding], per_run: list[list[Finding]], total_runs: int
) -> list[Finding]:
    """Raise confidence for a finding that recurs across runs; a defect a reviewer
    catches on every pass is more likely real than one caught on a single pass.

    Recall is the priority on the merge path, so this never drops a finding -- a
    once-in-N finding still surfaces in the blocking review, just without the bump.
    Not a statistical test: a coarse heuristic (unanimous > majority > single) that
    damps variance without pretending to be `prove.py`'s paired-trial gate.
    """
    if total_runs <= 1:
        return findings
    counts: dict[str, int] = {}
    for run in per_run:
        for fp in {f.fingerprint for f in run}:
            counts[fp] = counts.get(fp, 0) + 1
    for f in findings:
        count = counts.get(f.fingerprint, 1)
        f.recurrence = count
        frac = count / total_runs
        bump = 2 if frac >= 1.0 else 1 if frac > 0.5 else 0
        f.confidence = min(10, f.confidence + bump)
    findings.sort(key=lambda f: (-f.confidence, f.category, f.path))
    return findings


# --------------------------------------------------------------------------- engine


def _user_prompt(diff_text: str, prior: list[Finding] | None = None) -> str:
    parts = ["Review this unified diff for defects in your specialty:\n", diff_text]
    if prior:
        # `recurrence` is a post-aggregation stat (always 1 mid-run, before per_run
        # is complete) -- meaningless as reviewer context, and including it would
        # shift the prompt hash cassettes are keyed on for no reason. Excluded here,
        # not from to_record() itself, so the final CLI/log output still carries it.
        prior_records = [
            {k: v for k, v in f.to_record().items() if k != "recurrence"} for f in prior
        ]
        prior_json = json.dumps(prior_records, indent=2)
        parts.append(
            "\n\nThe other specialists already reported these findings. Do not repeat "
            f"them; only add what they missed:\n{prior_json}"
        )
    return "".join(parts)


def review_diff(
    diff_text: str,
    profile: dict[str, Any],
    specialists: list[str] | None = None,
    *,
    runs: int = DEFAULT_LIVE_RUNS,
    backend: ReviewBackend | None = None,
    mode: str = DEFAULT_MODE,
    threshold: int | None = None,
    max_workers: int = 6,
) -> ReviewResult:
    """Review a diff with the selected specialists, repeated `runs` times.

    Returns a ReviewResult whose per_run captures each repetition's gated findings (so a
    caller can measure detection across runs) and whose findings is the deduped union.
    """
    backend = backend or ClaudeCLIBackend()
    if threshold is None:
        threshold = MODE_THRESHOLDS.get(mode, MODE_THRESHOLDS[DEFAULT_MODE])

    files = changed_files(diff_text)
    flags = diff_scope.scope(files, diff_text)
    profile_specs = specialists if specialists is not None else profile.get("specialists", [])
    registry = _base.load_registry(packs_for(profile))
    selected = _base.select(registry, list(profile_specs), flags)

    reports: dict[str, SpecialistReport] = {
        s.name: SpecialistReport(name=s.name, model=model_name(backend)) for s in selected
    }
    per_run: list[list[Finding]] = []

    for _ in range(runs):
        run_findings: list[Finding] = []
        workers = [s for s in selected if not s.is_redteam]
        redteam = [s for s in selected if s.is_redteam]

        def _call(
            spec: _base.Specialist, prior: list[Finding] | None = None
        ) -> list[Finding]:
            t0 = time.monotonic()
            rep = reports[spec.name]
            user_prompt = _user_prompt(diff_text, prior)
            reply = backend.dispatch(spec.name, spec.system_prompt, user_prompt)
            rep.dispatches += 1
            if reply is None:
                # A single transient failure (timeout, CLI error) gets one retry
                # before this specialist is marked incomplete -- mirrors the
                # verifier's retry-then-fail-closed shape rather than hard-blocking
                # on a network blip.
                logger.warning("specialist %s did not complete; retrying once", spec.name)
                reply = backend.dispatch(spec.name, spec.system_prompt, user_prompt)
                rep.dispatches += 1
            if reply is None:
                logger.warning("specialist %s failed again; marking incomplete", spec.name)
                rep.failed = True
                rep.latency += time.monotonic() - t0
                return []
            found = parse_findings(reply, spec.name, spec.category)
            rep.n_findings += len(found)
            rep.latency += time.monotonic() - t0
            return found

        if workers:
            with ThreadPoolExecutor(max_workers=min(max_workers, len(workers))) as pool:
                for found in pool.map(_call, workers):
                    run_findings.extend(found)

        for spec in redteam:
            run_findings.extend(_call(spec, prior=list(run_findings)))

        gated = _gate(run_findings, threshold)
        per_run.append(dedup(gated))

    union: list[Finding] = [f for run in per_run for f in run]
    merged = _apply_recurrence(dedup(union), per_run, runs)
    return ReviewResult(
        findings=merged,
        per_run=per_run,
        specialist_reports=list(reports.values()),
        runs=runs,
        mode=mode,
        threshold=threshold,
        selected=[s.name for s in selected],
        scope_flags=flags,
    )
