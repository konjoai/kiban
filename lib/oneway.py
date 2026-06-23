"""One-way-door classifier: which changes are hard or costly to reverse.

A two-way door is cheap to revert (most code edits, docs, additive changes). A one-way
door is not: schema and data migrations, public-API removals, data deletes, key
rotation, and release actions (a VERSION bump that triggers a release, a tag, a publish,
a force-push, a brew formula). One-way doors must be acknowledged explicitly, not
auto-blocked and not silently allowed.

The classifier errs toward asking: on a sensitive surface where intent is unclear it
returns one-way. A plain edit with no sensitive path and no destructive pattern is
two-way.

The acknowledgement that CI can read travels in git, not in ~/.konjo: a commit trailer
`Konjo-Acknowledged-Oneway: <fingerprint>`. The fingerprint is a stable hash of the
sorted changed-file set, so the confirm step and the CI check agree on the same change.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

ACK_TRAILER = "Konjo-Acknowledged-Oneway"


@dataclass
class Classification:
    door: str  # "one-way" or "two-way"
    reasons: list[str] = field(default_factory=list)
    confidence: int = 0

    @property
    def is_one_way(self) -> bool:
        return self.door == "one-way"


# Path rules: a changed file whose path matches is a one-way surface.
_PATH_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("schema-or-migration", re.compile(r"(^|/)migrations?/|(^|/)schema[^/]*\.|\.sql$")),
    ("release-version", re.compile(r"(^|/)VERSION$")),
    ("release-formula", re.compile(r"(^|/)Formula/")),
    ("release-workflow", re.compile(r"(^|/)\.github/workflows/.*(release|publish|deploy)")),
    ("key-material", re.compile(r"\.pem$|\.key$|(^|/)id_(rsa|ed25519)$|(^|/)\.env$")),
]

# Diff patterns: a destructive or release action in the added/removed lines.
_DIFF_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("data-delete", re.compile(r"(?i)\b(DROP\s+TABLE|DELETE\s+FROM|TRUNCATE)\b")),
    ("destructive-shell", re.compile(r"(?i)\brm\s+-rf\b|\bgit\s+push\s+(--force|-f)\b|force-push")),
    ("publish", re.compile(r"(?i)\b(twine\s+upload|npm\s+publish|gh\s+release\s+create)\b")),
    ("model-publish", re.compile(r"(?i)(huggingface|hf)[^\n]{0,40}(push|upload)")),
    ("key-rotation", re.compile(r"(?i)\brotat\w*\b[^\n]{0,30}\b(key|secret|credential|token)")),
]

# A removed top-level def/class is a public-API break.
_REMOVED_DEF = re.compile(r"(?m)^-\s*(?:async\s+)?(?:def|class)\s+\w")
# A sensitive surface touched without a specific destructive match is still one-way
# (ambiguous on a risky path errs toward asking).
_SENSITIVE_DIR = re.compile(r"(^|/)(migrations?|schema|releases?)(/|$)")


def fingerprint(changed_files: list[str]) -> str:
    """Stable id for a change, keyed on the sorted file set. Confirm and CI agree on it."""
    key = "\n".join(sorted(changed_files))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def classify(changed_files: list[str], diff_text: str = "") -> Classification:
    reasons: list[str] = []

    for name, pat in _PATH_RULES:
        if any(pat.search(p) for p in changed_files):
            reasons.append(f"path:{name}")

    for name, pat in _DIFF_RULES:
        if pat.search(diff_text):
            reasons.append(f"diff:{name}")

    if _REMOVED_DEF.search(diff_text):
        reasons.append("diff:public-api-removal")

    # Ambiguous-on-a-sensitive-surface errs toward one-way.
    if not reasons and any(_SENSITIVE_DIR.search(p) for p in changed_files):
        reasons.append("ambiguous-on-sensitive-path")

    if reasons:
        # Confidence scales with how many independent signals fired, capped at 10.
        return Classification(door="one-way", reasons=reasons, confidence=min(10, 5 + len(reasons)))
    return Classification(door="two-way", reasons=[], confidence=8)


def ack_trailer(fp: str) -> str:
    """The commit-trailer line a confirmed one-way door carries for CI to read."""
    return f"{ACK_TRAILER}: {fp}"


def find_ack(messages: str, fp: str) -> bool:
    """True if any commit message carries the acknowledgement trailer for this change."""
    pat = re.compile(rf"^{re.escape(ACK_TRAILER)}:\s*{re.escape(fp)}\b", re.MULTILINE)
    return bool(pat.search(messages))
