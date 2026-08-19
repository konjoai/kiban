"""Tests for the doc staleness gate (lib/doc_staleness.py)."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from lib import doc_staleness, oneway

TODAY = date(2026, 7, 24)
_KIBAN_ROOT = Path(__file__).resolve().parent.parent


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    return repo


def _commit(repo: Path, name: str, contents: str, msg: str = "commit") -> str:
    (repo / name).write_text(contents)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", msg)
    return _git(repo, "rev-parse", "HEAD")


def _bump(repo: Path, n: int) -> None:
    """Add n throwaway commits so HEAD moves n commits past whatever came before."""
    for i in range(n):
        _commit(repo, f"filler-{i}.txt", "x", f"filler {i}")


# ---------------------------------------------------------------------------
# parse_front_matter
# ---------------------------------------------------------------------------


def test_parse_front_matter_basic() -> None:
    text = "---\ndecays: state\nverified-against: abc123\n---\n\n# Body\n"
    fm, body = doc_staleness.parse_front_matter(text)
    assert fm == {"decays": "state", "verified-against": "abc123"}
    assert body.strip() == "# Body"


def test_parse_front_matter_absent() -> None:
    fm, body = doc_staleness.parse_front_matter("# Just a doc\nno front matter here\n")
    assert fm is None
    assert body == "# Just a doc\nno front matter here\n"


def test_parse_front_matter_malformed_yaml_does_not_crash() -> None:
    text = "---\ndecays: [unterminated\n---\nbody\n"
    fm, body = doc_staleness.parse_front_matter(text)
    assert fm == {}
    assert "body" in body


def test_parse_front_matter_non_mapping_yaml_does_not_crash() -> None:
    text = "---\n- just\n- a\n- list\n---\nbody\n"
    fm, _ = doc_staleness.parse_front_matter(text)
    assert fm == {}


# ---------------------------------------------------------------------------
# check_document — the five required scenarios
# ---------------------------------------------------------------------------


def test_fresh_state_doc_passes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "seed.txt", "seed")
    head = _git(repo, "rev-parse", "HEAD")
    doc = repo / "ROADMAP.md"
    doc.write_text(
        f"---\ndecays: state\nverified-against: {head}\nverified-date: '2026-07-24'\n---\n"
        "# Roadmap\nEverything here was true at the stamped commit.\n"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "add roadmap")
    # HEAD has moved on by one commit (the doc's own commit) — well within any threshold.
    result = doc_staleness.check_document(doc, repo_root=repo, today=TODAY)
    assert result.verdict == doc_staleness.OK
    assert result.commits_behind is not None
    assert result.commits_behind <= doc_staleness.DEFAULT_STALE_COMMITS


def test_stale_state_doc_fails_on_commits(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    stamped_sha = _commit(repo, "seed.txt", "seed")
    doc = repo / "ROADMAP.md"
    doc.write_text(
        f"---\ndecays: state\nverified-against: {stamped_sha}\nverified-date: '2026-07-24'\n---\n"
        "# Roadmap\n"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "add roadmap")
    _bump(repo, 5)  # push HEAD well past the stamp

    result = doc_staleness.check_document(
        doc, repo_root=repo, today=TODAY, stale_commits=2, stale_days=365
    )
    assert result.verdict == doc_staleness.FAIL
    assert "stale" in result.reason


def test_stale_state_doc_fails_on_days(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    head = _commit(repo, "seed.txt", "seed")
    doc = repo / "ROADMAP.md"
    old_date = (TODAY - timedelta(days=60)).isoformat()
    doc.write_text(
        f"---\ndecays: state\nverified-against: {head}\n"
        f"verified-date: '{old_date}'\n---\n# Roadmap\n"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "add roadmap")

    result = doc_staleness.check_document(
        doc, repo_root=repo, today=TODAY, stale_commits=1000, stale_days=14
    )
    assert result.verdict == doc_staleness.FAIL
    assert result.days_behind is not None and result.days_behind > 14


def test_unstamped_state_doc_hard_fails(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "seed.txt", "seed")
    doc = repo / "ROADMAP.md"
    doc.write_text("---\ndecays: state\n---\n# Roadmap\nNo stamp at all.\n")
    result = doc_staleness.check_document(doc, repo_root=repo, today=TODAY)
    assert result.verdict == doc_staleness.FAIL
    assert "unstamped" in result.reason


def test_historical_doc_exempt_regardless_of_age(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    old_sha = _commit(repo, "seed.txt", "seed")
    doc = repo / "FEATURE_STATE_FINAL.md"
    doc.write_text(
        f"---\ndecays: historical\nverified-against: {old_sha}\n---\n"
        "# Feature state\n\n**Baseline:** main @ deadbeef, **Date:** 2020-01-01\n"
        "Long since superseded, but honest about when it was true.\n"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "add snapshot")
    _bump(repo, 50)  # far more commits than any state threshold would tolerate

    result = doc_staleness.check_document(
        doc, repo_root=repo, today=TODAY, stale_commits=1, stale_days=1
    )
    assert result.verdict == doc_staleness.OK
    assert "exempt" in result.reason


def test_historical_doc_without_dated_banner_warns_not_fails(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "seed.txt", "seed")
    doc = repo / "OLD_NOTES.md"
    doc.write_text(
        "---\ndecays: historical\n---\n# Notes\nNo date visible anywhere near the top.\n"
    )
    result = doc_staleness.check_document(doc, repo_root=repo, today=TODAY)
    assert result.verdict == doc_staleness.WARN
    assert "dated banner" in result.reason


def test_doc_with_no_front_matter_reported_not_crash(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "seed.txt", "seed")
    doc = repo / "README.md"
    doc.write_text("# Just a normal doc\nNothing special.\n")
    result = doc_staleness.check_document(doc, repo_root=repo, today=TODAY)
    assert result.verdict == doc_staleness.SKIP


# ---------------------------------------------------------------------------
# intent / reference — warn only, never fail
# ---------------------------------------------------------------------------


def test_reference_doc_never_fails_even_when_very_old(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    old_sha = _commit(repo, "seed.txt", "seed")
    doc = repo / "README.md"
    old_date = (TODAY - timedelta(days=3000)).isoformat()
    doc.write_text(
        f"---\ndecays: reference\nverified-against: {old_sha}\nverified-date: '{old_date}'\n---\n"
        "# README\n"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "add readme")
    _bump(repo, 50)

    result = doc_staleness.check_document(
        doc, repo_root=repo, today=TODAY, stale_commits=1, stale_days=1
    )
    assert result.verdict == doc_staleness.WARN


def test_intent_doc_with_no_stamp_warns(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "seed.txt", "seed")
    doc = repo / "VISION.md"
    doc.write_text("---\ndecays: intent\n---\n# Vision\n")
    result = doc_staleness.check_document(doc, repo_root=repo, today=TODAY)
    assert result.verdict == doc_staleness.WARN
    assert "warn only" in result.reason


# ---------------------------------------------------------------------------
# malformed stamps
# ---------------------------------------------------------------------------


def test_unresolvable_verified_against_sha_fails(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "seed.txt", "seed")
    doc = repo / "ROADMAP.md"
    doc.write_text("---\ndecays: state\nverified-against: 0000000notreal\n---\n# Roadmap\n")
    result = doc_staleness.check_document(doc, repo_root=repo, today=TODAY)
    assert result.verdict == doc_staleness.FAIL
    assert "not found" in result.reason


def test_malformed_verified_date_fails(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    head = _commit(repo, "seed.txt", "seed")
    doc = repo / "ROADMAP.md"
    doc.write_text(
        f"---\ndecays: state\nverified-against: {head}\n"
        "verified-date: 'not-a-date'\n---\n# Roadmap\n"
    )
    result = doc_staleness.check_document(doc, repo_root=repo, today=TODAY, stale_commits=1000)
    assert result.verdict == doc_staleness.FAIL
    assert "not a valid" in result.reason


def test_no_recognized_decays_value_is_skip(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "seed.txt", "seed")
    doc = repo / "WEIRD.md"
    doc.write_text("---\ndecays: someday\n---\n# Weird\n")
    result = doc_staleness.check_document(doc, repo_root=repo, today=TODAY)
    assert result.verdict == doc_staleness.SKIP


# ---------------------------------------------------------------------------
# scan_repo
# ---------------------------------------------------------------------------


def test_check_document_path_outside_repo_root_does_not_crash(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    head = _commit(repo, "seed.txt", "seed")
    outside = tmp_path / "elsewhere" / "STAMPED.md"
    outside.parent.mkdir()
    outside.write_text(f"---\ndecays: state\nverified-against: {head}\n---\n# Doc\n")
    result = doc_staleness.check_document(outside, repo_root=repo, today=TODAY)
    assert result.verdict == doc_staleness.OK
    assert result.path == str(outside)


def test_scan_repo_skips_git_dir_and_finds_docs(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "seed.txt", "seed")
    (repo / "PLAIN.md").write_text("# Plain\n")
    (repo / "STATE.md").write_text("---\ndecays: state\n---\n# unstamped\n")
    results = doc_staleness.scan_repo(repo, today=TODAY)
    paths = {r.path for r in results}
    assert "PLAIN.md" in paths
    assert "STATE.md" in paths
    assert not any(p.startswith(".git") for p in paths)
    state_result = next(r for r in results if r.path == "STATE.md")
    assert state_result.verdict == doc_staleness.FAIL


# ---------------------------------------------------------------------------
# Konjo-Doc-Verified trailer
# ---------------------------------------------------------------------------


def test_doc_verified_trailer_roundtrip() -> None:
    fp = oneway.fingerprint(["ROADMAP.md", "PLAN.md"])
    trailer = doc_staleness.doc_verified_trailer(fp)
    assert trailer == f"Konjo-Doc-Verified: {fp}"
    msgs = f"docs: re-verify state docs\n\n{trailer}\n"
    assert doc_staleness.find_doc_verified(msgs, fp)
    assert not doc_staleness.find_doc_verified("no trailer here", fp)


# ---------------------------------------------------------------------------
# check_projection -- event-clocked staleness for projected Cortex pages
# ---------------------------------------------------------------------------


def _cortex_page(tmp_path: Path, projected_at: str) -> Path:
    p = tmp_path / "org.md"
    p.write_text(
        f"---\ndecays: state\nscope: org\nprojected-at: {projected_at}\n"
        "source-events:\n  - abc123\n---\n\n# Cortex\n"
    )
    return p


def test_projection_fresh_when_projected_at_matches_newest_event(tmp_path: Path) -> None:
    page = _cortex_page(tmp_path, "2026-07-20T12:00:00Z")
    check = doc_staleness.check_projection(page, newest_event_at="2026-07-20T12:00:00Z")
    assert check.verdict == doc_staleness.OK


def test_projection_stale_when_newer_event_landed(tmp_path: Path) -> None:
    page = _cortex_page(tmp_path, "2026-07-20T12:00:00Z")
    check = doc_staleness.check_projection(page, newest_event_at="2026-07-25T09:00:00Z")
    assert check.verdict == doc_staleness.FAIL
    assert "stale projection" in check.reason


def test_projection_ok_when_scope_has_no_events_yet(tmp_path: Path) -> None:
    page = _cortex_page(tmp_path, "2026-07-20T12:00:00Z")
    check = doc_staleness.check_projection(page, newest_event_at=None)
    assert check.verdict == doc_staleness.OK


def test_projection_missing_stamp_fails(tmp_path: Path) -> None:
    page = tmp_path / "org.md"
    page.write_text("---\ndecays: state\nscope: org\n---\n\n# Cortex\n")
    check = doc_staleness.check_projection(page, newest_event_at="2026-07-20T12:00:00Z")
    assert check.verdict == doc_staleness.FAIL
    assert "no projected-at stamp" in check.reason


def test_projection_non_state_decays_is_skip(tmp_path: Path) -> None:
    page = tmp_path / "org.md"
    page.write_text("---\ndecays: reference\nscope: org\n---\n\n# Cortex\n")
    check = doc_staleness.check_projection(page, newest_event_at="2026-07-20T12:00:00Z")
    assert check.verdict == doc_staleness.SKIP


# ---------------------------------------------------------------------------
# KT-6 -- pipeline-level: the real CLI chain (not check_projection() directly)
# fails closed on a fold that never re-ran, and clears once it does
# ---------------------------------------------------------------------------


def _run_cli(script: str, args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_KIBAN_ROOT / "bin" / script), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _decide(scope: str, text: str, env: dict[str, str]) -> None:
    r = _run_cli(
        "konjo-decision",
        [
            "decide", "--scope", scope, "--decision", text,
            "--rationale", "kt6 fixture", "--author", "kt6",
        ],
        env,
    )
    assert r.returncode == 0, r.stderr


def _project(cortex_dir: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return _run_cli(
        "konjo-decision", ["project", "--all-scopes", "--out-dir", str(cortex_dir)], env
    )


def test_kt6_project_scan_fails_closed_when_fold_never_reran(tmp_path: Path) -> None:
    """This is the exact failure mode konjo-ship's checklist line (and the
    `cortex_fold_push.sh` hook that now runs it) exists to catch: a Ledger write this
    sprint made and never re-folded leaves Cortex silently stale. Real subprocess calls
    to the actual CLIs, not `doc_staleness.check_projection()` called directly -- this is
    what `test_projection_stale_when_newer_event_landed` above already covers at the
    unit level; this proves the full `konjo-decision` -> `konjo-doc-staleness` pipeline
    fails closed end to end.
    """
    state_dir = tmp_path / "state"
    cortex_dir = tmp_path / "cortex"
    state_dir.mkdir()
    cortex_dir.mkdir()
    env = {**os.environ, "KONJO_STATE_DIR": str(state_dir)}

    _decide("repo:kt6", "First decision", env)

    project1 = _project(cortex_dir, env)
    assert project1.returncode == 0, project1.stderr
    assert (cortex_dir / "repo-kt6.md").exists()

    scan1 = _run_cli("konjo-doc-staleness", ["project-scan", "--cortex-dir", str(cortex_dir)], env)
    assert scan1.returncode == 0, scan1.stdout + scan1.stderr

    # The Ledger's own event date has 1-second resolution (ledger/engine.py) -- sleep
    # past it so the second decision is provably newer than what got folded above,
    # not a same-second race.
    time.sleep(1.1)
    _decide("repo:kt6", "Second decision, deliberately never folded", env)

    # No re-run of `project` here -- this is the gap KT-6 exists to prove the gate catches.
    scan2 = _run_cli("konjo-doc-staleness", ["project-scan", "--cortex-dir", str(cortex_dir)], env)
    assert scan2.returncode == 1, scan2.stdout + scan2.stderr
    assert "FAIL" in scan2.stdout


def test_kt6_project_scan_passes_after_refold(tmp_path: Path) -> None:
    """Companion to the fail-closed test above: re-running `project` after the second
    write clears the same FAIL, proving the gate tracks real fold state rather than
    being permanently red once a page has ever gone stale.
    """
    state_dir = tmp_path / "state"
    cortex_dir = tmp_path / "cortex"
    state_dir.mkdir()
    cortex_dir.mkdir()
    env = {**os.environ, "KONJO_STATE_DIR": str(state_dir)}

    _decide("repo:kt6b", "First decision", env)
    _decide("repo:kt6b", "Second decision, will be folded", env)

    project = _project(cortex_dir, env)
    assert project.returncode == 0, project.stderr

    scan = _run_cli("konjo-doc-staleness", ["project-scan", "--cortex-dir", str(cortex_dir)], env)
    assert scan.returncode == 0, scan.stdout + scan.stderr
