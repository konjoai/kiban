"""End-to-end tests for the Konjo Ledger engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from ledger.engine import Ledger
from lib import jsonl_store


@pytest.fixture()
def ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Ledger:
    monkeypatch.setenv("KONJO_STATE_DIR", str(tmp_path))
    return Ledger("ledger/events")


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


def test_decided_at_defaults_to_the_append_time(ledger: Ledger) -> None:
    """Unseeded writes carry decided_at == date, so the field is always populated."""
    did = ledger.decide("Local embeddings only", "no third-party inference", scope="org")
    d = ledger.get(did)
    assert d is not None
    assert d.decided_at == d.date


def test_decided_at_records_a_past_call_without_moving_the_append_time(
    ledger: Ledger,
) -> None:
    """A seeded past decision: decided long ago, recorded now. Both stay readable.

    `date` keeps its append-time meaning (the staleness gate clocks off it), so a
    backdated seed must not drag it backwards.
    """
    did = ledger.decide(
        "Subscription over metered API",
        "fixed monthly cost beats per-token billing at this volume",
        scope="org",
        alternatives_considered=["metered API billing"],
        decided_at="2026-05-14T09:00:00Z",
    )
    d = ledger.get(did)
    assert d is not None
    assert d.decided_at == "2026-05-14T09:00:00Z"
    assert d.date != d.decided_at
    assert d.date > d.decided_at


def test_supersede_accepts_decided_at(ledger: Ledger) -> None:
    first = ledger.decide("a", "r", scope="org", decided_at="2026-04-01T09:00:00Z")
    second = ledger.supersede(first, "b", "r2", decided_at="2026-06-01T09:00:00Z")
    d = ledger.get(second)
    assert d is not None
    assert d.decided_at == "2026-06-01T09:00:00Z"


@pytest.mark.parametrize(
    "bad",
    ["2026-05-14", "14/05/2026", "2026-05-14T09:00:00", "2026-05-14T09:00:00+00:00", ""],
)
def test_decided_at_rejects_non_strict_utc_stamps(ledger: Ledger, bad: str) -> None:
    if bad == "":
        # Empty falls through to the default rather than raising.
        did = ledger.decide("x", "y", scope="org", decided_at=bad)
        assert ledger.get(did).decided_at != ""  # type: ignore[union-attr]
        return
    with pytest.raises(ValueError, match="decided_at"):
        ledger.decide("x", "y", scope="org", decided_at=bad)


def test_decided_at_rejects_a_future_stamp(ledger: Ledger) -> None:
    """Nothing can be decided after it was written down."""
    with pytest.raises(ValueError, match="future"):
        ledger.decide("x", "y", scope="org", decided_at="2099-01-01T00:00:00Z")


def test_legacy_events_without_decided_at_fall_back_to_date(
    ledger: Ledger, tmp_path: Path
) -> None:
    """The two ONEWAY-ACK events already on the real machine predate this field."""
    event = (
        '{"event":"decide","id":"f921e490f4d1","scope":"org","decision":"ONEWAY-ACK",'
        '"rationale":"r","alternatives_considered":[],"confidence":6,'
        '"date":"2026-07-29T16:48:16Z","author":"unknown"}'
    )
    events_dir = tmp_path / "ledger" / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    (events_dir / "f921e490f4d1.json").write_text(event, encoding="utf-8")
    d = ledger.get("f921e490f4d1")
    assert d is not None
    assert d.decided_at == "2026-07-29T16:48:16Z"
