"""Three-tier secret scanner shared by the jsonl store and the state-sync push.

Tiers:
  HIGH    genuinely-secret credentials (private keys, AWS secret keys, secret-entropy
          bearer/slack tokens). These block a write outright.
  MEDIUM  credential-shaped but high false-positive (publishable keys, Google AIza
          keys, JWTs, env-style key=value, basic PII). Flagged for a human confirm,
          never auto-blocked.
  LOW     surfaced only, never acted on.

Design rule: no wholesale MEDIUM -> HIGH promotion. A MEDIUM pattern stays MEDIUM even
if it co-occurs with other signals. Promotion would re-introduce the false-positive
blocking we are trying to avoid.

Public surface:
  scan(text)   -> list[Finding]   every match, any tier
  redact(text) -> str             HIGH spans replaced with a placeholder
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from re import Pattern


class Tier(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True)
class Finding:
    tier: Tier
    pattern_name: str
    span: tuple[int, int]


HIGH_PLACEHOLDER = "[REDACTED-HIGH]"

# Each rule: (pattern_name, compiled regex). Order is scan order, not priority.
_HIGH_RULES: list[tuple[str, Pattern[str]]] = [
    (
        "private_key_block",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"
            r".*?-----END (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    # AWS secret access key: 40 chars of base64-ish entropy. Keyed on context so we
    # do not flag every 40-char string.
    (
        "aws_secret_access_key",
        re.compile(
            r"(?i)aws.{0,20}?(?:secret|private).{0,20}?['\"]?([A-Za-z0-9/+=]{40})['\"]?"
        ),
    ),
    ("aws_access_key_id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    # GitHub fine-grained / classic personal access tokens carry real secret entropy.
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    # Slack bot/user tokens.
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    # Generic "Bearer <secret>" where the secret has real entropy (mixed case + digits,
    # 24+ chars). JWTs are caught separately at MEDIUM and excluded here.
    (
        "bearer_secret",
        re.compile(r"(?i)bearer\s+(?!ey[A-Za-z0-9_-]+\.)[A-Za-z0-9_\-]{24,}"),
    ),
]

_MEDIUM_RULES: list[tuple[str, Pattern[str]]] = [
    # JSON Web Token. Credential-shaped but frequently a non-secret id token in logs.
    (
        "jwt",
        re.compile(r"\bey[A-Za-z0-9_-]{8,}\.ey[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    ),
    # Google API key. Often a publishable client key.
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    # Stripe publishable key.
    ("stripe_publishable", re.compile(r"\bpk_(?:live|test)_[0-9A-Za-z]{10,}\b")),
    # env-style assignment of a secret-named var.
    (
        "env_secret_assignment",
        re.compile(
            r"(?im)^\s*[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|APIKEY|API_KEY)"
            r"[A-Z0-9_]*\s*=\s*\S+"
        ),
    ),
    # Email address (PII).
    ("email_pii", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
]

_LOW_RULES: list[tuple[str, Pattern[str]]] = [
    # A bare hex blob that could be a hash or could be nothing.
    ("hex_blob_32plus", re.compile(r"\b[0-9a-fA-F]{32,}\b")),
]


def scan(text: str) -> list[Finding]:
    """Return every finding across all three tiers, in tier then position order."""
    findings: list[Finding] = []
    for tier, rules in (
        (Tier.HIGH, _HIGH_RULES),
        (Tier.MEDIUM, _MEDIUM_RULES),
        (Tier.LOW, _LOW_RULES),
    ):
        for name, pattern in rules:
            for match in pattern.finditer(text):
                findings.append(Finding(tier=tier, pattern_name=name, span=match.span()))
    findings.sort(key=lambda f: (list(Tier).index(f.tier), f.span[0]))
    return findings


def has_high(text: str) -> bool:
    """True if any HIGH-tier secret is present. Cheap gate for the store."""
    return any(f.tier is Tier.HIGH for f in scan(text))


def redact(text: str) -> str:
    """Replace every HIGH span with a placeholder. MEDIUM and LOW are left intact."""
    high_spans = sorted(
        (f.span for f in scan(text) if f.tier is Tier.HIGH),
        key=lambda s: s[0],
        reverse=True,
    )
    out = text
    for start, end in high_spans:
        out = out[:start] + HIGH_PLACEHOLDER + out[end:]
    return out
