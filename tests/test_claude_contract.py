"""KT-13.P1 fixture pair: gate_claude_contract, offline, no model, no network."""

from __future__ import annotations

from lib import claude_contract

COMPLIANT = """\
## Org rules

@~/.konjo/kiban/plugins/konjo/skills/konjo/SKILL.md

## Stack

Rust 2021 - tokio

## Commands

cargo test --workspace

## Invariants

- No unwrap()/expect() outside tests (enforced: repo:clippy -D clippy::unwrap_used)
- No blocking I/O on async paths (ADVISORY -- no mechanical check yet)

## Repo map

| Crate | Role |
|-------|------|
| core | shared types |

## Repo-specific rules

Nothing else.
"""

_REPO_MAP_BLOCK = "## Repo map\n\n| Crate | Role |\n|-------|------|\n| core | shared types |\n\n"
MISSING_SECTION = COMPLIANT.replace(_REPO_MAP_BLOCK, "")

OUT_OF_ORDER = COMPLIANT.replace(
    "## Stack\n\nRust 2021 - tokio\n\n## Commands",
    "## Commands\n\ncargo test --workspace\n\n## Stack",
).replace(
    "Rust 2021 - tokio\n\ncargo test --workspace",
    "cargo test --workspace\n\nRust 2021 - tokio",
)

MISSING_IMPORT = COMPLIANT.replace(
    "@~/.konjo/kiban/plugins/konjo/skills/konjo/SKILL.md\n\n", ""
)

UNENFORCED_INVARIANT = COMPLIANT.replace(
    "- No blocking I/O on async paths (ADVISORY -- no mechanical check yet)",
    "- No blocking I/O on async paths",
)


def test_compliant_passes() -> None:
    check = claude_contract.check_contract(COMPLIANT)
    assert check.ok, check


def test_missing_section_fails() -> None:
    check = claude_contract.check_contract(MISSING_SECTION)
    assert not check.ok
    assert "repo map" in check.missing_sections


def test_out_of_order_fails() -> None:
    check = claude_contract.check_contract(OUT_OF_ORDER)
    assert not check.ok
    assert check.out_of_order


def test_missing_org_import_fails() -> None:
    check = claude_contract.check_contract(MISSING_IMPORT)
    assert not check.ok
    assert not check.has_org_import


def test_unenforced_invariant_bullet_fails() -> None:
    check = claude_contract.check_contract(UNENFORCED_INVARIANT)
    assert not check.ok
    assert any("blocking I/O" in b for b in check.unenforced_bullets)


def test_advisory_bullet_is_not_unenforced() -> None:
    check = claude_contract.check_contract(COMPLIANT)
    assert not check.unenforced_bullets


# citation_ratio: the incident-log lint.

INCIDENT_LOG = """\
# Security Rules

- Rate-limit all endpoints by default
- HMAC-verify webhook signatures (Sprint S10, Phase 4)
- Repo-supplied commands are untrusted by default (Sprint S10, Phase 0)
- Subprocess env is allowlisted (Sprint S10, Phase 1)
- MCP servers are allowlisted (Sprint S10, Phase 5)
"""

MOSTLY_INVARIANTS = """\
# Security Rules

- Validate all inputs at the API boundary
- Prompt injection: system prompt content must never be request-controllable
- Never log raw user content at INFO or above
- Rate-limit all endpoints by default
- Set and enforce per-request timeouts on every agent run
- HMAC-verify webhook signatures (v0.3.0)
- WhatsApp webhook: validate the Twilio HMAC-SHA1 signature (Sprint S10, Phase 4)
- Never store API keys or tokens in the codebase
- Repo-supplied commands are untrusted by default (Sprint S10, Phase 0)
- Subprocess env is allowlisted (Sprint S10, Phase 1)
- MCP servers are allowlisted (Sprint S10, Phase 5)
"""


def test_citation_ratio_majority_cited() -> None:
    # 4 of 5 substantive lines carry a Sprint citation.
    assert claude_contract.citation_ratio(INCIDENT_LOG) > 0.5


def test_citation_ratio_minority_cited() -> None:
    # 4 of 11 substantive lines carry a citation -- this is lopi's real
    # .claude/rules/security.md shape as of Phase 13: not (yet) a majority, an honest
    # correction of the sprint brief's "every line" baseline claim.
    ratio = claude_contract.citation_ratio(MOSTLY_INVARIANTS)
    assert ratio < 0.5
    assert 0.3 < ratio < 0.5
