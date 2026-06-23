"""Prose lint: the editorial gate, dogfooded across this repo's own docs.

Flags two things:
  1. Em dashes, and en dashes used as em dashes (an en dash padded by spaces).
  2. The AI-tell wordlist, tuned to Konjo taste. Whole-word, case-insensitive.

Reports file:line:col with the offending token. The CLI wrapper exits 1 on any
finding (blocking) or 0 in --warn mode (print but pass), so docs can run non-blocking
while article branches stay strict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Top-level, tuned to Konjo taste. Keep this the single source of the banned vocab.
AI_TELL_WORDS: tuple[str, ...] = (
    "delve",
    "crucial",
    "robust",
    "comprehensive",
    "nuanced",
    "multifaceted",
    "furthermore",
    "moreover",
    "pivotal",
    "landscape",
    "tapestry",
    "underscore",
    "foster",
    "showcase",
    "intricate",
)

EM_DASH = "—"
EN_DASH = "–"

_WORD_RE = re.compile(r"(?i)\b(" + "|".join(re.escape(w) for w in AI_TELL_WORDS) + r")\b")
# An en dash flanked by spaces is an em dash worn as a costume.
_EN_AS_EM_RE = re.compile(r"\s" + EN_DASH + r"\s")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    col: int
    rule: str
    token: str

    def format(self) -> str:
        return f"{self.path}:{self.line}:{self.col}: {self.rule}: {self.token!r}"


def lint_text(text: str, path: str = "<text>") -> list[Finding]:
    """Return every finding in a block of text."""
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for col, ch in enumerate(line, start=1):
            if ch == EM_DASH:
                findings.append(Finding(path, lineno, col, "em-dash", EM_DASH))
        for m in _EN_AS_EM_RE.finditer(line):
            findings.append(
                Finding(path, lineno, m.start() + 1, "en-dash-as-em", m.group().strip())
            )
        for m in _WORD_RE.finditer(line):
            findings.append(
                Finding(path, lineno, m.start() + 1, "ai-tell", m.group())
            )
    findings.sort(key=lambda f: (f.line, f.col))
    return findings


def lint_file(path: str | Path) -> list[Finding]:
    """Lint one file. Unreadable or binary files produce no findings."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return lint_text(text, str(p))
