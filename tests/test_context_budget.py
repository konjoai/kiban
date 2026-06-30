"""Tests for the context-budget measure and its gates (lib/context_budget + cli)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PKG_SRC = _ROOT / "packages" / "konjo-gates-py" / "src"
for _p in (str(_ROOT), str(_PKG_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from konjo_gates_py import cli  # noqa: E402

from lib import context_budget  # noqa: E402


def test_estimate_tokens_is_chars_over_four() -> None:
    assert context_budget.estimate_tokens("") == 0
    assert context_budget.estimate_tokens("abcd") == 1
    assert context_budget.estimate_tokens("abcde") == 2  # ceil(5/4)


def test_core_always_on_is_under_default_ceiling() -> None:
    used = context_budget.always_on_tokens(_ROOT)
    assert 0 < used <= context_budget.DEFAULT_BUDGET_TOKENS


def test_context_budget_gate_passes_on_core() -> None:
    assert cli.gate_context_budget({}).status == cli.PASS


def test_context_budget_gate_warns_when_ceiling_too_low() -> None:
    r = cli.gate_context_budget({"context_budget_tokens": 1})
    assert r.status == cli.WARN
    assert not r.blocking  # report-only, never blocks


def test_skill_size_gate_passes_on_core() -> None:
    # craft is over the line cap but carries the justification marker; all others are under.
    assert cli.gate_skill_size({}).status == cli.PASS


def test_skill_size_gate_warns_with_tiny_cap() -> None:
    r = cli.gate_skill_size({"skill_line_cap": 5})
    assert r.status == cli.WARN
    assert not r.blocking


def test_oversized_skills_respects_justification_marker(tmp_path: Path) -> None:
    skills = tmp_path / "plugins" / "konjo" / "skills"
    (skills / "big").mkdir(parents=True)
    (skills / "ok").mkdir(parents=True)
    long_body = "\n".join(f"line {i}" for i in range(50))
    (skills / "big" / "SKILL.md").write_text(long_body)
    (skills / "ok" / "SKILL.md").write_text(
        "konjo-skill-size-ok: justified\n" + long_body
    )
    offenders = context_budget.oversized_skills(tmp_path, cap=10)
    names = [p for p, _ in offenders]
    assert any("big" in n for n in names)
    assert not any("ok" in n for n in names)  # the justified one is exempt
