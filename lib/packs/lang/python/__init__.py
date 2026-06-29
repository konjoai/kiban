"""The Python language pack.

The Python review lanes from plan section 5b (`typing-contracts`, `correctness`) are
deferred to a later sprint; `SPECIALISTS` is intentionally empty for now. The shared
`concurrency` and `api-surface` lanes from `_base` already cover Python diffs, and the
ML-inference lanes live in the `mlx` pack. `TOOLS` names the Python tool set already wired
into the orchestrator (`konjo_gates_py.cli`), kept here so the pack documents its surface.
"""

from __future__ import annotations

from lib.packs.lang._base import Specialist

# Deferred: typing-contracts, correctness (plan section 5b). Empty until a later sprint so
# no Python prose lands that could perturb the Squish cassettes.
SPECIALISTS: tuple[Specialist, ...] = ()

# The Python contract/format-lint tools, already wired in konjo_gates_py.cli. Named here as
# the pack's tool surface; the orchestrator's tables remain the single execution source.
TOOLS: tuple[str, ...] = (
    "ruff",
    "ruff-format",
    "mypy",
    "vulture",
    "bandit",
    "radon",
    "interrogate",
    "mutmut",
)
