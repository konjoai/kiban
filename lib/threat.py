"""Trust-boundary classifier and brief-time threat-model record (Phase 13, Phase 3).

Sibling of `lib/oneway.py` and `lib/prove.py`, same shape: a pure classification
function with no model/network dependency, a session-side record step that demands
real content (not a rubber stamp), and a commit trailer CI reads without re-running the
classification.

Where this differs from `oneway`: a one-way door is binary (is this reversible or not).
Planned work can cross *several* trust boundaries in one change, each needing its own
named mitigation and abuse case -- there is no single "confirm" token that covers
"the webhook handler now also reads a header for auth," this needs one line per boundary
hit, not one line total.

Runs at brief time, not commit time -- classifying "what is this change about to do" is
a plan-time question. `gate_threat_model` (CI) never re-classifies; it only checks a
diff matching a repo's `security_globs` for the recorded trailer, the same
record-and-check split `gate_one_way_door`/`gate_prove` already use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lib import oneway

THREAT_TRAILER = "Konjo-Threat-Model"

# The eight trust-boundary classes named in Phase 13's brief. Fixed vocabulary --
# `record_threat_model` refuses a boundary name outside this set, the same way
# `konjo-learn` refuses a learning with no enforcement target: an unlisted boundary name
# is a typo or an invented category, neither of which belongs in a permanent record.
AUTHN_AUTHZ = "authn_authz"
SECRET_LIFECYCLE = "secret_lifecycle"
DESERIALIZATION = "deserialization"
SUBPROCESS_EXEC = "subprocess_exec"
PATH_HANDLING = "path_handling"
NETWORK_INGRESS = "network_ingress"
SQL_CONSTRUCTION = "sql_construction"
RESOURCE_LIMITS = "resource_limits"

TAXONOMY = (
    AUTHN_AUTHZ,
    SECRET_LIFECYCLE,
    DESERIALIZATION,
    SUBPROCESS_EXEC,
    PATH_HANDLING,
    NETWORK_INGRESS,
    SQL_CONSTRUCTION,
    RESOURCE_LIMITS,
)

# Heuristic hints only -- a starting point for the brief-time classification, not a
# substitute for it. Under-triggering is safe (the session still has to think about
# every boundary named in the sprint template's TRUST BOUNDARIES field); over-triggering
# just means a boundary gets a quick "not applicable" instead of silence.
_PATH_HINTS: list[tuple[str, re.Pattern[str]]] = [
    (AUTHN_AUTHZ, re.compile(r"(?i)(^|/)(auth|login|session|permission|rbac)")),
    (SECRET_LIFECYCLE, re.compile(r"(?i)(^|/)(secret|credential|token|key)[^/]*\.")),
    (SUBPROCESS_EXEC, re.compile(r"(?i)(^|/)(exec|spawn|subprocess|shell|command)")),
    (NETWORK_INGRESS, re.compile(r"(?i)(^|/)(webhook|server|api|handler|route)[^/]*\.")),
    (SQL_CONSTRUCTION, re.compile(r"(?i)(^|/)(query|repository|dao|migrations?)[^/]*\.")),
]

_DESERIALIZATION_RE = re.compile(
    r"(?i)\b(pickle\.loads|yaml\.load\b|json\.loads|eval\(|Deserialize)"
)
_SQL_RE = re.compile(r"(?i)\b(SELECT\b.{0,60}\bFROM\b|format!\(.{0,20}(SELECT|INSERT|UPDATE))")
_RESOURCE_LIMITS_RE = re.compile(
    r"(?im)\b(VecDeque::new\(\)|Vec::new\(\)|"
    r"(?:unbounded_channel|unbounded|channel)(?:::<[^()]*>)?\(\))\s*;?\s*$|\bwhile\s+true\b"
)

_DIFF_HINTS: list[tuple[str, re.Pattern[str]]] = [
    (AUTHN_AUTHZ, re.compile(r"(?i)\b(authenticat|authoriz|is_admin|permission|role)\w*\b")),
    (SECRET_LIFECYCLE, re.compile(r"(?i)\b(secret|api_key|credential|token)\w*\s*=")),
    (DESERIALIZATION, _DESERIALIZATION_RE),
    # `\.spawn\(\)` (a zero-arg method call) matches a process builder's terminal
    # call (`Command::new("x").spawn()`); a bare `spawn\(` also matched
    # `tokio::spawn(fut)`/`thread::spawn(closure)` -- in-process concurrency, not a
    # subprocess/OS-exec boundary at all. Found live (Phase 14, Phase 3's real
    # measurement): a `tokio::spawn(async move ...)` background task tripped this
    # hint on every run, unrelated to any actual subprocess.
    (
        SUBPROCESS_EXEC,
        re.compile(r"(?i)\b(subprocess\.|os\.system|Command::new|exec[lv])|\.spawn\(\)"),
    ),
    (PATH_HANDLING, re.compile(r"(?i)\b(path\.join|PathBuf::from|\.\./|realpath|canonicalize)")),
    (NETWORK_INGRESS, re.compile(r"(?i)\b(webhook|request\.(body|json)|axum::|#\[route)")),
    (SQL_CONSTRUCTION, _SQL_RE),
    (RESOURCE_LIMITS, _RESOURCE_LIMITS_RE),
]


@dataclass
class Classification:
    boundaries: list[str] = field(default_factory=list)
    reasons: dict[str, list[str]] = field(default_factory=dict)


def classify(changed_files: list[str], diff_text: str = "") -> Classification:
    """Heuristic hint of which trust boundaries this change plausibly touches.

    Advisory only -- see module docstring. Never used by the CI gate, which only checks
    for the recorded trailer.
    """
    reasons: dict[str, list[str]] = {}

    for boundary, pat in _PATH_HINTS:
        if any(pat.search(p) for p in changed_files):
            reasons.setdefault(boundary, []).append("path")

    for boundary, pat in _DIFF_HINTS:
        if pat.search(diff_text):
            reasons.setdefault(boundary, []).append("diff")

    return Classification(boundaries=sorted(reasons), reasons=reasons)


@dataclass
class BoundaryRecord:
    boundary: str
    mitigation: str
    abuse_case: str


class MissingContent(Exception):
    """A boundary hit was named with no mitigation or no abuse case -- refused."""


def record_threat_model(
    changed_files: list[str],
    records: list[BoundaryRecord],
    *,
    author: str = "unknown",
    ledger: object | None = None,
) -> str:
    """Record a brief-time threat model. Refuses a boundary with empty content.

    Every named boundary must carry a non-empty mitigation and a non-empty abuse case,
    the same "a note is not a learning without an enforcement target" discipline
    `lib/learnings.py` already applies to a different class of claim. "None" is a valid
    trust-boundary answer for the sprint template's own field, but that is a decision to
    record zero boundaries, not a boundary recorded with empty content.

    Logs to the Ledger (provenance, like `confirm.confirm_one_way`) and returns the
    commit trailer: `Konjo-Threat-Model: <fingerprint>`.
    """
    for rec in records:
        if rec.boundary not in TAXONOMY:
            raise MissingContent(f"{rec.boundary!r} is not in the fixed taxonomy: {TAXONOMY}")
        if not rec.mitigation.strip():
            raise MissingContent(f"boundary {rec.boundary!r} has no mitigation")
        if not rec.abuse_case.strip():
            raise MissingContent(f"boundary {rec.boundary!r} has no abuse case")

    fp = oneway.fingerprint(changed_files)
    if ledger is not None:
        summary = "; ".join(f"{r.boundary}: {r.mitigation}" for r in records) or "no boundaries hit"
        ledger.decide(  # type: ignore[attr-defined]
            f"THREAT-MODEL {fp}",
            summary,
            scope="org",
            alternatives_considered=[r.abuse_case for r in records],
            confidence=8 if records else 5,
            author=author,
        )
    return threat_trailer(fp)


def threat_trailer(fp: str) -> str:
    """The commit trailer CI reads: `Konjo-Threat-Model: <fingerprint>`."""
    return oneway.make_trailer(THREAT_TRAILER, fp)


def find_threat_model(messages: str, fp: str) -> bool:
    """True if a commit carries the Konjo-Threat-Model trailer for this fingerprint."""
    return oneway.find_trailer(messages, THREAT_TRAILER, fp)
