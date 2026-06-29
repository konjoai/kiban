"""unsafe-budget: a kiban-native, diff-only gate for Rust `unsafe`.

The rule: a change must not raise the count of `unsafe` blocks that carry no adjacent
safety comment. It reads the unified diff; it never builds the crate. This is the cheap,
mechanical complement to the `ownership-lifetimes` review lane: the lane reasons about
soundness, this gate just refuses a silent growth in unjustified `unsafe`.

An `unsafe` block is an added/removed line that opens one: `unsafe {`, `unsafe fn`,
`unsafe impl`, `unsafe trait`. A block is "justified" when a `SAFETY` comment sits on a
nearby line in the same hunk (the convention `// SAFETY: ...`). Net change is the count of
added unjustified blocks minus removed blocks; a net increase fails.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Opens an unsafe block/impl/fn/trait. Matches the `unsafe` keyword followed by `{` or one
# of the item keywords, so a mere identifier containing "unsafe" does not trip it.
_UNSAFE_RE = re.compile(r"\bunsafe\s*(\{|fn\b|impl\b|trait\b)")
_SAFETY_RE = re.compile(r"safety\b", re.IGNORECASE)

# How many lines back (within the hunk) a SAFETY comment may sit to justify an unsafe block.
_SAFETY_LOOKBACK = 3


@dataclass
class UnsafeBudget:
    added_unjustified: int
    removed: int

    @property
    def net(self) -> int:
        return self.added_unjustified - self.removed

    @property
    def fails(self) -> bool:
        return self.net > 0


def _hunks(diff_text: str) -> list[list[str]]:
    """Split a unified diff into per-hunk line lists (the lines after each @@ header)."""
    hunks: list[list[str]] = []
    cur: list[str] | None = None
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            cur = []
            hunks.append(cur)
        elif cur is not None:
            # Skip file headers that can appear between hunks.
            if line.startswith(("+++ ", "--- ", "diff --git ")):
                cur = None
                continue
            cur.append(line)
    return hunks


def _justified(hunk: list[str], idx: int) -> bool:
    """True if a SAFETY comment sits within the lookback window before line idx in the hunk
    (counting added and context lines, ignoring the +/- marker)."""
    start = max(0, idx - _SAFETY_LOOKBACK)
    for j in range(start, idx):
        line = hunk[j]
        if line.startswith("-"):
            continue  # a removed line cannot justify an added block
        if _SAFETY_RE.search(line):
            return True
    return False


def scan(diff_text: str) -> UnsafeBudget:
    """Count added-unjustified and removed `unsafe` blocks across the diff."""
    added_unjustified = 0
    removed = 0
    for hunk in _hunks(diff_text):
        for i, line in enumerate(hunk):
            if line.startswith("+") and _UNSAFE_RE.search(line[1:]):
                if not _justified(hunk, i):
                    added_unjustified += 1
            elif line.startswith("-") and _UNSAFE_RE.search(line[1:]):
                removed += 1
    return UnsafeBudget(added_unjustified=added_unjustified, removed=removed)
