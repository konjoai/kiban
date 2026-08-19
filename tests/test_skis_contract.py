"""Tests for the skis contract gate (lib/skis_contract.py)."""

from __future__ import annotations

from pathlib import Path

from lib.skis_contract import check_contract, extract_sections

MANIFEST_TEMPLATE = """
pairs:
  demo:
    plugin: plugin.md
    skis: skis.md
    must_match:
      - id: demo.rule
        why: must stay identical on purpose, for this test
    divergent:
      - id: demo.mechanism
        why: intentionally different, for this test
"""


def _write(repo: Path, name: str, text: str) -> Path:
    p = repo / name
    p.write_text(text, encoding="utf-8")
    return p


def _manifest(repo: Path) -> Path:
    return _write(repo, "CONTRACT.yml", MANIFEST_TEMPLATE)


def _block(section_id: str, body: str) -> str:
    return f"<!-- skis-contract:{section_id} -->\n{body}\n<!-- /skis-contract:{section_id} -->"


def test_extract_sections_basic():
    text = (
        "before\n" + _block("foo", "foo body") + "\n"
        "between\n" + _block("bar", "bar body") + "\n"
        "after\n"
    )
    sections = extract_sections(text)
    assert set(sections) == {"foo", "bar"}
    assert "foo body" in sections["foo"]
    assert "bar body" in sections["bar"]


def test_clean_pair_passes(tmp_path: Path):
    manifest = _manifest(tmp_path)
    shared = _block("demo.rule", "Same rule text.")
    divergent_a = _block("demo.mechanism", "plugin mechanism")
    divergent_b = _block("demo.mechanism", "skis mechanism, worded differently")
    _write(tmp_path, "plugin.md", shared + "\n" + divergent_a)
    _write(tmp_path, "skis.md", shared + "\n" + divergent_b)

    result = check_contract(manifest, tmp_path)
    assert result.ok, result.summary()
    assert result.checked_pairs == 1
    assert result.must_match_count == 1
    assert result.divergent_count == 1


def test_whitespace_only_difference_still_passes(tmp_path: Path):
    """Line-wrap width differing between two prose files is not drift."""
    manifest = _manifest(tmp_path)
    plugin_rule = _block("demo.rule", "Same rule\ntext wrapped\nacross lines.")
    skis_rule = _block("demo.rule", "Same rule text wrapped across\nlines.")
    divergent = _block("demo.mechanism", "x")
    _write(tmp_path, "plugin.md", plugin_rule + "\n" + divergent)
    _write(tmp_path, "skis.md", skis_rule + "\n" + divergent)

    result = check_contract(manifest, tmp_path)
    assert result.ok, result.summary()


def test_must_match_drift_fails_naming_section_and_paths(tmp_path: Path):
    manifest = _manifest(tmp_path)
    divergent = _block("demo.mechanism", "x")
    plugin_rule = _block("demo.rule", "Original rule.")
    skis_rule = _block("demo.rule", "Changed rule, only here.")
    _write(tmp_path, "plugin.md", plugin_rule + "\n" + divergent)
    _write(tmp_path, "skis.md", skis_rule + "\n" + divergent)

    result = check_contract(manifest, tmp_path)
    assert not result.ok
    mismatches = [d for d in result.drifts if d.kind == "content_mismatch"]
    assert len(mismatches) == 1
    assert mismatches[0].section == "demo.rule"
    assert "plugin.md" in mismatches[0].detail
    assert "skis.md" in mismatches[0].detail


def test_divergent_section_edit_does_not_fail(tmp_path: Path):
    """Editing a declared-divergent section on only one side must stay quiet."""
    manifest = _manifest(tmp_path)
    shared = _block("demo.rule", "Same rule text.")
    plugin_mech = _block("demo.mechanism", "original mechanism")
    skis_mech = _block("demo.mechanism", "completely different, edited freely")
    _write(tmp_path, "plugin.md", shared + "\n" + plugin_mech)
    _write(tmp_path, "skis.md", shared + "\n" + skis_mech)

    result = check_contract(manifest, tmp_path)
    assert result.ok, result.summary()


def test_missing_marker_in_one_file_fails(tmp_path: Path):
    manifest = _manifest(tmp_path)
    divergent = _block("demo.mechanism", "x")
    plugin_rule = _block("demo.rule", "Rule.")
    _write(tmp_path, "plugin.md", plugin_rule + "\n" + divergent)
    _write(tmp_path, "skis.md", "no marker here at all\n" + divergent)

    result = check_contract(manifest, tmp_path)
    assert not result.ok
    missing = [d for d in result.drifts if d.kind == "missing_marker"]
    assert len(missing) == 1
    assert missing[0].section == "demo.rule"


def test_divergent_without_reason_fails(tmp_path: Path):
    manifest_text = MANIFEST_TEMPLATE.replace(
        "why: intentionally different, for this test", "why: ''"
    )
    manifest = _write(tmp_path, "CONTRACT.yml", manifest_text)
    shared = _block("demo.rule", "Same rule text.")
    divergent = _block("demo.mechanism", "x")
    _write(tmp_path, "plugin.md", shared + "\n" + divergent)
    _write(tmp_path, "skis.md", shared + "\n" + divergent)

    result = check_contract(manifest, tmp_path)
    assert not result.ok
    reasons = [d for d in result.drifts if d.kind == "missing_reason"]
    assert len(reasons) == 1


def test_real_manifest_is_clean():
    """The real konjo-skis/CONTRACT.yml against the real SKILL.md files must pass --
    this is the state the gate ships in, not just a synthetic fixture."""
    repo_root = Path(__file__).resolve().parent.parent
    manifest = repo_root / "konjo-skis" / "CONTRACT.yml"
    result = check_contract(manifest, repo_root)
    assert result.ok, result.summary()
    assert result.checked_pairs == 2
    assert result.must_match_count == 6
    assert result.divergent_count == 1
