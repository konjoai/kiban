"""Interactive confirm flow for irreversible actions and MEDIUM-secret findings.

Evidence-first and deliberately hard to fool. The flow states plainly what is
irreversible and why, then requires the user to type an exact confirmation token (not a
bare y/N, not a vague "yes"). A mismatched or empty reply aborts. A one-way confirm also
requires a non-empty justification, logs an acknowledgement to the Ledger for provenance,
and returns the commit trailer CI will check.

I/O is injected (input_fn / output_fn) so the flow is testable without a real terminal.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from lib import oneway, redact

CONFIRM_TOKEN = "CONFIRM"

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


class ConfirmAborted(Exception):
    """The user did not give an exact confirmation; the action must not proceed."""


@dataclass
class Acknowledgement:
    fingerprint: str
    trailer: str
    justification: str
    reasons: list[str]
    ledger_id: str | None = None


def _require_token(input_fn: InputFn, output_fn: OutputFn, token: str) -> None:
    output_fn(f"Type exactly {token!r} to confirm (anything else aborts):")
    reply = input_fn("> ").strip()
    if reply != token:
        raise ConfirmAborted(f"expected {token!r}, got {reply!r}; aborting, nothing done")


def confirm_one_way(
    classification: oneway.Classification,
    changed_files: list[str],
    *,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    author: str = "unknown",
    ledger: object | None = None,
    token: str = CONFIRM_TOKEN,
) -> Acknowledgement:
    """Confirm an irreversible change. Refuses a vague reply; logs the acknowledgement.

    Raises ConfirmAborted on any reply that is not the exact token, or on an empty
    justification. On success, writes a Ledger ack (provenance) and returns the commit
    trailer CI checks for.
    """
    fp = oneway.fingerprint(changed_files)
    output_fn("ONE-WAY DOOR. This change is hard or costly to reverse.")
    output_fn(f"  reasons: {', '.join(classification.reasons) or 'sensitive surface'}")
    output_fn(f"  files:   {', '.join(changed_files)}")
    output_fn(f"  change id: {fp}")
    output_fn("Reverting may not be possible. Proceed only if you accept that.")

    _require_token(input_fn, output_fn, token)

    output_fn("State in one line why this is intended (required):")
    justification = input_fn("why> ").strip()
    if not justification:
        raise ConfirmAborted("a justification is required; aborting, nothing done")

    ledger_id: str | None = None
    if ledger is not None:
        ledger_id = ledger.decide(  # type: ignore[attr-defined]
            f"ONEWAY-ACK {fp}",
            justification,
            scope="org",
            alternatives_considered=classification.reasons,
            confidence=classification.confidence,
            author=author,
        )

    trailer = oneway.ack_trailer(fp)
    output_fn("Acknowledged. Add this trailer to the commit so CI can see it:")
    output_fn(f"  {trailer}")
    return Acknowledgement(
        fingerprint=fp,
        trailer=trailer,
        justification=justification,
        reasons=classification.reasons,
        ledger_id=ledger_id,
    )


def confirm_medium_secret(
    findings: list[redact.Finding],
    *,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
    token: str = CONFIRM_TOKEN,
) -> bool:
    """Confirm that MEDIUM-tier findings are non-secrets or intended.

    HIGH is never routed here; it blocks outright at the store and the CI secrets gate.
    Returns True only on the exact token. Any other reply aborts (returns False is not
    used; abort raises so a caller cannot mistake silence for assent).
    """
    names = ", ".join(sorted({f.pattern_name for f in findings}))
    output_fn(f"MEDIUM finding(s) on added lines: {names}")
    output_fn("These are credential-shaped but often non-secret (JWTs, publishable keys).")
    output_fn("Confirm only if you are certain these are not live secrets.")
    _require_token(input_fn, output_fn, token)
    return True
