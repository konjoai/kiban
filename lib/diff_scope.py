"""diff_scope: derive scope booleans from a changed-file list.

STUB (phase 1). Given the set of files a change touches, emit booleans that tell the
gate runner which specialist lanes and gates to activate, so a docs-only change does
not pay for a mutation-testing run and a Rust change does not run the MLX numerics lane.

Contract for the phase-1 implementation:
  scope(changed_files: list[str]) -> dict[str, bool] with keys:
    SCOPE_RUST, SCOPE_MLX, SCOPE_MOJO, SCOPE_SWIFT, SCOPE_PROMPTS,
    SCOPE_BENCH, SCOPE_DEPS, SCOPE_DOCS
  Classification is by path/extension rules per profile. The runner ANDs these against
  the profile's enabled gates to pick the minimal gate set for the change.
"""

from __future__ import annotations

SCOPE_KEYS = (
    "SCOPE_RUST",
    "SCOPE_MLX",
    "SCOPE_MOJO",
    "SCOPE_SWIFT",
    "SCOPE_PROMPTS",
    "SCOPE_BENCH",
    "SCOPE_DEPS",
    "SCOPE_DOCS",
)


def scope(changed_files: list[str]) -> dict[str, bool]:
    # TODO(phase-1): map file paths/extensions to the scope booleans above.
    raise NotImplementedError("diff_scope is a phase-1 stub")
