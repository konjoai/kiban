"""Tests for the three-tier secret scanner."""

from __future__ import annotations

from lib import redact
from lib.redact import Tier


def _tiers(text: str) -> set[Tier]:
    return {f.tier for f in redact.scan(text)}


def test_private_key_is_high_and_blocks() -> None:
    key = (
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "b3BlbnNzaC1rZXktdjEAAAAA1234567890\n"
        "-----END OPENSSH PRIVATE KEY-----"
    )
    assert Tier.HIGH in _tiers(key)
    assert redact.has_high(key)
    assert redact.HIGH_PLACEHOLDER in redact.redact(key)


def test_jwt_is_medium_not_high() -> None:
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcDEF123456"
    tiers = _tiers(jwt)
    assert Tier.MEDIUM in tiers
    assert Tier.HIGH not in tiers
    assert not redact.has_high(jwt)


def test_no_medium_to_high_promotion() -> None:
    # A JWT alongside other credential-shaped strings stays MEDIUM; nothing promotes it.
    text = (
        "token: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhYmMifQ.signature012345 "
        "key=AIzaSyA1234567890abcdefghijklmnopqrstuv0"
    )
    assert not redact.has_high(text)
    assert Tier.MEDIUM in _tiers(text)


def test_redact_leaves_medium_intact() -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhYmMifQ.signature012345"
    assert redact.redact(jwt) == jwt


def test_aws_access_key_id_is_high() -> None:
    assert redact.has_high("AKIAIOSFODNN7EXAMPLE")
