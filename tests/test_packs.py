"""Tests for the pack seam (lib/packs/lang).

These pin the load-bearing invariants of the Phase 7 refactor: an empty pack list yields
exactly the `_base` lanes; a [python, mlx] registry is the five Squish-era lanes; and the
moved prompt text is byte-identical to the pre-refactor lanes (the cassette key depends on
it, so a drift here is the same failure a stale Squish cassette would catch).
"""

from __future__ import annotations

import hashlib

from lib import review
from lib.packs.lang import _base

# The exact prompt strings the cassettes were recorded against. These are the SHA-256
# prefixes of each lane's system_prompt; a change to any prompt changes the cassette key
# and would stale the Squish cassettes. Frozen here as a second tripwire.
_FROZEN_PROMPT_SHA = {
    "numerics": "35e4",
    "memory-bandwidth": "e211",
    "concurrency": "721b",
    "api-surface": "c0a4",
    "red-team": "fb97",
}


def test_empty_pack_list_is_base_lanes_only() -> None:
    reg = _base.load_registry([])
    assert set(reg) == {"concurrency", "api-surface", "red-team"}


def test_base_named_explicitly_adds_nothing() -> None:
    assert set(_base.load_registry(["lang/_base"])) == set(_base.load_registry([]))


def test_python_mlx_registry_is_the_five_squish_lanes() -> None:
    reg = _base.load_registry(["lang/python", "lang/mlx"])
    assert set(reg) == {
        "numerics",
        "memory-bandwidth",
        "concurrency",
        "api-surface",
        "red-team",
    }


def test_packs_for_derives_from_stack_when_absent() -> None:
    # squish.yml has no `packs` field; it derives from stack: [python, mlx].
    assert review.packs_for({"stack": ["python", "mlx"]}) == ["lang/python", "lang/mlx"]
    # an explicit `packs` wins over stack.
    assert review.packs_for({"stack": ["python"], "packs": ["lang/rust"]}) == ["lang/rust"]
    # an unmapped stack entry contributes no pack (the _base lanes are still present).
    assert review.packs_for({"stack": ["cobol"]}) == []


def test_moved_prompts_are_byte_stable() -> None:
    # The numerics and memory-bandwidth prompts must hash to their frozen prefix, the same
    # text the Squish cassettes were recorded against.
    reg = _base.load_registry(["lang/mlx"])
    for name, want in _FROZEN_PROMPT_SHA.items():
        got = hashlib.sha256(reg[name].system_prompt.encode("utf-8")).hexdigest()[:4]
        assert got == want, f"prompt drift in {name}: {got} != {want}"


def test_base_lanes_carry_their_expected_scopes() -> None:
    reg = _base.load_registry([])
    assert "SCOPE_RUST" in reg["concurrency"].scopes
    assert "SCOPE_RUST" in reg["api-surface"].scopes
    assert reg["red-team"].is_redteam
