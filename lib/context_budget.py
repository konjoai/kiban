"""context_budget: measure the always-on context cost so the framework cannot bloat.

kiban preaches token-efficient context, so it must hold itself to a budget the way it
dogfoods prose_lint and shellcheck. The risk in adding packs, skills, a learnings loop, and
a long-run protocol is that the always-on per-session context creeps up until the foundation
is heavy. This module measures it; the gate (in the orchestrator) enforces it.

What counts as always-on: the session-plane umbrella skill text a repo loads every session
(the ethos lives inside it). Packs and the other skills (decide, recall, correct, longrun,
craft) load only when invoked, so they are never always-on and do not count here. That is the
whole point of the pack seam: depth is paid for only on use.

Token counting is an estimate, not a tokenizer: tokens are approximated as ceil(chars / 4),
the standard rough ratio for English prose. The estimate is deliberate, so the gate has no
model dependency and stays deterministic offline. The ceiling carries headroom to absorb the
estimate's error.
"""

from __future__ import annotations

import math
from pathlib import Path

# The always-on skill: the umbrella that every consuming CLAUDE.md imports. Relative to the
# kiban root.
UMBRELLA_SKILL = "plugins/konjo/skills/konjo/SKILL.md"

# The default ceiling for the always-on set, in estimated tokens. Headroom over the measured
# core (the umbrella skill plus its ethos section). A profile may override with
# `context_budget_tokens`.
DEFAULT_BUDGET_TOKENS = 1500

# The default per-SKILL.md line cap. A skill over the cap needs an in-file justification (the
# one-way-door marker below), or it is a finding.
DEFAULT_SKILL_LINE_CAP = 80
SKILL_SIZE_OVERRIDE = "konjo-skill-size-ok:"

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """A deterministic, model-free token estimate: ceil(chars / 4)."""
    return math.ceil(len(text) / _CHARS_PER_TOKEN)


def always_on_tokens(root: Path, umbrella: str = UMBRELLA_SKILL) -> int:
    """Estimated token cost of the always-on set (the umbrella skill, ethos included)."""
    path = root / umbrella
    if not path.exists():
        return 0
    return estimate_tokens(path.read_text(encoding="utf-8"))


def skill_line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def skill_is_justified(path: Path) -> bool:
    """True if a SKILL.md carries the one-way-door size justification marker."""
    return SKILL_SIZE_OVERRIDE in path.read_text(encoding="utf-8")


def oversized_skills(
    root: Path, cap: int = DEFAULT_SKILL_LINE_CAP
) -> list[tuple[str, int]]:
    """SKILL.md files over the line cap with no recorded justification.

    Returns (relative-path, line-count) for each unjustified offender. A skill that carries
    the `konjo-skill-size-ok:` marker is exempt (its length is a recorded one-way door).
    """
    offenders: list[tuple[str, int]] = []
    skills_dir = root / "plugins"
    if not skills_dir.exists():
        return offenders
    for path in sorted(skills_dir.rglob("SKILL.md")):
        n = skill_line_count(path)
        if n > cap and not skill_is_justified(path):
            offenders.append((str(path.relative_to(root)), n))
    return offenders
