"""The keystone review interface shared by the live gate and the eval harness.

    review_diff(diff_text, profile, specialists=None, *, runs=1) -> ReviewResult

One function, two callers. The live review CLI passes the working diff; the eval harness
passes each fixture's diff.patch. They share this exact path so the eval exercises the
real gate, not a parallel mock.

Specialists are prompt-driven reviewers invoked through a backend: the Claude CLI in
production, a scripted backend in tests. Findings carry a stable fingerprint (path,
category, normalized summary, never the line number) so the same issue on a shifted line
dedups to one. A confidence gate drops low-confidence noise before anything is shown.
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


# --------------------------------------------------------------------------- backends


class ReviewBackend(Protocol):
    def dispatch(
        self, specialist: str, system_prompt: str, user_prompt: str, *, model: str | None = None
    ) -> str: ...


class ClaudeCLIBackend:
    """Production backend: invoke the Claude CLI in headless print mode.

    Reuses the konjo_wall3_cc.sh pattern (a single -p call returning text). The system
    prompt and the diff are combined into one prompt so the call does not depend on a
    specific system-prompt flag. Any failure returns empty text, which the parser treats
    as dispatched-with-zero-findings; a specialist call never crashes the review.
    """

    def __init__(self, model: str | None = None, timeout: int = 180) -> None:
        self.model = model or os.environ.get("KONJO_REVIEW_MODEL")
        self.timeout = timeout

    def dispatch(
        self, specialist: str, system_prompt: str, user_prompt: str, *, model: str | None = None
    ) -> str:
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
            return ""
        if proc.returncode != 0:
            logger.warning("specialist %s backend exit %d", specialist, proc.returncode)
        return proc.stdout


class ScriptedBackend:
    """Deterministic backend for tests. Returns canned replies keyed by specialist name."""

    def __init__(self, by_specialist: dict[str, str], default: str = "NO FINDINGS") -> None:
        self.by_specialist = by_specialist
        self.default = default
        self.calls: list[str] = []

    def dispatch(
        self, specialist: str, system_prompt: str, user_prompt: str, *, model: str | None = None
    ) -> str:
        self.calls.append(specialist)
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
        }


@dataclass
class SpecialistReport:
    name: str
    dispatches: int = 0
    n_findings: int = 0
    latency: float = 0.0
    model: str | None = None

    @property
    def dispatched(self) -> bool:
        return self.dispatches > 0


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


# --------------------------------------------------------------------------- engine


def _user_prompt(diff_text: str, prior: list[Finding] | None = None) -> str:
    parts = ["Review this unified diff for defects in your specialty:\n", diff_text]
    if prior:
        prior_json = json.dumps([f.to_record() for f in prior], indent=2)
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
    runs: int = 1,
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
            reply = backend.dispatch(spec.name, spec.system_prompt, _user_prompt(diff_text, prior))
            found = parse_findings(reply, spec.name, spec.category)
            rep = reports[spec.name]
            rep.dispatches += 1
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
    return ReviewResult(
        findings=dedup(union),
        per_run=per_run,
        specialist_reports=list(reports.values()),
        runs=runs,
        mode=mode,
        threshold=threshold,
        selected=[s.name for s in selected],
        scope_flags=flags,
    )
