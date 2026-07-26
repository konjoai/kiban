"""G-POLARITY engine: does an unknown path return a passing value?

For every early-return, fallback, default, or error branch, is the returned value the
*permissive* end of its range? Three real lopi sites answer "I could not evaluate this"
with a bare pass: `verifier_runner.rs`'s unconfigured-client branch returns `true` and
gates L4 auto-merge; `eval_runner.rs`'s mirrors it for the judge tier; `scorer.rs`'s
unrecognised-stack branch sets `test_pass_rate = 1.0`, a perfect score for zero tests run.
All three passed every existing gate. This is the shape that catches them.

Detection is a small per-language regex/block scan (`lib/packs/lang/{rust,python,
typescript}/polarity.py`), not a full AST: find a branch whose *condition* tests for
absence or failure to evaluate (`let ... else`, `.is_none()`, `.unwrap_or(...)`, a
match/switch arm on the error or default case, Python's `except`/`is None`/`.get(k,
default)`, TypeScript's `??`/`if (!x)`/`catch`), then check whether that branch's body
sets or returns a permissive value (bare `true`, a numeric constant at the top of its
declared range such as `1.0`, `Ok(())`).

**The separating signal** (this is what keeps `verifier_error_proceeds` and
`zero_diff_is_success` out of the finding set, and it is deliberate, not an oversight):
every condition pattern here tests *whether evaluation was possible*
(`api_client.is_none()`, an `except` clause, a match arm on `Err`/`None`). None of them
test a domain fact (`until_satisfied`, `skip_build_check`, a plain `if proceed`). A bare
boolean check or an OR of two domain predicates never matches any pattern here, by
construction -- it is not down-ranked, it is simply not the shape this engine looks for.
Where a condition's shape is ambiguous between "could not evaluate" and "chose not to"
(the `else` arm of a 2-way if/else with no enclosing chain, or a permissive value routed
through a named operator field rather than a bare literal), this engine does not flag it.
**That is a deliberate false negative, not a bug**: a gate that cannot tell the two apart
is worse than one that occasionally misses, per the KT-K1.1 kill-test that shaped this
design (`.konjo/killtests/K1/KT-K1.1.md`).

**Limit, stated here because this is where it will be read:** this engine cannot judge a
threshold. It finds branches returning the permissive value; a branch returning the
*restrictive* value set at the wrong level (a score capped at 1.0 that should have been
capped at 0.3, a timeout of 30s that should have been 3s) passes it clean. That residual
is not closable by this gate; see `KONJO_FORWARD.md`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

# file extension -> the lib.packs.lang.<pack>.polarity module that scans it
_EXT_TO_PACK = {
    ".rs": "rust",
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    condition: str
    returned: str

    def format(self) -> str:
        return (
            f"{self.path}:{self.line}: {self.rule}: condition {self.condition!r} "
            f"returns permissive value {self.returned!r}"
        )

    def key(self) -> tuple[str, str, str]:
        """Identity for net-new comparison: rule + condition + returned text, never the
        line number -- a line shifts when unrelated earlier code changes, exactly the
        reason `prose_lint`'s net-new diff also keys on content, not position."""
        return (self.rule, self.condition, self.returned)


# An operator-facing override field name in the returned expression -- the
# `verifier_fail_open` precedent. A permissive value that traces to a named override
# rather than a bare literal is an explicit, recorded opt-out, not a silent pass. This is
# deliberately narrow: it will not recognize every legitimate override field, but it will
# never treat a bare `true`/`1.0` literal as one, which is the failure mode that matters.
_OVERRIDE_NAME_RE = re.compile(r"(?i)fail_open|_override\b|opt(?:ed)?_in\b")


def is_explicit_override(finding: Finding) -> bool:
    """True when the finding's returned expression names an operator override field."""
    return bool(_OVERRIDE_NAME_RE.search(finding.returned))


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def block_end_braces(lines: list[str], start: int) -> int:
    """Index of the line where the `{`-block opened on `lines[start]` closes.

    Naive brace counting (no string/comment awareness), the same simplification
    `lib/unsafe_budget.py` already makes for Rust's `unsafe` blocks. Good enough for a
    lint-style scan; a scanner that needed to be exact would parse, not grep.

    Counts from the LAST `{` on the start line, not the whole line's net brace delta: a
    chain header like `} else {` closes a sibling block (the preceding `else if`) and
    opens this one on the same line, and a naive whole-line count nets those to zero --
    reading as "already closed" before this block's body is ever scanned. Only the
    braces after that final `{` (this line's tail, then every following line) count
    toward this block's own depth.
    """
    line = lines[start]
    open_pos = line.rfind("{")
    if open_pos == -1:
        depth = line.count("{") - line.count("}")
    else:
        tail = line[open_pos + 1 :]
        depth = 1 + tail.count("{") - tail.count("}")
    if depth <= 0:
        return start
    for i in range(start + 1, len(lines)):
        depth += lines[i].count("{") - lines[i].count("}")
        if depth <= 0:
            return i
    return len(lines) - 1


def block_end_indent(lines: list[str], start: int) -> int:
    """Index of the last line of the indented block that opens on `lines[start]`
    (Python-style: header ends in `:`, body is every following line indented deeper)."""
    base = _indent(lines[start])
    end = start
    for i in range(start + 1, len(lines)):
        if lines[i].strip() == "":
            end = i
            continue
        if _indent(lines[i]) > base:
            end = i
        else:
            break
    return end


def _scanner_for(path: str):
    pack = _EXT_TO_PACK.get(Path(path).suffix)
    if pack is None:
        return None
    module = import_module(f"lib.packs.lang.{pack}.polarity")
    return module.scan


def lint_text(text: str, path: str = "<text>") -> list[Finding]:
    """Return every G-POLARITY finding in a block of text, dispatched by `path`'s
    extension to the matching language pack. An unrecognised extension yields no
    findings (a report-only gap, not a crash)."""
    scanner = _scanner_for(path)
    if scanner is None:
        return []
    return [
        Finding(path=path, line=line, rule=rule, condition=condition, returned=returned)
        for line, rule, condition, returned in scanner(text)
    ]


def lint_file(path: str | Path) -> list[Finding]:
    """Lint one file. Unreadable, binary, or unrecognised-language files produce no
    findings."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return lint_text(text, str(p))
