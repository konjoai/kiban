"""Doc staleness gate: the `decays:` front-matter convention, made checkable.

A markdown doc that asserts current-state facts ("no MCP", "no worktrees") is a claim,
and a claim with no stamp on it decays silently. This module is the mechanism that keeps
that class of claim from going stale unnoticed: a document opts in with a `decays:`
front-matter field, and this checker fails a `state` doc once its `verified-against`
stamp falls too far behind HEAD.

Four decay classes, because the class is the whole point (a roadmap and a changelog do
not age the same way):

  historical  append-only claims about the past (CHANGELOG.md, LEDGER.md, dated audits).
              Never decays; the past does not change. Exempt from the staleness check by
              declaration, but WARN if it lacks a visible dated banner near the top (a
              baseline SHA and date a reader can see without opening git log).
  intent      why-docs, vision. Long horizon: WARN only, never FAIL.
  reference   how to use the thing now (README.md, CLAUDE.md). Moderate horizon: WARN only.
  state       what is and isn't built right now (roadmap gap tables, feature matrices,
              parity audits). Decays every sprint; highest harm when stale, because plans
              get built on it. FAILs past the threshold.

A `decays: state` doc with no `verified-against` stamp is a hard FAIL regardless of age —
that is the unstamped case that caused this whole sprint (a roadmap fourteen versions
stale, on no checklist, asserting gaps the code had long since closed).

The commit-trailer family this joins: `Konjo-Acknowledged-Oneway` (lib/oneway.py) and
`Konjo-Prove-Merge` (lib/prove.py) are both record-and-check trailers built on
`oneway.make_trailer`/`oneway.find_trailer`. `Konjo-Doc-Verified` is the sibling for a
sprint that re-verified its `decays: state` docs, keyed on the same
`oneway.fingerprint(paths)` used elsewhere — one fingerprint scheme, not four.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from lib import oneway

DOC_VERIFIED_TRAILER = "Konjo-Doc-Verified"

STATE = "state"
REFERENCE = "reference"
INTENT = "intent"
HISTORICAL = "historical"
_VALID_DECAYS = {STATE, REFERENCE, INTENT, HISTORICAL}

# A sprint-ish cadence: past either bound, a `state` doc's claim is presumed stale. A
# profile may override both via check_document's/scan_repo's kwargs.
DEFAULT_STALE_COMMITS = 20
DEFAULT_STALE_DAYS = 14

OK = "OK"
WARN = "WARN"
FAIL = "FAIL"
SKIP = "SKIP"  # no decays: front matter (or no recognized value); the doc hasn't opted in.

_FRONT_MATTER = re.compile(r"\A---[ \t]*\n(.*?\n)---[ \t]*\n?", re.DOTALL)
_DATE_LINE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "target", "dist", "build"}


@dataclass
class DocCheck:
    """One document's verdict. `reason` is human-readable; the rest is the evidence."""

    path: str
    verdict: str  # OK | WARN | FAIL | SKIP
    reason: str
    decays: str | None = None
    verified_against: str | None = None
    verified_date: str | None = None
    commits_behind: int | None = None
    days_behind: int | None = None

    @property
    def is_fail(self) -> bool:
        return self.verdict == FAIL


def parse_front_matter(text: str) -> tuple[dict[str, object] | None, str]:
    """Split a leading YAML front-matter block from the body.

    Returns (None, text) if the doc has no `---` block at all — that is the "no front
    matter" case the checker must report, not crash on. Returns ({}, body) if the block
    exists but fails to parse as YAML or isn't a mapping, for the same reason.
    """
    m = _FRONT_MATTER.match(text)
    if not m:
        return None, text
    body = text[m.end() :]
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}, body
    return (data if isinstance(data, dict) else {}), body


def _commits_behind(repo_root: Path, sha: str) -> int | None:
    """Commits between sha and HEAD, or None if sha can't be resolved in this history."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-list", "--count", f"{sha}..HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    try:
        return int(out.stdout.strip())
    except ValueError:
        return None


def _days_behind(verified_date: str, today: date) -> int | None:
    try:
        stamped = datetime.strptime(verified_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (today - stamped).days


def _has_dated_banner(body: str) -> bool:
    """A visible date near the top of the body: the baseline-SHA-and-date banner a
    historical snapshot should carry so a reader can see how old it is without `git log`."""
    head = "\n".join(body.splitlines()[:20])
    return bool(_DATE_LINE.search(head))


def check_document(
    path: Path,
    *,
    repo_root: Path,
    today: date | None = None,
    stale_commits: int = DEFAULT_STALE_COMMITS,
    stale_days: int = DEFAULT_STALE_DAYS,
) -> DocCheck:
    """Check one document's `decays:` claim against HEAD. Never raises on a malformed doc."""
    if path.is_absolute():
        try:
            rel = str(path.relative_to(repo_root))
        except ValueError:
            rel = str(path)
    else:
        rel = str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return DocCheck(rel, FAIL, f"unreadable: {exc}")

    fm, body = parse_front_matter(text)
    if fm is None:
        return DocCheck(rel, SKIP, "no decays: front matter; convention not adopted")
    return _evaluate_decay(
        rel, fm, body, repo_root=repo_root, today=today,
        stale_commits=stale_commits, stale_days=stale_days,
    )


def _evaluate_decay(
    rel: str,
    fm: dict[str, object],
    body: str,
    *,
    repo_root: Path,
    today: date | None = None,
    stale_commits: int = DEFAULT_STALE_COMMITS,
    stale_days: int = DEFAULT_STALE_DAYS,
) -> DocCheck:
    """The staleness verdict shared by whole-document and per-section checks.

    Both `check_document` and `check_sections` parse a `decays:` block from a different
    scope (a whole file's leading front matter vs. one `## Heading`'s trailing HTML
    comment) and then apply the exact same four-class staleness rule -- extracted here so
    a stale crate map inside CLAUDE.md decays by the identical clock as a stale whole doc.
    """
    decays_raw = fm.get("decays")
    if not isinstance(decays_raw, str) or decays_raw not in _VALID_DECAYS:
        return DocCheck(rel, SKIP, f"no recognized decays: value ({decays_raw!r})")
    decays: str = decays_raw

    verified_against = fm.get("verified-against")
    verified_date = fm.get("verified-date")
    verified_against = str(verified_against) if verified_against is not None else None
    verified_date = str(verified_date) if verified_date is not None else None
    today = today or datetime.now().date()

    if decays == HISTORICAL:
        if _has_dated_banner(body):
            return DocCheck(rel, OK, "historical: exempt, dated banner present",
                             decays, verified_against, verified_date)
        return DocCheck(
            rel, WARN, "historical doc lacks a dated banner near the top",
            decays, verified_against, verified_date,
        )

    if decays in (INTENT, REFERENCE):
        if not verified_against and not verified_date:
            return DocCheck(
                rel, WARN, f"{decays}: no verified-against stamp; long horizon, warn only",
                decays,
            )
        commits_behind = _commits_behind(repo_root, verified_against) if verified_against else None
        days_behind = _days_behind(verified_date, today) if verified_date else None
        return DocCheck(
            rel, WARN, f"{decays}: long horizon, informational only",
            decays, verified_against, verified_date, commits_behind, days_behind,
        )

    # decays == STATE
    if not verified_against and not verified_date:
        return DocCheck(
            rel, FAIL,
            "state doc has no verified-against stamp — the unstamped case that started this",
            decays,
        )

    commits_behind = _commits_behind(repo_root, verified_against) if verified_against else None
    if verified_against and commits_behind is None:
        return DocCheck(
            rel, FAIL, f"verified-against {verified_against!r} not found in this repo's history",
            decays, verified_against, verified_date,
        )

    days_behind = _days_behind(verified_date, today) if verified_date else None
    if verified_date and days_behind is None:
        return DocCheck(
            rel, FAIL, f"verified-date {verified_date!r} is not a valid YYYY-MM-DD date",
            decays, verified_against, verified_date,
        )

    over_commits = commits_behind is not None and commits_behind > stale_commits
    over_days = days_behind is not None and days_behind > stale_days
    if over_commits or over_days:
        return DocCheck(
            rel, FAIL,
            f"state doc is stale: {commits_behind} commits / {days_behind} days behind HEAD "
            f"(cap {stale_commits} commits / {stale_days} days)",
            decays, verified_against, verified_date, commits_behind, days_behind,
        )
    return DocCheck(
        rel, OK, "state doc verified within threshold",
        decays, verified_against, verified_date, commits_behind, days_behind,
    )


def scan_repo(
    repo_root: Path, *, glob: str = "**/*.md", **kwargs: object
) -> list[DocCheck]:
    """Check every markdown doc in a repo, skipping VCS/dependency directories."""
    results: list[DocCheck] = []
    for path in sorted(repo_root.glob(glob)):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        results.append(check_document(path, repo_root=repo_root, **kwargs))  # type: ignore[arg-type]
    return results


_H2 = re.compile(r"^##[ \t]+(.*)$", re.MULTILINE)
_SECTION_FRONT_MATTER = re.compile(r"\A\s*\n?<!--[ \t]*\n(.*?\n)-->[ \t]*\n?", re.DOTALL)


def parse_section_front_matter(text: str) -> list[tuple[str, dict[str, object] | None, str]]:
    """Find every `## Heading` immediately followed by a `<!-- decays: ... -->` block.

    A CLAUDE.md is one file with several claims of different half-lives in it -- a crate
    map decays like a `state` doc, a stack line barely decays at all. Per-file `decays:`
    front matter (the whole-document mechanism above) cannot express that; this is the
    section-scoped sibling. Returns (heading, front_matter_or_None, section_body) for
    every H2 in the document. `None` front matter means that section carries no stamp --
    the same "convention not adopted" default a whole unstamped doc gets, not an error.
    """
    headings = list(_H2.finditer(text))
    out: list[tuple[str, dict[str, object] | None, str]] = []
    for i, m in enumerate(headings):
        heading = m.group(1).strip()
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        section_text = text[start:end]
        fm_match = _SECTION_FRONT_MATTER.match(section_text)
        if not fm_match:
            out.append((heading, None, section_text))
            continue
        try:
            data = yaml.safe_load(fm_match.group(1))
        except yaml.YAMLError:
            data = {}
        body = section_text[fm_match.end() :]
        out.append((heading, data if isinstance(data, dict) else {}, body))
    return out


def check_sections(
    path: Path,
    *,
    repo_root: Path,
    today: date | None = None,
    stale_commits: int = DEFAULT_STALE_COMMITS,
    stale_days: int = DEFAULT_STALE_DAYS,
) -> list[DocCheck]:
    """Check every stamped `## Heading` section of one document (e.g. a repo's CLAUDE.md).

    Unstamped sections are silently skipped -- reported as SKIP the same as a whole
    unstamped document, not an error. A stamped section's `path` is rendered
    `<file>#<heading>` so a gate can name exactly which section went stale.
    """
    if path.is_absolute():
        try:
            rel = str(path.relative_to(repo_root))
        except ValueError:
            rel = str(path)
    else:
        rel = str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [DocCheck(rel, FAIL, f"unreadable: {exc}")]

    results: list[DocCheck] = []
    for heading, fm, body in parse_section_front_matter(text):
        section_rel = f"{rel}#{heading}"
        if fm is None:
            results.append(DocCheck(section_rel, SKIP, "no decays: front matter on this section"))
            continue
        results.append(
            _evaluate_decay(
                section_rel, fm, body, repo_root=repo_root, today=today,
                stale_commits=stale_commits, stale_days=stale_days,
            )
        )
    return results


def doc_verified_trailer(fp: str) -> str:
    """The commit trailer CI reads: `Konjo-Doc-Verified: <fingerprint>`.

    Shares `oneway.make_trailer` with the other record-and-check trailers rather than
    inventing a fourth format. Callers key `fp` on `oneway.fingerprint(doc_paths)` over
    the docs re-verified this sprint, the same fingerprint scheme used everywhere else.
    """
    return oneway.make_trailer(DOC_VERIFIED_TRAILER, fp)


def find_doc_verified(messages: str, fp: str) -> bool:
    """True if a commit carries the Konjo-Doc-Verified trailer for this fingerprint."""
    return oneway.find_trailer(messages, DOC_VERIFIED_TRAILER, fp)
