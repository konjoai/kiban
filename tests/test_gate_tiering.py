"""Adoption-Ramp-1: tier resolution, alias compatibility, default-to-advisory.

resolve_tier's precedence (see its own docstring in
packages/konjo-gates-py/src/konjo_gates_py/cli.py): an explicit `tier:` on the gate's
own profile sub-block, then a matching `gates:` entry's `tier:`, then the legacy
`advisory: bool` alias, then the default ("advisory").
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PKG_SRC = _ROOT / "packages" / "konjo-gates-py" / "src"
for _p in (str(_ROOT), str(_PKG_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from konjo_gates_py.cli import FAIL, WARN, _tier_verdict, resolve_tier  # noqa: E402


def test_default_is_advisory_with_no_config() -> None:
    assert resolve_tier(None, {}, "polarity") == "advisory"
    assert resolve_tier({}, {}, "polarity") == "advisory"


def test_explicit_tier_on_own_subblock_wins() -> None:
    cfg = {"tier": "blocking"}
    assert resolve_tier(cfg, {"gates": []}, "polarity") == "blocking"


def test_explicit_tier_advisory_on_own_subblock() -> None:
    cfg = {"tier": "advisory"}
    assert resolve_tier(cfg, {}, "claude_contract") == "advisory"


def test_legacy_advisory_true_alias_maps_to_advisory() -> None:
    cfg = {"advisory": True}
    assert resolve_tier(cfg, {}, "polarity") == "advisory"


def test_legacy_advisory_false_alias_maps_to_blocking() -> None:
    cfg = {"advisory": False}
    assert resolve_tier(cfg, {}, "claude_contract") == "blocking"


def test_tier_takes_precedence_over_legacy_advisory_alias() -> None:
    # A profile mid-migration might carry both -- tier: wins, so a profile author who
    # sets tier: explicitly is never silently overridden by a stale advisory: bool.
    cfg = {"tier": "blocking", "advisory": True}
    assert resolve_tier(cfg, {}, "polarity") == "blocking"


def test_gates_list_entry_tier_used_when_no_dedicated_subblock() -> None:
    # A repo-native ratchet check named only in `gates:` (no dedicated `polarity`-style
    # sub-block) can still declare a tier there.
    profile = {"gates": [{"name": "scope-assert", "tier": "blocking", "rejects_test": "true"}]}
    assert resolve_tier(None, profile, "scope-assert") == "blocking"


def test_gates_list_entry_with_no_tier_falls_through_to_default() -> None:
    profile = {"gates": [{"name": "scope-assert", "rejects_test": "true"}]}
    assert resolve_tier(None, profile, "scope-assert") == "advisory"


def test_unknown_gate_name_falls_through_to_default() -> None:
    profile = {"gates": [{"name": "some-other-gate", "tier": "blocking"}]}
    assert resolve_tier(None, profile, "scope-assert") == "advisory"


def test_invalid_tier_value_falls_through() -> None:
    # A typo'd tier value must not silently resolve to blocking (fail-closed the other
    # way: an invalid value is treated as absent, not as a promotion).
    cfg = {"tier": "sometimes"}
    assert resolve_tier(cfg, {}, "polarity") == "advisory"


def test_tier_value_is_case_and_whitespace_insensitive() -> None:
    cfg = {"tier": "  BLOCKING  "}
    assert resolve_tier(cfg, {}, "polarity") == "blocking"


def test_tier_verdict_maps_blocking_to_fail_and_advisory_to_warn() -> None:
    assert _tier_verdict("blocking") == FAIL
    assert _tier_verdict("advisory") == WARN
    # Anything else defaults to the safe (non-blocking) side.
    assert _tier_verdict("unknown") == WARN
