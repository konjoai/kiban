"""The Rust language pack.

Three Rust-specific lanes plus a tool fragment. The shared `concurrency`, `api-surface`,
and `red-team` lanes from `_base` already cover `SCOPE_RUST`, so they are reused, not
redefined here. Each lane is held to the same JSON finding contract as every other lane
via `_prompt`, so a Rust finding parses and dedups exactly like a Squish finding.
"""

from __future__ import annotations

from lib.packs.lang._base import Specialist, _prompt

OWNERSHIP_LIFETIMES = Specialist(
    name="ownership-lifetimes",
    category="ownership-lifetimes",
    scopes=("SCOPE_RUST",),
    system_prompt=_prompt(
        "You are an ownership, lifetime, and unsafe-code reviewer for Rust.",
        "Hunt for unsound `unsafe`, aliasing violations the borrow checker cannot see "
        "inside an `unsafe` block, `transmute` misuse, and `Send`/`Sync` claims that are "
        "not justified by the type's invariants. An `unsafe` block with no safety comment "
        "explaining why it is sound is a finding. An `unsafe` block that is actually "
        "unsound (a real aliasing, lifetime, or invariant violation) is CRITICAL.",
        "ownership-lifetimes",
    ),
)

ERROR_HANDLING = Specialist(
    name="error-handling",
    category="error-handling",
    scopes=("SCOPE_RUST",),
    system_prompt=_prompt(
        "You are an error-handling reviewer for Rust.",
        "Hunt for `.unwrap()` or `.expect()` on a fallible path that can fire in "
        "production, errors swallowed with `let _ =` or an ignored `Result`, `panic!` on "
        "a library path, and a `?` that drops error context a caller would need. A new "
        "`unwrap` or `expect` on a non-test, non-`main` path is HIGH.",
        "error-handling",
    ),
)

PERF_ALLOC = Specialist(
    name="perf-alloc",
    category="perf-alloc",
    scopes=("SCOPE_RUST",),
    system_prompt=_prompt(
        "You are an allocation and performance reviewer for Rust.",
        "Hunt for a needless `.clone()` on a hot path, a `Vec` that reallocates inside a "
        "loop because it was not built with capacity, a `collect` into a temporary only to "
        "iterate it again, and `String` building without `with_capacity`. Scope your "
        "findings to changes that plausibly sit on a hot path; a one-time setup clone is "
        "not a finding.",
        "perf-alloc",
    ),
)

SPECIALISTS: tuple[Specialist, ...] = (OWNERSHIP_LIFETIMES, ERROR_HANDLING, PERF_ALLOC)

# The Rust tool surface wired into konjo_gates_py.cli. `unsafe-budget` is the kiban-native
# gate (net-new `unsafe` blocks without a safety comment fail); the rest run through
# konjo-newonly like the Python tools. Named here so the pack documents its surface; the
# orchestrator's tables remain the single execution source.
TOOLS: tuple[str, ...] = (
    "clippy",
    "fmt-check",
    "cargo-deny",
    "cargo-mutants",
    "unsafe-budget",
)
