"""Prompt-driven review specialists for the kiban meta-gate.

Each specialist is a focused reviewer with its own system prompt, invoked through a
backend (the Claude CLI in production, a scripted backend in tests). The registry here
plus the scope map in diff_scope drive which specialists run on a given diff. The
red-team specialist runs last and is handed the other specialists' findings.
"""

from __future__ import annotations

from dataclasses import dataclass

from lib import diff_scope


@dataclass(frozen=True)
class Specialist:
    name: str
    category: str
    scopes: tuple[str, ...]
    system_prompt: str
    is_redteam: bool = False


# The output contract every specialist is held to. Kept in one place so all prompts
# agree on the Finding shape the parser expects.
_OUTPUT_CONTRACT = """
Output ONLY one of these two things, nothing else:
1. The literal text NO FINDINGS  (when the diff is clean for your specialty), or
2. A JSON array of finding objects. Each object has exactly these keys:
   {"severity": "CRITICAL|HIGH|MEDIUM|LOW",
    "confidence": <integer 0-10>,
    "path": "<file path from the diff>",
    "line": <integer line number or null>,
    "category": "<your specialty category>",
    "summary": "<one plain sentence naming the defect>",
    "fix": "<one plain sentence naming the fix>"}
Do not wrap the JSON in prose. Do not use code fences. Be precise; a false alarm on a
correct change is itself a defect. Only report defects you can point to in the diff.
""".strip()


def _prompt(role: str, focus: str, category: str) -> str:
    return f"{role}\n\n{focus}\n\nYour finding category is \"{category}\".\n\n{_OUTPUT_CONTRACT}"


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

CONCURRENCY = Specialist(
    name="concurrency",
    category="concurrency",
    scopes=("SCOPE_RUST", "SCOPE_SWIFT", "SCOPE_PYTHON", "SCOPE_MOJO"),
    system_prompt=_prompt(
        "You are a concurrency reviewer.",
        "Hunt for data races, unsynchronized shared state, deadlocks, lost wakeups, and "
        "ordering bugs. Flag shared mutable state crossing threads without a guard.",
        "concurrency",
    ),
)

API_SURFACE = Specialist(
    name="api-surface",
    category="api-surface",
    scopes=("SCOPE_SWIFT", "SCOPE_PYTHON", "SCOPE_RUST"),
    system_prompt=_prompt(
        "You are an API-surface reviewer.",
        "Hunt for breaking changes to a public signature, return type, or contract: a "
        "removed or renamed parameter, a changed default, a narrowed type, or a silent "
        "behavior change a caller would not expect. A purely additive optional "
        "parameter that preserves behavior is NOT a finding.",
        "api-surface",
    ),
)

RED_TEAM = Specialist(
    name="red-team",
    category="red-team",
    scopes=("SCOPE_MLX", "SCOPE_MOJO", "SCOPE_SWIFT", "SCOPE_PYTHON", "SCOPE_RUST"),
    is_redteam=True,
    system_prompt=_prompt(
        "You are a red-team reviewer. You run after the other specialists and see what "
        "they reported.",
        "Hunt for what they missed: edge cases, interaction bugs, and defects that fall "
        "between specialties. Do not repeat a finding the others already raised; only "
        "add what is new.",
        "red-team",
    ),
)

_ALL = (NUMERICS, MEMORY_BANDWIDTH, CONCURRENCY, API_SURFACE, RED_TEAM)
REGISTRY: dict[str, Specialist] = {s.name: s for s in _ALL}


def select(profile_specialists: list[str], flags: dict[str, bool]) -> list[Specialist]:
    """Pick the minimal specialist set: in the profile, activated by an in-scope lane.

    The red-team specialist is appended last whenever at least one other specialist
    runs. A docs-only (no code) change selects nothing.
    """
    if not diff_scope.has_code(flags):
        return []

    chosen: list[Specialist] = []
    for name in profile_specialists:
        spec = REGISTRY.get(name)
        if spec is None or spec.is_redteam:
            continue
        if any(flags.get(scope) for scope in spec.scopes):
            chosen.append(spec)

    if chosen:
        chosen.append(RED_TEAM)
    return chosen
