"""konjo-gates: the CI-plane gate orchestrator.

Reads a repo profile, routes changed files through diff_scope, and runs the kiban-native
gates (prose, secrets, the self_test replay eval, report-only specialist stats) plus the
profile's repo-native gates (each wrapped in konjo-newonly so only net-new findings
block). Exits nonzero if any gate reports a regression.

Single source of truth: this orchestrator imports the real lib/ and evals/ engine. It
reimplements no review, redact, prose, or diff_scope logic. The CI plane never reads
~/.konjo.

Usage:
  konjo-gates --profile .konjo/profile.yml [--base origin/main]
              [--changed FILE ...] [--mode daily|deep] [--no-self-test]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


def _ensure_engine_on_path() -> Path:
    """Make the kiban engine importable whether installed or run from a checkout.

    When installed via the root distribution, lib/ and evals/ import normally. When run
    from a source checkout (the kill-test path), add the repo root to sys.path. Returns
    the kiban root for locating bin/konjo-newonly and the cassettes.
    """
    here = Path(__file__).resolve()
    # packages/konjo-gates-py/src/konjo_gates_py/cli.py -> repo root is parents[4]
    root = here.parents[4]
    try:
        import lib.review  # noqa: F401
    except ModuleNotFoundError:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
    return root


KIBAN_ROOT = _ensure_engine_on_path()

import yaml  # type: ignore[import-untyped]  # noqa: E402

from evals import cassettes, runner  # noqa: E402
from lib import (  # noqa: E402
    diff_scope,
    oneway,
    prose_lint,
    redact,
    review_log,
    specialist_stats,
    unsafe_budget,
)

PASS, FAIL, WARN, SKIP, ERROR = "PASS", "FAIL", "WARN", "SKIP", "ERROR"
_BLOCKING = {FAIL, ERROR}

# Which scope flag activates each repo-native tool, and how to invoke it. Tools absent
# from PATH but named in the profile are a clear ERROR (blocking), not a crash.
_TOOL_SCOPE = {
    "ruff": "SCOPE_PYTHON",
    "ruff-format": "SCOPE_PYTHON",
    "mypy": "SCOPE_PYTHON",
    "vulture": "SCOPE_PYTHON",
    "bandit": "SCOPE_PYTHON",
    "mutmut": "SCOPE_PYTHON",
    "radon": "SCOPE_PYTHON",
    "interrogate": "SCOPE_PYTHON",
    "clippy": "SCOPE_RUST",
    "fmt-check": "SCOPE_RUST",
    "cargo-deny": "SCOPE_RUST",
    "cargo-mutants": "SCOPE_RUST",
    "unsafe-budget": "SCOPE_RUST",
}
_TOOL_BIN = {
    "ruff-format": "ruff",
    "clippy": "cargo",
    "fmt-check": "cargo",
    "cargo-deny": "cargo",
    "cargo-mutants": "cargo",
}

# kiban-native gates handled in-process, not as a PATH binary through konjo-newonly.
_NATIVE_TOOLS = {"unsafe-budget"}


@dataclass
class GateResult:
    name: str
    status: str
    detail: str = ""

    @property
    def blocking(self) -> bool:
        return self.status in _BLOCKING


def _git(args: list[str]) -> str:
    proc = subprocess.run(["git", *args], capture_output=True, text=True)
    return proc.stdout


def _changed_files(base: str, explicit: list[str]) -> list[str]:
    if explicit:
        return explicit
    names: list[str] = []
    for cmd in (
        ["diff", "--name-only", f"{base}...HEAD"],
        ["diff", "--name-only", "HEAD"],
        ["diff", "--name-only", "--cached"],
    ):
        names.extend(line for line in _git(cmd).splitlines() if line.strip())
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _diff_text(base: str) -> str:
    return _git(["diff", f"{base}...HEAD"]) + _git(["diff", "HEAD"])


def _base_file(base: str, path: str) -> str:
    proc = subprocess.run(["git", "show", f"{base}:{path}"], capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else ""


def _is_doc(path: str) -> bool:
    return path.lower().endswith((".md", ".markdown", ".rst", ".txt"))


def _is_article(path: str, article_globs: list[str]) -> bool:
    low = path.lower()
    if any(seg in low for seg in ("article", "blog", "/posts/")):
        return True
    return any(Path(path).match(g) for g in article_globs)


# --------------------------------------------------------------------------- gates


def gate_prose(changed: list[str], base: str, article_globs: list[str]) -> GateResult:
    """Net-new prose findings. Blocking in article scope, warn elsewhere."""
    docs = [p for p in changed if _is_doc(p)]
    if not docs:
        return GateResult("prose", SKIP, "no changed docs")

    article_hits: list[str] = []
    general_hits: list[str] = []
    for path in docs:
        if not Path(path).exists():
            continue
        head = {(f.rule, f.token) for f in prose_lint.lint_file(path)}
        base_txt = _base_file(base, path)
        base_set = {(f.rule, f.token) for f in prose_lint.lint_text(base_txt, path)}
        net_new = head - base_set
        if not net_new:
            continue
        rendered = ", ".join(f"{rule}:{tok!r}" for rule, tok in sorted(net_new))
        if _is_article(path, article_globs):
            article_hits.append(f"{path} ({rendered})")
        else:
            general_hits.append(f"{path} ({rendered})")

    if article_hits:
        return GateResult("prose", FAIL, "net-new in article scope: " + "; ".join(article_hits))
    if general_hits:
        return GateResult("prose", WARN, "net-new in general docs: " + "; ".join(general_hits))
    return GateResult("prose", PASS, f"{len(docs)} doc(s) clean of net-new findings")


def gate_secrets(diff_text: str) -> GateResult:
    """HIGH secrets on added lines block. MEDIUM surfaces as a warn (Phase 3 confirm)."""
    findings = redact.scan_diff(diff_text)
    high = [f for f in findings if f.tier is redact.Tier.HIGH]
    medium = [f for f in findings if f.tier is redact.Tier.MEDIUM]
    if high:
        names = ", ".join(sorted({f.pattern_name for f in high}))
        return GateResult("secrets", FAIL, f"HIGH secret(s) on added lines: {names}")
    if medium:
        names = ", ".join(sorted({f.pattern_name for f in medium}))
        return GateResult("secrets", WARN, f"MEDIUM (confirm in phase 3): {names}")
    return GateResult("secrets", PASS, "no net-new secrets")


def gate_one_way_door(changed: list[str], diff_text: str, base: str) -> GateResult:
    """One-way doors need an acknowledgement trailer in the PR; never prompts.

    Two-way doors pass straight through. A one-way change is checked against the commit
    messages in base..HEAD for `Konjo-Acknowledged-Oneway: <fingerprint>`. Absent, the
    gate FAILs with guidance to run the interactive confirm (the session path). The gate
    reads git only, never stdin, so it is safe in CI.
    """
    cls = oneway.classify(changed, diff_text)
    if not cls.is_one_way:
        return GateResult("one_way_door", PASS, "two-way door")
    fp = oneway.fingerprint(changed)
    messages = _git(["log", f"{base}..HEAD", "--format=%B"])
    if oneway.find_ack(messages, fp):
        return GateResult("one_way_door", PASS, f"acknowledged ({', '.join(cls.reasons)})")
    return GateResult(
        "one_way_door",
        FAIL,
        f"one-way door ({', '.join(cls.reasons)}); change id {fp}. Run "
        f"`konjo-oneway confirm --files ...` and add the trailer "
        f"'{oneway.ack_trailer(fp)}' to a commit",
    )


def gate_prove(changed: list[str], flags: dict[str, bool], profile: dict, base: str) -> GateResult:
    """Perf changes need a recorded MERGE verdict; this gate never runs the benchmark.

    It applies only to a perf-labeled change (SCOPE_BENCH, or a profile-declared perf
    path). For such a change it checks the commit messages in base..HEAD for the prove
    MERGE trailer, reusing the one-way record-and-check path. No MERGE record -> FAIL with
    guidance to run konjo-prove on the bench hardware. The gate imports no stats and runs
    no benchmark, so the CI runner stays clean.
    """
    perf_globs = list(profile.get("prove", {}).get("perf_globs", []))
    is_perf = flags.get("SCOPE_BENCH", False) or any(
        any(Path(c).match(g) for g in perf_globs) for c in changed
    )
    if not is_perf:
        return GateResult("prove", SKIP, "not a perf change")
    fp = oneway.fingerprint(changed)
    messages = _git(["log", f"{base}..HEAD", "--format=%B"])
    if oneway.find_trailer(messages, oneway.PROVE_MERGE_TRAILER, fp):
        return GateResult("prove", PASS, f"MERGE verdict recorded (change id {fp})")
    return GateResult(
        "prove",
        FAIL,
        f"perf change with no MERGE verdict (change id {fp}). Run "
        f"`konjo-prove run --results <artifact> --profile <profile>` on the bench "
        f"hardware and add the 'Konjo-Prove-Merge: {fp}' trailer to a commit",
    )


def gate_self_test(profile_path: str, mode: str) -> GateResult:
    """Run the meta-gate eval through the deterministic replay backend (no model)."""
    if not cassettes.cassettes_present():
        return GateResult("self_test", SKIP, "no cassettes recorded; run konjo-eval record")
    backend = cassettes.ReplayBackend(cassettes.load_cassettes())
    try:
        report = runner.run(profile_path, runs=runner.DEFAULT_RUNS, backend=backend, mode=mode)
    except cassettes.CassetteMiss as exc:
        return GateResult("self_test", ERROR, f"stale cassette: {exc}")
    s = report["summary"]
    if report["ok"]:
        return GateResult(
            "self_test", PASS,
            f"{s['n_must_flag']} must-flag, {s['n_controls']} control(s), runs={report['runs']}",
        )
    detail = []
    if s["missed_bugs"]:
        detail.append("missed: " + ", ".join(s["missed_bugs"]))
    if s["false_positive_controls"]:
        detail.append("controls fired: " + ", ".join(s["false_positive_controls"]))
    return GateResult("self_test", FAIL, "; ".join(detail))


def gate_specialist_stats() -> GateResult:
    """Report-only: print the per-specialist table. Never blocks."""
    try:
        branch = _git(["rev-parse", "--abbrev-ref", "HEAD"]).strip() or "detached"
        log_path = review_log.log_path_for(branch)
        stats = specialist_stats.compute(log_path)
    except Exception:  # noqa: BLE001  report-only must never break the run
        return GateResult("specialist_stats", PASS, "no review history")
    if not stats:
        return GateResult("specialist_stats", PASS, "no review history yet")
    table = specialist_stats.format_table(stats)
    return GateResult("specialist_stats", PASS, "\n" + table)


def _newonly_cmd(tool_argv: list[str], base: str) -> list[str]:
    newonly = str(KIBAN_ROOT / "bin" / "konjo-newonly")
    return [sys.executable, newonly, "--base", base, "--", *tool_argv]


def _tool_argv(tool: str, py_files: list[str]) -> list[str] | None:
    files = py_files or ["."]
    table: dict[str, list[str]] = {
        "ruff": ["ruff", "check", *files],
        "ruff-format": ["ruff", "format", "--check", *files],
        "mypy": ["mypy", *files],
        "vulture": ["vulture", *files],
        "bandit": ["bandit", "-q", "-r", *files],
        "radon": ["radon", "cc", "-s", *files],
        "interrogate": ["interrogate", "-q", *files],
        "mutmut": ["mutmut", "run"],
        # Rust tools operate on the whole crate; they take no file list. Each still runs
        # through konjo-newonly so only net-new findings block.
        "clippy": ["cargo", "clippy", "--", "-D", "warnings"],
        "fmt-check": ["cargo", "fmt", "--check"],
        "cargo-deny": ["cargo", "deny", "check"],
        "cargo-mutants": ["cargo", "mutants"],
    }
    return table.get(tool)


def gate_unsafe_budget(flags: dict[str, bool], diff_text: str) -> GateResult:
    """kiban-native: a net increase in `unsafe` blocks with no safety comment fails.

    Reads the diff only; never builds the crate. Skips a change with no Rust in scope.
    """
    if not flags.get("SCOPE_RUST"):
        return GateResult("repo:unsafe-budget", SKIP, "SCOPE_RUST not in this change")
    budget = unsafe_budget.scan(diff_text)
    if budget.fails:
        return GateResult(
            "repo:unsafe-budget",
            FAIL,
            f"net +{budget.net} unsafe block(s) without a safety comment "
            f"(added unjustified {budget.added_unjustified}, removed {budget.removed}); "
            f"add a `// SAFETY:` comment or remove the unsafe",
        )
    return GateResult(
        "repo:unsafe-budget",
        PASS,
        f"no net-new unjustified unsafe (added unjustified {budget.added_unjustified}, "
        f"removed {budget.removed})",
    )


def gate_repo_native(
    tool: str, flags: dict[str, bool], changed: list[str], base: str
) -> GateResult:
    scope = _TOOL_SCOPE.get(tool)
    if scope is None:
        return GateResult(f"repo:{tool}", WARN, "no runner mapping; skipped")
    if not flags.get(scope):
        return GateResult(f"repo:{tool}", SKIP, f"{scope} not in this change")
    binary = _TOOL_BIN.get(tool, tool)
    if shutil.which(binary) is None:
        return GateResult(
            f"repo:{tool}", ERROR, f"tool {binary!r} named in profile is not installed"
        )
    argv = _tool_argv(tool, [c for c in changed if c.endswith(".py")])
    if argv is None:
        return GateResult(f"repo:{tool}", WARN, "no runner mapping; skipped")
    proc = subprocess.run(_newonly_cmd(argv, base), capture_output=True, text=True)
    if proc.returncode == 0:
        return GateResult(f"repo:{tool}", PASS, "no net-new findings")
    last = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "net-new findings"
    return GateResult(f"repo:{tool}", FAIL, last)


# --------------------------------------------------------------------------- driver


def run_gates(
    profile: dict,
    profile_path: str,
    *,
    base: str,
    changed: list[str],
    diff_text: str,
    mode: str,
    self_test: bool,
) -> list[GateResult]:
    flags = diff_scope.scope(changed, diff_text)
    article_globs = list(profile.get("prose_article_globs", []))

    results: list[GateResult] = [
        gate_prose(changed, base, article_globs),
        gate_secrets(diff_text),
        gate_one_way_door(changed, diff_text, base),
        gate_prove(changed, flags, profile, base),
    ]
    if self_test:
        results.append(gate_self_test(profile_path, mode))
    results.append(gate_specialist_stats())

    repo_tools = list(profile.get("format_lint", [])) + list(profile.get("contract_gates", []))
    mutation = profile.get("mutation", "")
    if isinstance(mutation, str) and mutation and not mutation.startswith("none"):
        repo_tools.append(mutation)
    for tool in repo_tools:
        if tool not in _TOOL_SCOPE:
            continue
        if tool in _NATIVE_TOOLS:
            if tool == "unsafe-budget":
                results.append(gate_unsafe_budget(flags, diff_text))
            continue
        results.append(gate_repo_native(tool, flags, changed, base))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(prog="konjo-gates")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--changed", nargs="*", default=[])
    parser.add_argument("--mode", default="daily", choices=["daily", "deep"])
    parser.add_argument("--no-self-test", action="store_true")
    args = parser.parse_args()

    with open(args.profile, encoding="utf-8") as fh:
        profile = yaml.safe_load(fh) or {}

    changed = _changed_files(args.base, args.changed)
    diff_text = _diff_text(args.base)

    results = run_gates(
        profile,
        args.profile,
        base=args.base,
        changed=changed,
        diff_text=diff_text,
        mode=args.mode,
        self_test=not args.no_self_test,
    )

    print(f"konjo-gates: {len(changed)} changed file(s), base {args.base}")
    blocking = 0
    for r in results:
        print(f"  [{r.status:<5}] {r.name}: {r.detail}")
        if r.blocking:
            blocking += 1

    if blocking:
        print(f"konjo-gates: BLOCKED ({blocking} gate(s) failed)")
        return 1
    print("konjo-gates: all gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
