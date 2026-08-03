"""kiban bench: one-shot baseline measurement, per repo.

Phase 0 of the review-pipeline plan needs falsifiable numbers before any gate, critic, or
router gets built. This module is the measurement side: given a target repo, it runs
coverage, mutation, test, and build-timing tools that are *already the repo's own*
(lopi's `cargo llvm-cov nextest` + `cargo mutants`, squish's `pytest --cov` + `mutmut`) and
records what they report. It does not introduce a new coverage tool (no tarpaulin: neither
target repo uses it, and lopi's own CI already standardized on cargo-llvm-cov -- see
LEDGER.md "Bench-Coverage-Tool-1").

Two outputs per run:
  1. A dated JSON artifact under a results directory (the full detail, one file per run).
  2. A compact record appended to `bench/<repo>-bench.jsonl` on the jsonl_store substrate
     (the same injection-reject/secret-scan substrate the Decision Ledger uses -- see
     `lib/review_log.py` for the precedent of a non-Decision event stream on that
     substrate). This is not a Decision Ledger event: a bench run is a measurement, not a
     durable call, so it does not go through `Ledger.decide()`.

Mutation scope here is deliberately full-repo (`cargo mutants --workspace` / `mutmut run`
with no diff restriction), unlike the diff-scoped `cargo-mutants --in-diff` gate already
wired into lopi's own CI (`.github/workflows/konjo-gate.yml` G3) and into
`konjo_gates_py.cli`'s per-PR dispatcher. Those two are a different measurement
(per-PR, changed-lines-only); this is the standing baseline they don't produce.
"""

from __future__ import annotations

import json
import os
import platform
import re
import signal
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lib import jsonl_store

RESULTS_DIR = Path("bench_results")


class BenchError(Exception):
    """A step could not run at all (missing tool, repo not found, etc.)."""


def _run(cmd: list[str], cwd: Path, timeout: int | None = None) -> tuple[int, str, float]:
    """Run a command, returning (exit_code, combined_output, wall_seconds).

    Never raises on a nonzero exit or on timeout -- a failed/timed-out tool run is still a
    measurement (e.g. "coverage tool errored"), not a bench-harness bug. Runs in its own
    process group (`start_new_session=True`) and, on timeout, kills the whole group, not
    just the direct child: `mutmut run` (and `cargo mutants`) fan out worker subprocesses
    that plain `subprocess.run(..., timeout=...)` leaves orphaned and still burning CPU
    after this function returns -- confirmed live (a killed `mutmut run` trial left two
    ~1.8GB worker processes running until manually `pkill`ed). A timed-out run is reported
    as a nonzero synthetic exit code (124, matching the shell convention).
    """
    start = time.monotonic()
    proc = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
        elapsed = time.monotonic() - start
        return proc.returncode, out or "", elapsed
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, _ = proc.communicate()
        elapsed = time.monotonic() - start
        return 124, out or "", elapsed
    except FileNotFoundError as exc:
        elapsed = time.monotonic() - start
        return 127, f"tool not found: {exc}", elapsed


def _git_sha(repo: Path) -> str:
    code, out, _ = _run(["git", "rev-parse", "HEAD"], repo)
    return out.strip() if code == 0 else "unknown"


def _repo_kind(repo: Path) -> str:
    """Detect 'rust' or 'python' from what's actually at the repo root.

    Prefers the repo's own `.konjo/profile.yml` `stack:` declaration when present (the
    single source of truth kiban already uses for this repo); falls back to file presence
    so bench also works against a repo that has not adopted a kiban profile yet.
    """
    profile = repo / ".konjo" / "profile.yml"
    if profile.exists():
        import yaml  # type: ignore[import-untyped]

        try:
            data = yaml.safe_load(profile.read_text(encoding="utf-8")) or {}
            stack = data.get("stack", [])
            if "rust" in stack:
                return "rust"
            if "python" in stack:
                return "python"
        except Exception:  # noqa: BLE001  a malformed profile falls through to file-sniff
            pass
    if (repo / "Cargo.toml").exists():
        return "rust"
    if (repo / "pyproject.toml").exists() or (repo / "setup.py").exists():
        return "python"
    raise BenchError(f"cannot detect repo kind for {repo}: no Cargo.toml or pyproject.toml")


@dataclass
class ToolVersions:
    rustc: str | None = None
    cargo: str | None = None
    python: str | None = None
    os: str = field(default_factory=platform.platform)


@dataclass
class BenchResult:
    repo: str
    repo_kind: str
    sha: str
    started_at: str
    finished_at: str | None = None
    tool_versions: dict[str, Any] = field(default_factory=dict)
    clean_build_wall_s: float | None = None
    clean_build_ok: bool | None = None
    test_count: int | None = None
    test_wall_s: float | None = None
    tests_ok: bool | None = None
    coverage_line_pct: float | None = None
    coverage_lines_found: int | None = None
    coverage_lines_hit: int | None = None
    coverage_tool: str | None = None
    coverage_notes: str | None = None
    mutation_score_pct: float | None = None
    mutation_caught: int | None = None
    mutation_missed: int | None = None
    mutation_unviable: int | None = None
    mutation_timeout: int | None = None
    mutation_wall_s: float | None = None
    mutation_per_crate: dict[str, Any] | None = None
    mutation_tool: str | None = None
    mutation_notes: str | None = None
    errors: list[str] = field(default_factory=list)


def _tool_versions_rust(repo: Path) -> dict[str, Any]:
    _, rustc_out, _ = _run(["rustc", "--version"], repo)
    _, cargo_out, _ = _run(["cargo", "--version"], repo)
    return {"rustc": rustc_out.strip(), "cargo": cargo_out.strip(), "os": platform.platform()}


def _tool_versions_python(repo: Path) -> dict[str, Any]:
    _, py_out, _ = _run(["python3", "--version"], repo)
    return {"python": py_out.strip(), "os": platform.platform()}


def _clean_build_rust(repo: Path, result: BenchResult) -> None:
    code, out, elapsed = _run(["cargo", "build", "--workspace"], repo, timeout=1800)
    result.clean_build_wall_s = round(elapsed, 2)
    result.clean_build_ok = code == 0
    if code != 0:
        result.errors.append(f"cargo build --workspace failed (exit {code}): {out[-500:]}")


_NEXTEST_SUMMARY_RE = re.compile(
    r"Summary\s*\[\s*[\d.]+s\]\s*(\d+)\s+tests? run"
)


def _tests_rust(repo: Path, result: BenchResult) -> None:
    code, out, elapsed = _run(
        ["cargo", "nextest", "run", "--workspace"], repo, timeout=1800
    )
    if code == 127:
        # nextest not installed: fall back to the repo's own declared verify_cmd
        # (`cargo test --workspace` per lopi's CLAUDE.md) so this step still produces a
        # real number instead of a silent null.
        code, out, elapsed = _run(["cargo", "test", "--workspace"], repo, timeout=1800)
        m = re.findall(r"(\d+) passed", out)
        result.test_count = sum(int(x) for x in m) if m else None
    else:
        m = _NEXTEST_SUMMARY_RE.search(out)
        result.test_count = int(m.group(1)) if m else None
    result.test_wall_s = round(elapsed, 2)
    result.tests_ok = code == 0
    if code not in (0,):
        result.errors.append(f"test run exit {code} in {elapsed:.1f}s")


def _coverage_rust(repo: Path, result: BenchResult) -> None:
    """cargo-llvm-cov nextest --lcov, matching lopi's own G2 CI step exactly.

    Deliberately not tarpaulin: lopi's CI already standardized on llvm-cov, and
    introducing a second coverage tool here would produce a number that disagrees with
    the one the coverage-floor gate enforces, for no benefit.
    """
    lcov_path = repo / "lcov.bench.info"
    code, out, elapsed = _run(
        [
            "cargo", "llvm-cov", "nextest", "--workspace", "--all-features",
            "--lcov", "--output-path", str(lcov_path),
        ],
        repo,
        timeout=1800,
    )
    result.coverage_tool = "cargo-llvm-cov"
    if code == 127:
        result.coverage_notes = "cargo-llvm-cov not installed"
        result.errors.append("coverage skipped: cargo-llvm-cov not installed")
        return
    if not lcov_path.exists():
        result.coverage_notes = f"lcov output not produced (exit {code})"
        result.errors.append(f"coverage tool exit {code}, no lcov.info: {out[-300:]}")
        return
    lf = lh = 0
    for line in lcov_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("LF:"):
            lf += int(line.split(":", 1)[1])
        elif line.startswith("LH:"):
            lh += int(line.split(":", 1)[1])
    lcov_path.unlink(missing_ok=True)
    result.coverage_lines_found = lf
    result.coverage_lines_hit = lh
    result.coverage_line_pct = round(100 * lh / lf, 2) if lf else None
    result.coverage_notes = (
        "line coverage only; branch coverage needs nightly + cargo-llvm-cov --branch, "
        "not attempted this run"
    )


_MUTANTS_SUMMARY_RE = re.compile(
    r"(\d+)\s+mutants?\s+tested\s+in\s+.*?:\s*(\d+)\s+missed,\s*(\d+)\s+caught"
    r"(?:,\s*(\d+)\s+unviable)?(?:,\s*(\d+)\s+timeout)?"
)


def _mutation_rust(repo: Path, result: BenchResult, timeout_s: int) -> None:
    """cargo mutants --workspace, full repo, no diff scoping. Per-crate breakdown from
    the per-mutant outcome file cargo-mutants writes under --output.
    """
    out_dir = repo / ".cargo-mutants-bench"
    code, out, elapsed = _run(
        [
            "cargo", "mutants", "--workspace", "--jobs", "2",
            "--output", str(out_dir),
        ],
        repo,
        timeout=timeout_s,
    )
    result.mutation_tool = "cargo-mutants"
    result.mutation_wall_s = round(elapsed, 2)
    if code == 127:
        result.mutation_notes = "cargo-mutants not installed"
        result.errors.append("mutation skipped: cargo-mutants not installed")
        return
    if code == 124:
        result.mutation_notes = f"timed out after {timeout_s}s, partial results only"
        result.errors.append(
            f"mutation run hit the {timeout_s}s time-box; scored from partial output"
        )

    m = _MUTANTS_SUMMARY_RE.search(out)
    caught = missed = unviable = timeout_n = None
    if m:
        missed = int(m.group(2))
        caught = int(m.group(3))
        unviable = int(m.group(4)) if m.group(4) else 0
        timeout_n = int(m.group(5)) if m.group(5) else 0
    else:
        # Summary line absent (timed out mid-run, or format drift) -- fall back to
        # counting the per-outcome text files cargo-mutants writes incrementally.
        def _count(name: str) -> int:
            p = out_dir / "mutants.out" / name
            if not p.exists():
                return 0
            return len([ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()])

        caught = _count("caught.txt")
        missed = _count("missed.txt")
        unviable = _count("unviable.txt")
        timeout_n = _count("timeout.txt")

    result.mutation_caught = caught
    result.mutation_missed = missed
    result.mutation_unviable = unviable
    result.mutation_timeout = timeout_n
    tested = (caught or 0) + (missed or 0)
    result.mutation_score_pct = round(100 * caught / tested, 2) if tested else None

    per_crate: dict[str, dict[str, int]] = {}
    outcomes_json = out_dir / "mutants.out" / "outcomes.json"
    if outcomes_json.exists():
        try:
            data = json.loads(outcomes_json.read_text(encoding="utf-8"))
            for o in data.get("outcomes", []):
                fname = o.get("scenario", {}).get("Mutant", {}).get("file", "unknown")
                crate = fname.split("/")[0] if "/" in fname else fname
                bucket = per_crate.setdefault(crate, {"caught": 0, "missed": 0, "unviable": 0})
                summary = o.get("summary", "").lower()
                if "caught" in summary:
                    bucket["caught"] += 1
                elif "missed" in summary:
                    bucket["missed"] += 1
                elif "unviable" in summary:
                    bucket["unviable"] += 1
        except Exception as exc:  # noqa: BLE001  per-crate breakdown is best-effort
            result.errors.append(f"per-crate mutation breakdown unavailable: {exc}")
    result.mutation_per_crate = per_crate or None


_PROGRESS_LINE_RE = re.compile(r"^[.FEsxX]+\s*\[\s*\d{1,3}%\]$")
_PRECISE_COVERAGE_RE = re.compile(r"[Tt]otal coverage:\s*([\d.]+)%")
_TOTAL_ROW_RE = re.compile(r"^TOTAL\s+(?:\d+\s+)+?(\d+)%\s*$", re.MULTILINE)


def _count_test_outcomes(out: str) -> int | None:
    """Count tests run from pytest's `-q` dot-progress lines (e.g. `....F..ss [ 12%]`).

    Not the `"N passed"` summary line: a repo with `--cov-fail-under` configured (squish
    does, at 100%) makes pytest-cov call `pytest.exit()` on a coverage-threshold miss,
    which skips the normal terminal summary entirely -- confirmed live, not assumed
    (`squish`'s bench run produced zero "passed"/"failed" line while still running its
    full suite). Progress-character counting works regardless of whether that summary
    line exists.
    """
    total = 0
    seen_any = False
    for line in out.splitlines():
        if _PROGRESS_LINE_RE.match(line.strip()):
            seen_any = True
            total += sum(1 for c in line if c in ".FEsxX")
    return total if seen_any else None


def _tests_and_coverage_python(repo: Path, result: BenchResult) -> None:
    """One pytest invocation for both test count/wall-clock and coverage -- running the
    full suite twice (once plain, once with --cov) was pure waste, and both numbers come
    from the same run's output anyway.
    """
    code, out, elapsed = _run(
        ["python3", "-m", "pytest", "-q", "--cov", "--cov-report=term"], repo, timeout=1800
    )
    result.test_wall_s = round(elapsed, 2)
    result.tests_ok = code == 0
    result.test_count = _count_test_outcomes(out)
    if code not in (0, 1):  # pytest exits 1 for "tests failed", still a real count
        result.errors.append(f"pytest exit {code} in {elapsed:.1f}s")

    result.coverage_tool = "pytest-cov"
    if code == 127 or "unrecognized arguments" in out or "unknown option" in out.lower():
        result.coverage_notes = "pytest-cov not installed/configured"
        result.errors.append("coverage skipped: pytest-cov not available")
        return
    # Prefer the precise "Total coverage: XX.XX%" line pytest-cov prints on a
    # --cov-fail-under check; fall back to the TOTAL row's rounded integer percentage
    # (format varies by whether branch coverage is enabled -- squish's TOTAL row has
    # statements/missed/branch/partial-branch columns before the percentage, so the
    # column count before "%" cannot be assumed fixed).
    m = _PRECISE_COVERAGE_RE.search(out)
    if m:
        result.coverage_line_pct = float(m.group(1))
        return
    m = _TOTAL_ROW_RE.search(out)
    if m:
        result.coverage_line_pct = float(m.group(1))
    else:
        result.coverage_notes = "could not parse pytest-cov TOTAL line"
        result.errors.append(f"coverage parse failed: {out[-300:]}")


def _mutation_python(repo: Path, result: BenchResult, timeout_s: int) -> None:
    result.mutation_tool = "mutmut"
    code, out, elapsed = _run(["python3", "-m", "mutmut", "run"], repo, timeout=timeout_s)
    result.mutation_wall_s = round(elapsed, 2)
    if code == 127:
        result.mutation_notes = "mutmut not installed"
        result.errors.append("mutation skipped: mutmut not installed")
        return
    if code == 124:
        result.mutation_notes = f"timed out after {timeout_s}s, partial results only"
        result.errors.append(
            f"mutation run hit the {timeout_s}s time-box; scored from partial output"
        )
    elif code != 0:
        # A real, non-timeout mutmut failure (e.g. its own baseline collection erroring)
        # -- record why, not just a silent None score. Confirmed live against squish:
        # `mutmut run` failed with `AttributeError: module 'squish.cli' has no attribute
        # 'build_parser'` even though the same import resolves fine in a plain
        # interpreter, consistent with mutmut's isolated source copy diverging from the
        # editable install's resolved path -- a real environment limitation, not
        # something to paper over as "0% mutation score."
        tail = out.strip().splitlines()[-1] if out.strip() else f"exit {code}, no output"
        result.mutation_notes = f"mutmut run failed (exit {code}): {tail}"
        result.errors.append(f"mutation run failed: {tail}")
        # A hard failure before any mutant ran means "not measured," not "measured,
        # zero" -- leave caught/missed as None (BenchResult's default) rather than the
        # 0/0 a completed-but-empty run would legitimately report.
        return
    code2, out2, _ = _run(["python3", "-m", "mutmut", "results"], repo, timeout=120)
    survived = len(re.findall(r"^\d+-\d+:\s*survived", out2, re.MULTILINE))
    killed = len(re.findall(r"^\d+-\d+:\s*killed", out2, re.MULTILINE))
    result.mutation_caught = killed
    result.mutation_missed = survived
    tested = killed + survived
    result.mutation_score_pct = round(100 * killed / tested, 2) if tested else None


def run_bench(repo: Path, *, mutation_timeout_s: int = 1800) -> BenchResult:
    """Run the full one-shot baseline against a single repo. Never raises for a tool
    failure -- failures land in `result.errors` so a partial bench artifact is always
    produced rather than nothing at all.
    """
    repo = repo.resolve()
    kind = _repo_kind(repo)
    result = BenchResult(
        repo=repo.name,
        repo_kind=kind,
        sha=_git_sha(repo),
        started_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    if kind == "rust":
        result.tool_versions = _tool_versions_rust(repo)
        _clean_build_rust(repo, result)
        _tests_rust(repo, result)
        _coverage_rust(repo, result)
        _mutation_rust(repo, result, mutation_timeout_s)
    elif kind == "python":
        result.tool_versions = _tool_versions_python(repo)
        result.clean_build_ok = None  # no compile step for a pure-Python repo
        _tests_and_coverage_python(repo, result)
        _mutation_python(repo, result, mutation_timeout_s)
    else:
        raise BenchError(f"unsupported repo kind: {kind}")
    result.finished_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return result


def write_artifact(result: BenchResult, out_dir: Path = RESULTS_DIR) -> Path:
    """Write the full-detail JSON artifact to a dated results directory."""
    date = result.started_at[:10]
    target = out_dir / result.repo / f"{date}-{result.sha[:12]}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")
    return target


def record_to_ledger(result: BenchResult, artifact_path: Path) -> str:
    """Append a compact record to `bench/<repo>-bench.jsonl` on the jsonl_store
    substrate. Not a Decision Ledger event (see module docstring) -- this is a
    measurement stream, mirroring `lib/review_log.py`'s precedent.
    """
    path = f"bench/{result.repo}-bench.jsonl"
    record = {
        "ts": result.finished_at or result.started_at,
        "repo": result.repo,
        "repo_kind": result.repo_kind,
        "sha": result.sha,
        "artifact": str(artifact_path),
        "tool_versions": result.tool_versions,
        "clean_build_wall_s": result.clean_build_wall_s,
        "test_count": result.test_count,
        "test_wall_s": result.test_wall_s,
        "coverage_line_pct": result.coverage_line_pct,
        "coverage_tool": result.coverage_tool,
        "mutation_score_pct": result.mutation_score_pct,
        "mutation_caught": result.mutation_caught,
        "mutation_missed": result.mutation_missed,
        "mutation_tool": result.mutation_tool,
        "mutation_wall_s": result.mutation_wall_s,
        "errors": result.errors,
    }
    jsonl_store.append(path, record)
    return path
