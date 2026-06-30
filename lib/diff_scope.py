"""diff_scope: derive scope booleans from a changed-file list.

Given the files a change touches, emit booleans that tell the engine which specialist
lanes to run and tell CI when the prompt-eval gate must fire. A docs-only change should
not pay for the numerics lane; a Rust change should not run the MLX lane.

Classification is by path and extension, plus a light content sniff for MLX (an `mx.`
import or call) since MLX code lives in `.py` files. The engine ANDs these flags against
the profile's specialist list to pick the minimal set per change.
"""

from __future__ import annotations

import re

SCOPE_KEYS = (
    "SCOPE_RUST",
    "SCOPE_MLX",
    "SCOPE_MOJO",
    "SCOPE_SWIFT",
    "SCOPE_PYTHON",
    "SCOPE_TS",
    "SCOPE_PROMPTS",
    "SCOPE_BENCH",
    "SCOPE_DEPS",
    "SCOPE_DOCS",
)

_EXT = {
    ".rs": "SCOPE_RUST",
    ".mojo": "SCOPE_MOJO",
    ".🔥": "SCOPE_MOJO",
    ".swift": "SCOPE_SWIFT",
    ".py": "SCOPE_PYTHON",
    ".pyi": "SCOPE_PYTHON",
    ".ts": "SCOPE_TS",
    ".tsx": "SCOPE_TS",
    ".mts": "SCOPE_TS",
    ".md": "SCOPE_DOCS",
    ".markdown": "SCOPE_DOCS",
    ".rst": "SCOPE_DOCS",
    ".txt": "SCOPE_DOCS",
}

_DEP_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "uv.lock",
    "cargo.toml",
    "cargo.lock",
    "package.json",
    "package-lock.json",
    "go.mod",
    "go.sum",
}

_PROMPT_HINT = re.compile(r"(prompt|specialist|skill|\.tmpl|/prompts?/)", re.IGNORECASE)
_BENCH_HINT = re.compile(r"(bench|benchmark)", re.IGNORECASE)
_MLX_HINT = re.compile(r"\bmx\.|\bimport mlx\b|from mlx\b")


def _ext(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    return name[dot:].lower() if dot > 0 else ""


def scope(changed_files: list[str], diff_text: str | None = None) -> dict[str, bool]:
    """Map changed files to the scope booleans. Optional diff_text enables the MLX sniff."""
    flags = dict.fromkeys(SCOPE_KEYS, False)

    for path in changed_files:
        lower = path.lower()
        base = lower.rsplit("/", 1)[-1]

        ext_scope = _EXT.get(_ext(path))
        if ext_scope:
            flags[ext_scope] = True

        if base in _DEP_FILES:
            flags["SCOPE_DEPS"] = True
        if _PROMPT_HINT.search(lower):
            flags["SCOPE_PROMPTS"] = True
        if _BENCH_HINT.search(lower):
            flags["SCOPE_BENCH"] = True
        if "docs/" in lower:
            flags["SCOPE_DOCS"] = True

    # MLX lives in .py files; a content sniff promotes SCOPE_MLX when the diff touches it.
    if diff_text and _MLX_HINT.search(diff_text):
        flags["SCOPE_MLX"] = True

    return flags


CODE_SCOPES = (
    "SCOPE_RUST",
    "SCOPE_MLX",
    "SCOPE_MOJO",
    "SCOPE_SWIFT",
    "SCOPE_PYTHON",
    "SCOPE_TS",
)


def has_code(flags: dict[str, bool]) -> bool:
    """True if any code lane is in scope. Docs/deps/bench-only changes are not code."""
    return any(flags.get(k) for k in CODE_SCOPES)
