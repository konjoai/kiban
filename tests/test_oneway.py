"""Tests for the one-way-door classifier (lib/oneway.py)."""

from __future__ import annotations

from lib import oneway


def test_public_api_removal_is_one_way() -> None:
    diff = "-def public_fn(x):\n+def public_fn(x, y):\n"
    c = oneway.classify(["pkg/api.py"], diff)
    assert c.is_one_way
    assert "diff:public-api-removal" in c.reasons


def test_data_delete_is_one_way() -> None:
    c = oneway.classify(["db/m.sql"], "+DELETE FROM users WHERE 1=1;\n")
    assert c.is_one_way
    assert any("data-delete" in r for r in c.reasons)


def test_release_version_bump_is_one_way() -> None:
    c = oneway.classify(["VERSION"], "-0.3.0\n+0.4.0\n")
    assert c.is_one_way
    assert "path:release-version" in c.reasons


def test_comment_change_is_two_way() -> None:
    c = oneway.classify(["notes.py"], "+# fix a typo in the comment\n")
    assert not c.is_one_way
    assert c.door == "two-way"


def test_ambiguous_on_sensitive_path_is_one_way() -> None:
    # No destructive pattern, but the change touches a migrations/ path: err toward asking.
    c = oneway.classify(["app/migrations/0007_tweak.py"], "+    pass  # adjust\n")
    assert c.is_one_way
    assert "ambiguous-on-sensitive-path" in c.reasons or any(
        "schema-or-migration" in r for r in c.reasons
    )


def test_fingerprint_is_stable_and_order_independent() -> None:
    a = oneway.fingerprint(["b.py", "a.py"])
    b = oneway.fingerprint(["a.py", "b.py"])
    assert a == b
    assert a != oneway.fingerprint(["a.py", "c.py"])


def test_find_ack_matches_trailer() -> None:
    fp = oneway.fingerprint(["VERSION"])
    msgs = f"Some commit\n\n{oneway.ack_trailer(fp)}\nCo-authored-by: x\n"
    assert oneway.find_ack(msgs, fp)
    assert not oneway.find_ack("no trailer here", fp)
