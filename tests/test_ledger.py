"""End-to-end tests for the Konjo Ledger engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from ledger.engine import Ledger
from lib import jsonl_store


@pytest.fixture()
def ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Ledger:
    monkeypatch.setenv("KONJO_STATE_DIR", str(tmp_path))
    return Ledger("ledger/decisions.jsonl")


def test_decide_then_search_returns_active(ledger: Ledger) -> None:
    did = ledger.decide("Use gstack-style distribution", "No marketplace cache layer",
                        scope="org", confidence=8, author="wes")
    results = ledger.search("gstack")
    assert len(results) == 1
    assert results[0].id == did
    assert results[0].active is True


def test_supersede_shows_new_active_with_chain(ledger: Ledger) -> None:
    first = ledger.decide("State lives in the clone", "simpler", scope="org")
    second = ledger.supersede(first, "State lives in ~/.konjo/state",
                              "updates must never touch state")
    actives = ledger.active(scope="org")
    assert [d.id for d in actives] == [second]
    old = ledger.get(first)
    new = ledger.get(second)
    assert old is not None and not old.active
    assert old.superseded_by == second
    assert new is not None and new.chain == [first]


def test_redact_makes_inactive(ledger: Ledger) -> None:
    did = ledger.decide("temporary call", "will retire", scope="org")
    ledger.redact_decision(did, "obsolete")
    d = ledger.get(did)
    assert d is not None and d.redacted and not d.active
    assert ledger.active(scope="org") == []


def test_high_secret_in_decision_blocks_write(ledger: Ledger) -> None:
    secret = (
        "-----BEGIN PRIVATE KEY-----\nMIIBVAIBADANBgkqhkiG9w0BAQEFAASC\n"
        "-----END PRIVATE KEY-----"
    )
    with pytest.raises(jsonl_store.SecretRejected):
        ledger.decide("leak", secret, scope="org")
    assert ledger.search("leak") == []


def test_confidence_range_validated(ledger: Ledger) -> None:
    with pytest.raises(ValueError):
        ledger.decide("x", "y", confidence=11)
