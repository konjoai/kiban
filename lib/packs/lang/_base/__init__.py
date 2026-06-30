"""The pack seam: the language-agnostic specialist machinery, plus the shared lanes.

This is the always-present `_base` pack. It holds what every language pack builds on (the
`Specialist` dataclass, the output contract, the `_prompt` helper, the registry loader, and
`select`) and the lanes that are not language-specific (`concurrency`, `api-surface`, the
`red-team` lane that runs last). Language packs (`mlx`, `python`, `rust`, ...) each expose a
`SPECIALISTS` tuple; `load_registry` assembles a registry from `_base` plus the named packs.

The `Specialist` instances, `_OUTPUT_CONTRACT`, and `_prompt` moved here verbatim from the
former `lib/specialists`. The cassette key is a hash of (specialist, system_prompt,
user_prompt), so this text must not drift: a verbatim move keeps the Squish cassettes valid.
"""

from __future__ import annotations

import importlib
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
    scopes=("SCOPE_SWIFT", "SCOPE_PYTHON", "SCOPE_RUST", "SCOPE_TS", "SCOPE_MOJO"),
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
    scopes=("SCOPE_MLX", "SCOPE_MOJO", "SCOPE_SWIFT", "SCOPE_PYTHON", "SCOPE_RUST", "SCOPE_TS"),
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

# The lanes the `_base` pack always contributes: language-agnostic, present in every
# registry regardless of which language packs a profile names.
SPECIALISTS: tuple[Specialist, ...] = (CONCURRENCY, API_SURFACE, RED_TEAM)


def _import_pack(pack: str) -> object:
    """Import a pack module by its profile name (e.g. 'lang/rust' -> lib.packs.lang.rust)."""
    module = pack.strip().strip("/").replace("/", ".")
    return importlib.import_module(f"lib.packs.{module}")


def load_registry(packs: list[str]) -> dict[str, Specialist]:
    """Build the specialist registry from the always-present `_base` lanes plus each pack.

    Starts from `_base.SPECIALISTS` (so the shared lanes and the red-team lane are always
    available) and folds in each named pack's `SPECIALISTS`. A later pack with a same-named
    lane overrides an earlier one. `_base` (named or not) contributes nothing extra.
    """
    registry: dict[str, Specialist] = {s.name: s for s in SPECIALISTS}
    for pack in packs:
        norm = pack.strip().strip("/").replace("/", ".")
        if norm in ("lang._base", "_base"):
            continue
        mod = _import_pack(pack)
        for spec in getattr(mod, "SPECIALISTS", ()):  # type: ignore[attr-defined]
            registry[spec.name] = spec
    return registry


def select(
    registry: dict[str, Specialist], profile_specialists: list[str], flags: dict[str, bool]
) -> list[Specialist]:
    """Pick the minimal specialist set: in the profile, activated by an in-scope lane.

    The red-team specialist is appended last whenever at least one other specialist
    runs. A docs-only (no code) change selects nothing.
    """
    if not diff_scope.has_code(flags):
        return []

    chosen: list[Specialist] = []
    for name in profile_specialists:
        spec = registry.get(name)
        if spec is None or spec.is_redteam:
            continue
        if any(flags.get(scope) for scope in spec.scopes):
            chosen.append(spec)

    if chosen:
        redteam = registry.get(RED_TEAM.name)
        if redteam is not None:
            chosen.append(redteam)
    return chosen
