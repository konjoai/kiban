"""lib/threat.py: trust-boundary classification and the brief-time record."""

from __future__ import annotations

import pytest

from lib import threat


class _FakeLedger:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def decide(self, title, justification, **kwargs):  # noqa: ANN001, ANN003
        self.calls.append({"title": title, "justification": justification, **kwargs})
        return "ledger-id-1"


def test_classify_hints_subprocess_from_path_and_diff() -> None:
    cls = threat.classify(
        ["src/exec_runner.py"], "subprocess.run(user_supplied_cmd, shell=True)"
    )
    assert threat.SUBPROCESS_EXEC in cls.boundaries


def test_classify_no_hits_on_plain_change() -> None:
    cls = threat.classify(["README.md"], "fix a typo")
    assert cls.boundaries == []


def test_record_refuses_empty_mitigation() -> None:
    records = [
        threat.BoundaryRecord(boundary=threat.NETWORK_INGRESS, mitigation="", abuse_case="x")
    ]
    with pytest.raises(threat.MissingContent):
        threat.record_threat_model(["src/webhook.rs"], records)


def test_record_refuses_empty_abuse_case() -> None:
    records = [
        threat.BoundaryRecord(
            boundary=threat.NETWORK_INGRESS, mitigation="HMAC check", abuse_case=""
        )
    ]
    with pytest.raises(threat.MissingContent):
        threat.record_threat_model(["src/webhook.rs"], records)


def test_record_refuses_unknown_boundary() -> None:
    records = [
        threat.BoundaryRecord(boundary="not_a_real_boundary", mitigation="x", abuse_case="y")
    ]
    with pytest.raises(threat.MissingContent):
        threat.record_threat_model(["src/webhook.rs"], records)


def test_record_succeeds_with_real_content_and_logs_ledger() -> None:
    ledger = _FakeLedger()
    records = [
        threat.BoundaryRecord(
            boundary=threat.NETWORK_INGRESS,
            mitigation="HMAC-SHA256 signature check before dispatch",
            abuse_case="forged webhook body with no signature triggers task injection",
        )
    ]
    trailer = threat.record_threat_model(["src/webhook.rs"], records, author="a", ledger=ledger)
    assert trailer.startswith("Konjo-Threat-Model: ")
    assert len(ledger.calls) == 1


def test_record_with_no_boundaries_is_a_valid_explicit_answer() -> None:
    ledger = _FakeLedger()
    trailer = threat.record_threat_model(["README.md"], [], author="a", ledger=ledger)
    assert trailer.startswith("Konjo-Threat-Model: ")
    assert ledger.calls[0]["justification"] == "no boundaries hit"


def test_trailer_round_trip() -> None:
    fp = "abc123def456"
    trailer = threat.threat_trailer(fp)
    messages = f"some commit message\n\n{trailer}\n"
    assert threat.find_threat_model(messages, fp)
    assert not threat.find_threat_model(messages, "different")
