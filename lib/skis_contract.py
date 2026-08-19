"""Skis contract gate: keeps a plugins/konjo/skills/<name>/SKILL.md and its
konjo-skis/<name>/SKILL.md portable variant in sync on the content a manifest
declares must match, while letting genuinely divergent content (e.g. a CLI
shell-out read path vs a Cortex-page read path) diverge on purpose. See
konjo-skis/CONTRACT.yml for the declared contract itself, and
LEDGER.md's Skis-Contract-1 entry for why this exists: konjo-skis/README.md
argued two files beat one file with an if-cli-available branch, but two names
alone do nothing to stop one file receiving a correctness fix the other never
gets (the exact class of drift Doc-Integrity-Gate-1 found and fixed once
already, for konjo-ship).

Sections are delimited inline by HTML-comment markers:

    <!-- skis-contract:<id> -->
    ...content...
    <!-- /skis-contract:<id> -->

must_match sections: extracted content, whitespace-normalized, must be
identical across both files in a pair. Drift is a FAIL naming the section id
and both file paths.

divergent sections: both files must still carry the marker (tracked, not
merely absent) and the manifest entry must give a non-empty `why:` reason;
content is never compared.

A must_match or divergent id declared in the manifest that is missing its
marker in either file is a failure in its own right -- the contract and the
docs have drifted apart from each other, the same failure mode one layer up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml  # type: ignore[import-untyped]

_MARKER_RE = re.compile(
    r"<!--\s*skis-contract:(?P<id>[\w.\-]+)\s*-->(?P<body>.*?)"
    r"<!--\s*/skis-contract:(?P=id)\s*-->",
    re.DOTALL,
)


def _normalize(text: str) -> str:
    """Collapse all whitespace runs to a single space so differing line-wrap
    width between two prose files doesn't register as drift -- only the
    words themselves are compared."""
    return re.sub(r"\s+", " ", text).strip()


def extract_sections(doc_text: str) -> dict[str, str]:
    """id -> raw marked body, first occurrence wins on a duplicate id."""
    sections: dict[str, str] = {}
    for m in _MARKER_RE.finditer(doc_text):
        sections.setdefault(m.group("id"), m.group("body"))
    return sections


@dataclass
class Drift:
    pair: str
    section: str
    kind: str  # "content_mismatch" | "missing_marker" | "missing_reason"
    detail: str


@dataclass
class ContractResult:
    ok: bool = True
    drifts: list[Drift] = field(default_factory=list)
    checked_pairs: int = 0
    must_match_count: int = 0
    divergent_count: int = 0

    def summary(self) -> str:
        if self.ok:
            return (
                f"skis-contract: OK -- {self.checked_pairs} pair(s), "
                f"{self.must_match_count} must-match section(s), "
                f"{self.divergent_count} declared-divergent section(s)"
            )
        lines = [f"skis-contract: FAIL -- {len(self.drifts)} drift(s)"]
        for d in self.drifts:
            lines.append(f"  [{d.pair}] {d.section} ({d.kind}): {d.detail}")
        return "\n".join(lines)


def _check_present(
    pair_name: str,
    sid: str,
    plugin_path: Path,
    skis_path: Path,
    plugin_sections: dict[str, str],
    skis_sections: dict[str, str],
    result: ContractResult,
) -> bool:
    """Returns True iff the marker is present in both files."""
    present = True
    if sid not in plugin_sections:
        result.ok = False
        present = False
        result.drifts.append(Drift(
            pair_name, sid, "missing_marker",
            f"{plugin_path} has no <!-- skis-contract:{sid} --> marker",
        ))
    if sid not in skis_sections:
        result.ok = False
        present = False
        result.drifts.append(Drift(
            pair_name, sid, "missing_marker",
            f"{skis_path} has no <!-- skis-contract:{sid} --> marker",
        ))
    return present


def check_contract(manifest_path: Path, repo_root: Path) -> ContractResult:
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    result = ContractResult()

    for pair_name, pair_cfg in (manifest.get("pairs") or {}).items():
        result.checked_pairs += 1
        plugin_path = repo_root / pair_cfg["plugin"]
        skis_path = repo_root / pair_cfg["skis"]
        plugin_sections = extract_sections(plugin_path.read_text(encoding="utf-8"))
        skis_sections = extract_sections(skis_path.read_text(encoding="utf-8"))

        for entry in pair_cfg.get("must_match") or []:
            sid = entry["id"]
            result.must_match_count += 1
            both_present = _check_present(
                pair_name, sid, plugin_path, skis_path,
                plugin_sections, skis_sections, result,
            )
            if both_present:
                a = _normalize(plugin_sections[sid])
                b = _normalize(skis_sections[sid])
                if a != b:
                    result.ok = False
                    result.drifts.append(Drift(
                        pair_name, sid, "content_mismatch",
                        f"{plugin_path} and {skis_path} disagree on "
                        f"must-match section {sid!r}",
                    ))

        for entry in pair_cfg.get("divergent") or []:
            sid = entry["id"]
            result.divergent_count += 1
            if not str(entry.get("why", "")).strip():
                result.ok = False
                result.drifts.append(Drift(
                    pair_name, sid, "missing_reason",
                    f"divergent section {sid!r} in pair {pair_name!r} has "
                    f"no why: reason",
                ))
            _check_present(
                pair_name, sid, plugin_path, skis_path,
                plugin_sections, skis_sections, result,
            )

    return result
