"""Tests for lib/cortex.py -- KT-2 (projection fidelity) and idempotency."""

from __future__ import annotations

from pathlib import Path

import pytest

from ledger.engine import Ledger
from lib import cortex


@pytest.fixture()
def ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Ledger:
    monkeypatch.setenv("KONJO_STATE_DIR", str(tmp_path))
    return Ledger("ledger/decisions.jsonl")


def test_kt2_chain_and_redact_fidelity(ledger: Ledger) -> None:
    """KT-2: decide A, supersede A->B, supersede B->C, redact unrelated D.

    Exact match on active set, full chain visible, no field loss.
    """
    a = ledger.decide(
        "Use SQLite for local cache",
        "Zero-ops, single file",
        scope="repo:demo",
        alternatives_considered=["Postgres", "flat files"],
        confidence=6,
        author="wes",
    )
    b = ledger.supersede(
        a,
        "Use SQLite with WAL mode",
        "Concurrent readers were blocking on the default journal mode",
        alternatives_considered=["Postgres"],
        confidence=7,
        author="wes",
    )
    c = ledger.supersede(
        b,
        "Use SQLite with WAL mode and a busy_timeout",
        "WAL alone still surfaced SQLITE_BUSY under load",
        alternatives_considered=["retry loop in application code"],
        confidence=8,
        author="wes",
    )
    d = ledger.decide(
        "Log at INFO by default",
        "DEBUG was too noisy in production",
        scope="repo:demo",
        confidence=5,
        author="wes",
    )
    ledger.redact_decision(d, "superseded by structured logging sprint, unrelated to cache")

    page = cortex.render_scope(ledger, "repo:demo")

    # Active set: exactly C, nothing else.
    assert "Use SQLite with WAL mode and a busy_timeout" in page
    active_section = page.split("## Active decisions")[1].split("## Retired")[0]
    assert c in active_section
    assert "busy_timeout" in active_section

    # Full chain A -> B -> C visible, in order, in the active section.
    assert f"{a} -> {b} -> {c}" in active_section
    assert "Use SQLite for local cache" in active_section
    assert "Use SQLite with WAL mode" in active_section

    # No field loss: rationale/alternatives/confidence preserved for every link.
    assert "Zero-ops, single file" in active_section
    assert "Postgres, flat files" in active_section
    assert "6/10" in active_section
    assert "Concurrent readers were blocking on the default journal mode" in active_section
    assert "7/10" in active_section
    assert "WAL alone still surfaced SQLITE_BUSY under load" in active_section
    assert "retry loop in application code" in active_section
    assert "8/10" in active_section

    # D omitted from active, but not erased -- present in Retired with its reason.
    assert "Log at INFO by default" not in active_section
    retired_section = page.split("## Retired")[1]
    assert "Log at INFO by default" in retired_section
    assert d in retired_section
    assert "superseded by structured logging sprint" in retired_section


def test_idempotent_fold_is_byte_identical(ledger: Ledger) -> None:
    a = ledger.decide("Pin CI to ubuntu-22.04", "24.04 broke a transitive dep", scope="org")
    ledger.supersede(a, "Pin CI to ubuntu-24.04", "upstream fixed it, and 22.04 is EOL soon")

    first = cortex.render_scope(ledger, "org")
    second = cortex.render_scope(ledger, "org")
    assert first == second


def test_empty_scope_renders_without_erroring(ledger: Ledger) -> None:
    page = cortex.render_scope(ledger, "org")
    assert "_none active_" in page
    assert "_none retired_" in page


def test_scope_slug() -> None:
    assert cortex.scope_slug("org") == "org"
    assert cortex.scope_slug("repo:lopi") == "repo-lopi"
