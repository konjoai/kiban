"""Tests for the interactive confirm flow (lib/confirm.py).

I/O is injected, so the typed-confirmation behavior is exercised without a terminal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledger.engine import Ledger
from lib import confirm, oneway, redact


def _scripted(replies: list[str]):
    it = iter(replies)
    return lambda _prompt="": next(it)


def test_one_way_confirm_succeeds_and_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KONJO_STATE_DIR", str(tmp_path))
    ledger = Ledger("ledger/decisions.jsonl")
    cls = oneway.classify(["VERSION"], "-0.3.0\n+0.4.0\n")
    ack = confirm.confirm_one_way(
        cls, ["VERSION"],
        input_fn=_scripted(["CONFIRM", "cutting the 0.4.0 release"]),
        output_fn=lambda _m: None,
        author="wes",
        ledger=ledger,
    )
    assert ack.fingerprint == oneway.fingerprint(["VERSION"])
    assert ack.trailer == oneway.ack_trailer(ack.fingerprint)
    assert ack.ledger_id is not None
    # The acknowledgement is in the Ledger.
    found = ledger.search("ONEWAY-ACK")
    assert any(ack.fingerprint in d.decision for d in found)


def test_vague_reply_is_refused() -> None:
    cls = oneway.classify(["VERSION"], "+0.4.0\n")
    with pytest.raises(confirm.ConfirmAborted):
        confirm.confirm_one_way(
            cls, ["VERSION"],
            input_fn=_scripted(["yes"]),  # not the exact token
            output_fn=lambda _m: None,
        )


def test_empty_token_is_refused() -> None:
    cls = oneway.classify(["VERSION"], "+0.4.0\n")
    with pytest.raises(confirm.ConfirmAborted):
        confirm.confirm_one_way(
            cls, ["VERSION"],
            input_fn=_scripted([""]),
            output_fn=lambda _m: None,
        )


def test_empty_justification_is_refused() -> None:
    cls = oneway.classify(["VERSION"], "+0.4.0\n")
    with pytest.raises(confirm.ConfirmAborted):
        confirm.confirm_one_way(
            cls, ["VERSION"],
            input_fn=_scripted(["CONFIRM", "   "]),  # token ok, justification blank
            output_fn=lambda _m: None,
        )


def test_medium_secret_confirm_token_required() -> None:
    findings = [redact.Finding(redact.Tier.MEDIUM, "jwt", (0, 10))]
    # Vague reply aborts.
    with pytest.raises(confirm.ConfirmAborted):
        confirm.confirm_medium_secret(
            findings, input_fn=_scripted(["sure"]), output_fn=lambda _m: None
        )
    # Exact token affirms.
    assert confirm.confirm_medium_secret(
        findings, input_fn=_scripted(["CONFIRM"]), output_fn=lambda _m: None
    )
