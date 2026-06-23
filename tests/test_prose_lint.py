"""Tests for the editorial prose lint."""

from __future__ import annotations

from lib import prose_lint


def test_flags_em_dash() -> None:
    findings = prose_lint.lint_text("a sentence — with an em dash")
    assert any(f.rule == "em-dash" for f in findings)


def test_flags_one_ai_tell_word() -> None:
    findings = prose_lint.lint_text("this is a robust solution")
    tells = [f for f in findings if f.rule == "ai-tell"]
    assert len(tells) == 1
    assert tells[0].token.lower() == "robust"


def test_silent_on_clean_prose() -> None:
    assert prose_lint.lint_text("a plain clear sentence with no tells") == []


def test_reports_line_and_col() -> None:
    findings = prose_lint.lint_text("ok line\na crucial thing", path="x.md")
    f = next(f for f in findings if f.rule == "ai-tell")
    assert f.line == 2
    assert f.col == 3
    assert f.path == "x.md"


def test_en_dash_as_em_flagged() -> None:
    findings = prose_lint.lint_text("a sentence – with a spaced en dash")
    assert any(f.rule == "en-dash-as-em" for f in findings)
