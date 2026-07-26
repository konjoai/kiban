"""TypeScript condition/permissive-value shapes for G-POLARITY.

1. `if (!x) { ... }` -- an explicit absence/falsy check.
2. `catch (...) { ... }` / `catch { ... }` -- the "could not evaluate" branch.
3. `x ?? true` / `x ?? 1.0` -- nullish coalescing straight to a permissive literal is a
   one-line expression, checked directly rather than as a block.
"""

from __future__ import annotations

import re

from lib.polarity import block_end_braces

_IF_NOT_RE = re.compile(r"^\s*\}?\s*if\s*\(\s*!\s*[\w.]+")
_CATCH_RE = re.compile(r"^\s*\}?\s*catch\s*(?:\([^)]*\))?\s*\{")
_NULLISH_RE = re.compile(r"\?\?\s*(true|1\.0)\b")

_PERMISSIVE_RE = re.compile(r"\breturn\s+true\b|=\s*true\s*;|=\s*1\.0\s*;")


def _find_permissive(lines: list[str], start: int, end: int) -> str | None:
    for i in range(start, min(end, len(lines) - 1) + 1):
        m = _PERMISSIVE_RE.search(lines[i])
        if m:
            return m.group(0).strip()
    return None


def scan(text: str) -> list[tuple[int, str, str, str]]:
    lines = text.splitlines()
    findings: list[tuple[int, str, str, str]] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _IF_NOT_RE.match(line):
            end = block_end_braces(lines, i)
            perm = _find_permissive(lines, i + 1, end)
            if perm:
                findings.append((i + 1, "absence-if-not", line.strip(), perm))
            i = end + 1
            continue
        if _CATCH_RE.match(line):
            end = block_end_braces(lines, i)
            perm = _find_permissive(lines, i + 1, end)
            if perm:
                findings.append((i + 1, "absence-catch", line.strip(), perm))
            i = end + 1
            continue
        m = _NULLISH_RE.search(line)
        if m:
            findings.append((i + 1, "absence-nullish-coalesce", line.strip(), m.group(1)))
        i += 1
    return findings
