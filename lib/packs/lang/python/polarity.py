"""Python condition/permissive-value shapes for G-POLARITY.

Three block shapes (a header ending in `:`, body is the following more-indented lines)
plus one one-line expression shape:

1. `except ...:` -- the handler is the "could not evaluate" branch.
2. `if x is None:` -- an explicit absence check.
3. `if not x:` -- the same shape spelled the other way (`not x` reads as "x is falsy /
   absent / unset" far more often than a considered domain negation; kept narrow -- a
   single bare `not <name-like atom>` condition, not an arbitrary boolean expression --
   so an ordinary domain negation like `if not until_satisfied:` is not swept in merely
   for using `not`).
4. `d.get(k, default)` where `default` is a bare permissive literal -- the fallback IS the
   mechanism, so this is checked as a one-line expression, not a block.
"""

from __future__ import annotations

import re

from lib.polarity import block_end_indent

_EXCEPT_RE = re.compile(r"^\s*except\b[^:]*:\s*$")
_IS_NONE_RE = re.compile(r"^\s*if\b.*\bis\s+None\b.*:\s*$")
_NOT_X_RE = re.compile(r"^\s*if\s+not\s+[\w.\[\]'\"]+\s*:\s*$")
_GET_DEFAULT_RE = re.compile(r"\.get\([^,()]+,\s*(True|1\.0)\s*\)")

_PERMISSIVE_RE = re.compile(r"\breturn\s+True\b|=\s*True\s*$|=\s*1\.0\s*$")


def _find_permissive(lines: list[str], start: int, end: int) -> str | None:
    for i in range(start, min(end, len(lines) - 1) + 1):
        m = _PERMISSIVE_RE.search(lines[i].rstrip())
        if m:
            return m.group(0).strip()
    return None


def scan(text: str) -> list[tuple[int, str, str, str]]:
    lines = text.splitlines()
    findings: list[tuple[int, str, str, str]] = []
    for i, line in enumerate(lines):
        if _EXCEPT_RE.match(line):
            end = block_end_indent(lines, i)
            perm = _find_permissive(lines, i + 1, end)
            if perm:
                findings.append((i + 1, "absence-except", line.strip(), perm))
            continue
        if _IS_NONE_RE.match(line):
            end = block_end_indent(lines, i)
            perm = _find_permissive(lines, i + 1, end)
            if perm:
                findings.append((i + 1, "absence-is-none", line.strip(), perm))
            continue
        if _NOT_X_RE.match(line):
            end = block_end_indent(lines, i)
            perm = _find_permissive(lines, i + 1, end)
            if perm:
                findings.append((i + 1, "absence-not-x", line.strip(), perm))
            continue
        m = _GET_DEFAULT_RE.search(line)
        if m:
            findings.append((i + 1, "absence-get-default", line.strip(), m.group(1)))
    return findings
