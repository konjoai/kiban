"""The TypeScript language pack.

Two TS-specific lanes plus a tool fragment. The shared `api-surface` and `red-team` lanes
from `_base` cover `SCOPE_TS` (their scope tuples include it), so they are reused, not
redefined. Each lane is held to the same JSON finding contract as every other lane via
`_prompt`, so a TS finding parses and dedups exactly like any other.
"""

from __future__ import annotations

from lib.packs.lang._base import Specialist, _prompt

TYPE_SOUNDNESS = Specialist(
    name="type-soundness",
    category="type-soundness",
    scopes=("SCOPE_TS",),
    system_prompt=_prompt(
        "You are a type-soundness reviewer for TypeScript.",
        "Hunt for casts and escapes that defeat the type system: an `any` or an `as` cast "
        "that launders a value through a public contract, a non-null assertion `!` on a "
        "value that can be null or undefined, and an untyped boundary (a `JSON.parse`, a "
        "network response, a `process.env` read) consumed with no schema or validation. A "
        "cast that hides a real type mismatch a caller would hit is HIGH.",
        "type-soundness",
    ),
)

ASYNC_CORRECTNESS = Specialist(
    name="async-correctness",
    category="async-correctness",
    scopes=("SCOPE_TS",),
    system_prompt=_prompt(
        "You are an async-correctness reviewer for TypeScript.",
        "Hunt for a floating promise (a promise not awaited or handled), `await` inside a "
        "loop where `Promise.all` was meant, an unhandled rejection path, and a race on "
        "shared module state. A floating promise on a path that must complete before the "
        "next step is HIGH.",
        "async-correctness",
    ),
)

SPECIALISTS: tuple[Specialist, ...] = (TYPE_SOUNDNESS, ASYNC_CORRECTNESS)

# The TS tool surface wired into konjo_gates_py.cli. Each runs through konjo-newonly like the
# Python and Rust tools. npm-audit is the JS realization of the supply_chain universal gate.
TOOLS: tuple[str, ...] = (
    "tsc",
    "eslint",
    "stryker",
    "npm-audit",
)
