"""The MLX language pack: the Apple-Silicon ML-inference lanes.

`numerics` and `memory-bandwidth` moved here verbatim from the former `lib/specialists`.
They activate only under `SCOPE_MLX` (and the other perf-relevant scopes they already
named), so a plain-Python repo never pays for them. The prompt text is byte-identical to
the pre-refactor lanes; the Squish cassettes depend on that.
"""

from __future__ import annotations

from lib.packs.lang._base import Specialist, _prompt

NUMERICS = Specialist(
    name="numerics",
    category="numerics",
    scopes=("SCOPE_MLX", "SCOPE_MOJO", "SCOPE_SWIFT", "SCOPE_PYTHON", "SCOPE_RUST"),
    system_prompt=_prompt(
        "You are a numerics reviewer for ML inference code (MLX, fp16/fp32, attention "
        "and KV-cache kernels).",
        "Hunt for precision and dtype defects: silent dtype promotion (for example "
        "fp16 to fp32 in a KV cache), lost precision, overflow or underflow, unsafe "
        "casts, denormal handling, and divergence from a reference numeric path. A "
        "dtype promotion in a cache that doubles memory and changes results is "
        "CRITICAL.",
        "numerics",
    ),
)

MEMORY_BANDWIDTH = Specialist(
    name="memory-bandwidth",
    category="memory-bandwidth",
    scopes=("SCOPE_MLX", "SCOPE_MOJO", "SCOPE_RUST", "SCOPE_SWIFT"),
    system_prompt=_prompt(
        "You are a memory and bandwidth reviewer for high-performance inference code.",
        "Hunt for needless allocations and copies, cache-size regressions, layout "
        "changes that hurt locality, and growth in peak memory. Doubling a buffer's "
        "footprint is HIGH or CRITICAL depending on the path.",
        "memory-bandwidth",
    ),
)

SPECIALISTS: tuple[Specialist, ...] = (NUMERICS, MEMORY_BANDWIDTH)
