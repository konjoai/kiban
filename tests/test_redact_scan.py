"""Tests for the redact path/diff scan wrappers (C-D)."""

from __future__ import annotations

from pathlib import Path

from lib import redact

PRIVATE_KEY = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIIBVgIBADANBgkqhkiG9w0BAQEFAASCAUAwggE8AgEAAkEA\n"
    "-----END PRIVATE KEY-----"
)


def test_scan_paths_flags_high(tmp_path: Path) -> None:
    good = tmp_path / "ok.txt"
    good.write_text("nothing secret here\n")
    bad = tmp_path / "leak.txt"
    bad.write_text(f"key = {PRIVATE_KEY}\n")
    found = redact.scan_paths([str(good), str(bad)])
    assert str(good) not in found
    assert str(bad) in found
    assert any(f.tier is redact.Tier.HIGH for f in found[str(bad)])


def test_scan_paths_skips_unreadable(tmp_path: Path) -> None:
    missing = str(tmp_path / "nope.txt")
    assert redact.scan_paths([missing]) == {}


def test_scan_diff_only_added_lines() -> None:
    # A secret on a removed/context line is not the change; only '+' lines are scanned.
    diff = (
        "diff --git a/c.txt b/c.txt\n"
        "--- a/c.txt\n"
        "+++ b/c.txt\n"
        "@@ -1,2 +1,2 @@\n"
        f"-old = {PRIVATE_KEY}\n"
        " context line\n"
        "+a harmless new line\n"
    )
    assert not any(f.tier is redact.Tier.HIGH for f in redact.scan_diff(diff))


def test_scan_diff_flags_added_secret() -> None:
    # A real diff prefixes every added line with '+'.
    added = "\n".join("+" + ln for ln in f"key = {PRIVATE_KEY}".splitlines())
    diff = "diff --git a/c.txt b/c.txt\n+++ b/c.txt\n" + added + "\n"
    assert any(f.tier is redact.Tier.HIGH for f in redact.scan_diff(diff))
