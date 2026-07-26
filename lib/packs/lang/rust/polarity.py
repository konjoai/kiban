"""Rust condition/permissive-value shapes for G-POLARITY.

Four shapes, matched by construction to the three real lopi defects plus the two
reference-correct fixtures the gate must never flag (see `.konjo/killtests/K1/
KT-K1.1.md`):

1. `let Some(x) = ... else { ... }` -- the `else` body is the "could not bind" branch.
2. `if <expr>.is_none() ... { ... }` (optionally `&&`-combined with a domain check; the
   `is_none()` clause is still the dominant "could not evaluate" signal).
3. A `match` arm on `Err(...)` or `None`.
4. The terminal, unconditioned `else` of an if/else-if chain of three or more branches --
   the dispatch's "none of the known cases matched" default. A plain 2-way `if/else` is
   NOT treated as this shape: a binary choice is far more likely a domain decision (see
   `zero_diff_is_success`) than "unrecognised input", and this engine prefers a false
   negative there over flagging every ordinary `if/else` in the language.

Each shape's body is searched for a permissive statement: `return true`, an assignment or
return of a bare `true`, `1.0` (the top of a 0.0-1.0 score range), or `Ok(())`.

Not implemented as its own shape: a bare `.ok()?` fallthrough (`resolve(x).ok()?;`,
propagating `None` immediately via `?`). It signals the same "could not evaluate", but
it has no `{}` body for this scanner to search for a permissive statement -- the `?`
propagates the absence itself rather than falling into a block. Named in the vocabulary
for completeness; left undetected rather than reported unreliably.
"""

from __future__ import annotations

import re

from lib.polarity import block_end_braces

_LET_ELSE_RE = re.compile(r"^\s*let\s+(?:Some|Ok)\([^()]*\)\s*=.*\belse\s*\{")
_IF_HEAD_RE = re.compile(r"^\s*\}?\s*(?:else\s+)?if\b")
_ABSENCE_COND_RE = re.compile(r"\.is_none\(\)|\.unwrap_or(?:_default)?\(")
_MATCH_ARM_RE = re.compile(r"\b(?:Err\([^)]*\)|None)\s*=>\s*(.+?),?\s*$")
_BARE_ELSE_HEAD_RE = re.compile(r"^\s*\}\s*else\s*\{\s*$")
_ELSE_IF_RE = re.compile(r"^\s*\}\s*else\s+if\b")
_IF_START_RE = re.compile(r"^\s*if\b")

_PERMISSIVE_RE = re.compile(
    r"\breturn\s+true\b"
    r"|^\s*true\s*;?\s*$"
    r"|=\s*true\s*;"
    r"|=\s*1\.0\s*;"
    r"|\breturn\s+1\.0\b"
    r"|\bOk\(\(\)\)\s*;?\s*$"
)


def _find_permissive(lines: list[str], start: int, end: int) -> str | None:
    for i in range(start, min(end, len(lines) - 1) + 1):
        m = _PERMISSIVE_RE.search(lines[i])
        if m:
            return m.group(0).strip()
    return None


def _has_preceding_else_if(lines: list[str], else_idx: int) -> bool:
    """True if the terminal `else` at `else_idx` is preceded, at the same indentation, by
    at least one `} else if` before the chain's originating `if` -- i.e. this is a 3+-way
    dispatch, not a plain 2-way if/else."""
    indent = len(lines[else_idx]) - len(lines[else_idx].lstrip(" \t"))
    j = else_idx - 1
    count = 0
    while j >= 0:
        line = lines[j]
        if line.strip() == "":
            j -= 1
            continue
        cur_indent = len(line) - len(line.lstrip(" \t"))
        if cur_indent == indent:
            stripped = line.strip()
            if _ELSE_IF_RE.match(line):
                count += 1
            elif _IF_START_RE.match(stripped) and not stripped.startswith("else"):
                return count >= 1
        j -= 1
    return False


def scan(text: str) -> list[tuple[int, str, str, str]]:
    """Return (line, rule, condition, returned) for every G-POLARITY finding."""
    lines = text.splitlines()
    findings: list[tuple[int, str, str, str]] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        if _LET_ELSE_RE.search(line):
            end = block_end_braces(lines, i)
            perm = _find_permissive(lines, i, end)
            if perm:
                findings.append((i + 1, "absence-let-else", line.strip(), perm))
            i = end + 1
            continue

        if _IF_HEAD_RE.match(line) and _ABSENCE_COND_RE.search(line):
            end = block_end_braces(lines, i)
            perm = _find_permissive(lines, i + 1, end)
            if perm:
                findings.append((i + 1, "absence-if-condition", line.strip(), perm))
            i = end + 1
            continue

        m = _MATCH_ARM_RE.search(line)
        if m:
            val = m.group(1)
            pm = _PERMISSIVE_RE.search(val)
            if pm:
                findings.append((i + 1, "absence-match-arm", line.strip(), val.strip()))
            i += 1
            continue

        if _BARE_ELSE_HEAD_RE.match(line) and _has_preceding_else_if(lines, i):
            end = block_end_braces(lines, i)
            perm = _find_permissive(lines, i + 1, end)
            if perm:
                findings.append((i + 1, "absence-default-branch", line.strip(), perm))
            i = end + 1
            continue

        i += 1
    return findings
