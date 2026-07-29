"""CLAUDE.md section contract (Phase 13, Phase 1): the org import audit, made permanent.

A consuming repo's root CLAUDE.md is always-on context -- every session reads it before
writing a line of code. S13 Phase 0 audited lopi's self-claims in that file once; this
module makes that audit mechanical and repeatable, org-wide, offline, with no model and
no network.

Two checks:

1. **Section contract.** `REQUIRED_SECTIONS`, in order: org rules, stack, commands,
   invariants, repo map, repo-specific rules. A repo may add its own extra headings
   (e.g. "Pinning") -- only the required ones are checked, and only their relative
   order against each other, not their position among any extras.
2. **Enforcement naming.** Every bullet under a heading matching `invariant`/`hard rule`
   must name the gate that enforces it (`gate_x`, `konjo-x`) or say `ADVISORY`
   explicitly. An unenforced "invariant" is a claim with no consumer -- the same class
   of failure as a rubric with no reader.

A third, related check lives here too: `citation_ratio`, for the incident-log failure
mode. A rules file where a majority of lines end in a sprint or date citation is a log
of what broke, not a statement of what to check -- it records incidents, not
invariants, and should be split into the two.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ORG_IMPORT_RE = re.compile(r"@~/\.konjo/kiban/.*SKILL\.md")

# Matched by heading PREFIX (case-insensitive), so a repo can extend a heading's title
# (e.g. "## Org rules (imported from kiban)") without breaking the contract on wording.
REQUIRED_SECTIONS = (
    "org rules",
    "stack",
    "commands",
    "invariants",
    "repo map",
    "repo-specific rules",
)

_HEADING_RE = re.compile(r"^##\s+(.*)$", re.MULTILINE)
_INVARIANT_HEADING_RE = re.compile(r"invariant|hard.rule", re.IGNORECASE)

# A bullet under an invariants/hard-rules heading must name its enforcement: a gate
# function (`gate_x`), a repo-native tool the dispatcher runs (`repo:x`), a konjo-*
# command, or say ADVISORY explicitly. Anything else is a claim with no consumer.
_ENFORCEMENT_RE = re.compile(
    r"`?gate_[a-z_]+`?|`?repo:[a-z0-9_-]+`?|`?konjo-[a-z-]+`?|\bADVISORY\b", re.IGNORECASE
)

# A rules file where a majority of lines carry a sprint/date citation is recording
# incidents, not invariants -- the incident-log failure mode (lopi's
# .claude/rules/security.md, pre-Phase-13: WhatsApp/MCP/env-allowlist lines each ending
# "Sprint S10, Phase N"). Deliberately narrow: a sprint reference or a literal
# parenthesized date, not any digit-bearing token (a version number is not a citation).
_CITATION_RE = re.compile(
    r"\bSprint\s+\S+.{0,20}Phase\s+\d+"
    r"|\(\d{4}-\d{2}-\d{2}\)"
)


@dataclass
class ContractCheck:
    ok: bool
    missing_sections: list[str] = field(default_factory=list)
    out_of_order: list[str] = field(default_factory=list)
    has_org_import: bool = True
    unenforced_bullets: list[str] = field(default_factory=list)


def _headings(text: str) -> list[str]:
    return [h.strip().lower() for h in _HEADING_RE.findall(text)]


def check_contract(text: str) -> ContractCheck:
    """Check a whole CLAUDE.md body against the fixed section contract."""
    headings = _headings(text)

    def _find(section: str) -> int | None:
        for i, h in enumerate(headings):
            if h.startswith(section):
                return i
        return None

    positions = {s: _find(s) for s in REQUIRED_SECTIONS}
    missing = [s for s in REQUIRED_SECTIONS if positions[s] is None]

    present: list[tuple[str, int]] = [
        (s, pos) for s in REQUIRED_SECTIONS if (pos := positions[s]) is not None
    ]
    present_by_position = sorted(present, key=lambda si: si[1])
    expected_order = [s for s, _ in present]
    actual_order = [s for s, _ in present_by_position]
    out_of_order = expected_order if actual_order != expected_order else []

    has_import = bool(ORG_IMPORT_RE.search(text))
    unenforced = _unenforced_invariant_bullets(text)

    ok = not missing and not out_of_order and has_import and not unenforced
    return ContractCheck(ok, missing, out_of_order, has_import, unenforced)


def _unenforced_invariant_bullets(text: str) -> list[str]:
    in_invariants = False
    out: list[str] = []
    for line in text.splitlines():
        heading = _HEADING_RE.match(line)
        if heading:
            in_invariants = bool(_INVARIANT_HEADING_RE.search(heading.group(1)))
            continue
        if not in_invariants:
            continue
        stripped = line.strip()
        if not stripped.startswith(("-", "*")):
            continue
        if not _ENFORCEMENT_RE.search(stripped):
            out.append(stripped)
    return out


def citation_ratio(text: str) -> float:
    """Fraction of a rules file's substantive lines that carry a sprint/date citation.

    Skips blank lines, heading lines, and the YAML front-matter `---` delimiters. A high
    ratio (this module's gate uses > 0.5, i.e. a majority) marks an incident log, not an
    invariant set.
    """
    lines = [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith("#") and ln.strip() != "---"
    ]
    if not lines:
        return 0.0
    cited = sum(1 for ln in lines if _CITATION_RE.search(ln))
    return cited / len(lines)
