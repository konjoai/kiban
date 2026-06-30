"""The Mojo language pack.

Three Mojo-specific lanes plus a tool fragment. Mojo is a Python-superset systems language:
value semantics (`owned` / `borrowed` / `inout`, the `^` transfer), manual memory
(`UnsafePointer`, `memcpy`), SIMD (`SIMD[dtype, width]`, `vectorize`, `parallelize`), and a
Python FFI (`PythonObject`). The lanes target the defects those features invite. The shared
`concurrency`, `api-surface`, and `red-team` lanes from `_base` already cover `SCOPE_MOJO`, so
they are reused, not redefined. Each lane is held to the same JSON finding contract via
`_prompt`, so a Mojo finding parses and dedups exactly like any other.
"""

from __future__ import annotations

from lib.packs.lang._base import Specialist, _prompt

MOJO_MEMORY = Specialist(
    name="mojo-memory",
    category="mojo-memory",
    scopes=("SCOPE_MOJO",),
    system_prompt=_prompt(
        "You are a memory and ownership reviewer for Mojo.",
        "Hunt for unsafe-memory and value-semantics defects: an `UnsafePointer` read or store "
        "past the buffer length (an out-of-bounds SIMD `load`/`store`), a manual allocation "
        "with no matching free, aliasing two mutable views of the same buffer, a wrong "
        "argument convention (`owned` / `borrowed` / `inout`) that copies or mutates "
        "unexpectedly, and use of a value after it was transferred with `^`. A real "
        "out-of-bounds or use-after-transfer is CRITICAL.",
        "mojo-memory",
    ),
)

MOJO_NUMERICS = Specialist(
    name="mojo-numerics",
    category="mojo-numerics",
    scopes=("SCOPE_MOJO",),
    system_prompt=_prompt(
        "You are a numerics and SIMD-correctness reviewer for Mojo quantization code.",
        "Hunt for precision and SIMD-width defects: a `SIMD[dtype, width]` whose width or "
        "dtype mismatches the accumulator or the store, an unsafe `cast`/`bitcast` that loses "
        "or reinterprets bits, overflow in a fixed-width integer accumulation, a quantization "
        "step that loses precision or clamps wrong (a missing or wrong saturating clamp before "
        "an int8 cast), and divergence from the reference numeric path. A silent precision or "
        "overflow bug on the quantization hot path is CRITICAL.",
        "mojo-numerics",
    ),
)

MOJO_PERF = Specialist(
    name="mojo-perf",
    category="mojo-perf",
    scopes=("SCOPE_MOJO",),
    system_prompt=_prompt(
        "You are a performance reviewer for Mojo.",
        "Hunt for a needless copy under value semantics (passing or returning a large `List` or "
        "buffer by copy where a `borrowed` reference or a `^` transfer was meant), a hot loop "
        "left scalar where `vectorize` or `parallelize` was intended, a missing "
        "`@always_inline` / `@parameter` on a hot kernel, and an allocation inside a hot loop. "
        "Scope your findings to changes that plausibly sit on a hot path.",
        "mojo-perf",
    ),
)

SPECIALISTS: tuple[Specialist, ...] = (MOJO_MEMORY, MOJO_NUMERICS, MOJO_PERF)

# The Mojo tool surface. Mojo ships a formatter (`mojo format`) and a test runner
# (`mojo test`); a repo wires the ones its CI uses. Named here so the pack documents its
# surface; the orchestrator's tables remain the single execution source.
TOOLS: tuple[str, ...] = (
    "mojo-format",
    "mojo-test",
)
