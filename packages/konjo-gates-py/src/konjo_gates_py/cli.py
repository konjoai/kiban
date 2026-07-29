"""konjo-gates: the CI-plane gate orchestrator.

Reads a repo profile, routes changed files through diff_scope, and runs the kiban-native
gates (prose, secrets, the self_test replay eval, report-only specialist stats) plus the
profile's repo-native gates (each wrapped in konjo-newonly so only net-new findings
block). Exits nonzero if any gate reports a regression.

Single source of truth: this orchestrator imports the real lib/ and evals/ engine. It
reimplements no review, redact, prose, or diff_scope logic. The CI plane never reads
~/.konjo.

Progress: a per-gate heartbeat (which gate is running, and each gate's elapsed time) is
always written to stderr, so a run is never silent -- an operator can see which gate is
eating the wall-clock instead of watching a job hang for minutes and fail with no clue.
`--verbose` (or KONJO_GATES_VERBOSE=1) adds per-scanner detail: the exact argv and each of
the two HEAD/base scan passes with its own duration.

Usage:
  konjo-gates --profile .konjo/profile.yml [--base origin/main]
              [--changed FILE ...] [--mode daily|deep] [--no-self-test] [--verbose]
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path


def _ensure_engine_on_path() -> Path:
    """Make the kiban engine importable whether installed or run from a checkout.

    When installed via the root distribution, lib/ and evals/ import normally. When run
    from a source checkout (the kill-test path), add the repo root to sys.path. Returns
    the kiban root for locating the always-on skills and the eval cassettes.
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
    claude_contract,
    context_budget,
    diff_scope,
    newonly,
    oneway,
    polarity,
    progress,
    prose_lint,
    redact,
    review_log,
    specialist_stats,
    threat,
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
    "cargo-audit": "SCOPE_RUST",
    "cargo-mutants": "SCOPE_RUST",
    "unsafe-budget": "SCOPE_RUST",
    "tsc": "SCOPE_TS",
    "eslint": "SCOPE_TS",
    "stryker": "SCOPE_TS",
    "npm-audit": "SCOPE_TS",
    "mojo-format": "SCOPE_MOJO",
    "mojo-test": "SCOPE_MOJO",
}
_TOOL_BIN = {
    "ruff-format": "ruff",
    "clippy": "cargo",
    "fmt-check": "cargo",
    "cargo-deny": "cargo",
    "cargo-audit": "cargo",
    "cargo-mutants": "cargo",
    "tsc": "npx",
    "eslint": "npx",
    "stryker": "npx",
    "npm-audit": "npm",
    "mojo-format": "mojo",
    "mojo-test": "mojo",
}

# Some tools live behind a subcommand of an already-installed binary (cargo-deny,
# cargo-mutants are `cargo` subcommands installed separately via `cargo install`).
# `shutil.which("cargo")` passing tells us nothing about whether the subcommand plugin
# is present, so probe it directly and report a distinct error rather than letting the
# gate run and misreport a missing plugin as "net-new findings".
_TOOL_PROBE = {
    "cargo-deny": ["cargo", "deny", "--version"],
    "cargo-audit": ["cargo", "audit", "--version"],
    "cargo-mutants": ["cargo", "mutants", "--version"],
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
    proc = subprocess.run(["git", *args], capture_output=True, text=True, errors="replace")
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
    proc = subprocess.run(
        ["git", "show", f"{base}:{path}"], capture_output=True, text=True, errors="replace"
    )
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


_DEFAULT_SECURITY_GLOBS = (
    "**/auth*", "**/api*", "**/server*", "**/webhook*", "**/*secret*", "**/*credential*",
)


def gate_threat_model(changed: list[str], diff_text: str, base: str, profile: dict) -> GateResult:
    """Phase 13, Phase 3: a security-glob change needs a recorded threat model.

    Same shape as `gate_one_way_door`/`gate_prove`: never prompts, never re-runs the
    brief-time classification (`konjo-threat classify`/`record` is the session-side
    half). Applies only to a change touching a `security_globs` path (profile-declared,
    default a generic auth/api/server/webhook/secret/credential set if the profile
    doesn't override it -- `diff_scope` has no fixed SCOPE_SECURITY flag the way
    `gate_prove` gets SCOPE_BENCH from `diff_scope`, since a trust boundary is a path
    concern, not a language/kind concern). No recorded trailer -> FAIL with guidance to
    run `konjo-threat record` at brief time.
    """
    globs = list(profile.get("security_globs", [])) or list(_DEFAULT_SECURITY_GLOBS)
    is_security = any(_glob_match(c, globs) for c in changed)
    if not is_security:
        return GateResult("threat_model", SKIP, "no security_globs path changed")
    fp = oneway.fingerprint(changed)
    messages = _git(["log", f"{base}..HEAD", "--format=%B"])
    if threat.find_threat_model(messages, fp):
        return GateResult("threat_model", PASS, f"threat model recorded (change id {fp})")
    return GateResult(
        "threat_model",
        FAIL,
        f"security-glob change with no recorded threat model (change id {fp}). Run "
        f"`konjo-threat classify --files ...` then `konjo-threat record --files ... "
        f"--boundary ... --mitigation ... --abuse-case ...` (repeat per boundary hit, or "
        f"pass none for 'no boundaries apply') and add the "
        f"'{threat.threat_trailer(fp)}' trailer to a commit",
    )


def _is_polarity_exempt(path: str, exempt_globs: list[str]) -> bool:
    return any(Path(path).match(g) for g in exempt_globs)


def gate_polarity(changed: list[str], base: str, profile: dict) -> GateResult:
    """K1, Family 0: does an unknown path return a passing value?

    Net-new findings only (added lines score against the base version of the same
    file), the way `gate_prose` already does -- pre-existing findings elsewhere in a
    touched file are debt, not a blocker for unrelated work. A finding is resolved one
    of three ways, in order: an explicit operator-override field in the returned
    expression (the `verifier_fail_open` precedent, `polarity.is_explicit_override`);
    the `Konjo-Polarity-Waived: <fp> — <reason>` trailer recorded against this exact
    changed-file set (`oneway.fingerprint`, same mechanism as the one-way-door
    acknowledgement and the prove MERGE record -- no second override channel); or
    nothing, which fails naming the file, line, condition, and returned value.

    `advisory: true` (the default for an existing repo adopting the gate) reports
    without blocking; `enabled: false` skips the gate entirely. `exempt_globs` names
    paths where the shape is legitimate by design.
    """
    cfg = profile.get("polarity", {}) or {}
    if not cfg.get("enabled", True):
        return GateResult("polarity", SKIP, "disabled (polarity.enabled: false)")
    exempt_globs = list(cfg.get("exempt_globs", []))
    # Ship-default is advisory (WARN, not FAIL) for a repo that has not opted in yet --
    # the coverage-floor ratchet pattern: adopt, clean the baseline, then set
    # `advisory: false` once clean. A profile with no `polarity:` block at all is exactly
    # that unopted-in case.
    advisory = bool(cfg.get("advisory", True))

    net_new: list[polarity.Finding] = []
    for path in changed:
        if _is_polarity_exempt(path, exempt_globs) or not Path(path).exists():
            continue
        head_findings = polarity.lint_file(path)
        if not head_findings:
            continue
        base_keys = {f.key() for f in polarity.lint_text(_base_file(base, path), path)}
        net_new.extend(f for f in head_findings if f.key() not in base_keys)

    if not net_new:
        return GateResult("polarity", PASS, "no net-new unknown-path-returns-permissive findings")

    fp = oneway.fingerprint(changed)
    messages = _git(["log", f"{base}..HEAD", "--format=%B"])
    waived = oneway.find_trailer(messages, oneway.POLARITY_WAIVED_TRAILER, fp)

    unresolved = [
        f for f in net_new
        if not polarity.is_explicit_override(f) and not waived
    ]
    if not unresolved:
        resolution = "waived on the record" if waived else "an explicit operator override"
        return GateResult(
            "polarity", PASS,
            f"{len(net_new)} finding(s), all resolved by {resolution} (change id {fp})",
        )

    rendered = "; ".join(f.format() for f in unresolved)
    detail = (
        f"{len(unresolved)} unknown-path-returns-permissive finding(s): {rendered}. "
        f"Fix the branch to return the restrictive value, name an explicit operator "
        f"override field, or add the trailer "
        f"'{oneway.make_trailer(oneway.POLARITY_WAIVED_TRAILER, fp)} — <reason>' to a commit"
    )
    return GateResult("polarity", WARN if advisory else FAIL, detail)


_RULES_FILE_RE = re.compile(r"^\.claude/rules/.*\.md$")


def gate_claude_contract(changed: list[str], profile: dict) -> GateResult:
    """Phase 13, Phase 1: the CLAUDE.md section contract, made permanent and org-wide.

    S13 Phase 0 audited lopi's self-claims in its root CLAUDE.md once, by hand. This gate
    makes that audit mechanical: any changed root `CLAUDE.md` is checked against the fixed
    section contract (org rules, stack, commands, invariants, repo map, repo-specific
    rules -- `lib.claude_contract.REQUIRED_SECTIONS`, in that order) and every bullet under
    an invariants/hard-rules heading must name the gate that enforces it or say ADVISORY --
    an unenforced "invariant" is a claim with no consumer. Any changed `.claude/rules/*.md`
    file is separately checked for the incident-log shape: a majority of lines carrying a
    sprint/date citation means the file records what broke, not what to check.

    Offline, no model, no network -- pure regex/heading parse over files already on disk.
    Ships advisory by default (WARN, not FAIL) so an adopting repo's non-conformant
    CLAUDE.md doesn't retroactively block unrelated work; `claude_contract.advisory: false`
    promotes it to blocking once a repo's CLAUDE.md has been brought into contract.
    """
    cfg = profile.get("claude_contract", {}) or {}
    if not cfg.get("enabled", True):
        return GateResult("claude_contract", SKIP, "disabled (claude_contract.enabled: false)")
    advisory = bool(cfg.get("advisory", True))

    claude_hits = [p for p in changed if Path(p).name == "CLAUDE.md"]
    rule_hits = [p for p in changed if _RULES_FILE_RE.match(p)]
    if not claude_hits and not rule_hits:
        return GateResult("claude_contract", SKIP, "no changed CLAUDE.md or rules file")

    problems: list[str] = []
    for path in claude_hits:
        if not Path(path).exists():
            continue
        text = Path(path).read_text(errors="replace")
        check = claude_contract.check_contract(text)
        if check.missing_sections:
            problems.append(f"{path}: missing section(s) {check.missing_sections}")
        if check.out_of_order:
            problems.append(f"{path}: sections out of order, expected {check.out_of_order}")
        if not check.has_org_import:
            problems.append(f"{path}: missing org import line (@~/.konjo/kiban/...)")
        if check.unenforced_bullets:
            rendered = "; ".join(check.unenforced_bullets[:5])
            problems.append(f"{path}: invariant bullet(s) name no enforcing gate: {rendered}")

    for path in rule_hits:
        if not Path(path).exists():
            continue
        text = Path(path).read_text(errors="replace")
        ratio = claude_contract.citation_ratio(text)
        if ratio > 0.5:
            problems.append(
                f"{path}: {ratio:.0%} of lines carry a sprint/date citation -- reads as "
                f"an incident log, not an invariant set; split into invariants (what to "
                f"check) and sinks (where it's enforced)"
            )

    if problems:
        return GateResult("claude_contract", WARN if advisory else FAIL, "; ".join(problems))
    n = len(claude_hits) + len(rule_hits)
    return GateResult("claude_contract", PASS, f"{n} file(s) contract-clean")


def gate_can_fail(profile: dict) -> GateResult:
    """K1, Family 0: every declared quality gate ships with a test that makes it reject.

    'A green run is not evidence a gate works. Only a red one is.' For each entry in the
    profile's `gates:` list, the named `rejects_test` command must exist AND pass --
    both checked the same way, by actually running it. This cannot verify the test's
    *content* is adversarial (that it exercises the hard input, not the easy one); it can
    only require that the rejecting test exists, is named, and is green. A profile with
    no `gates:` declared skips (Phase 3's KT-K1.3 finding: this gate has nothing to bind
    to until a repo enumerates its own gate set).
    """
    declared = profile.get("gates", []) or []
    if not declared:
        return GateResult("can_fail", SKIP, "no gates: declared in profile")

    missing = [
        g.get("name", "<unnamed>")
        for g in declared
        if not str(g.get("rejects_test", "")).strip()
    ]
    if missing:
        return GateResult(
            "can_fail", FAIL,
            f"gate(s) with no rejects_test declared: {', '.join(missing)}. Every quality "
            f"gate must name the test that proves it rejects a known-bad input",
        )

    failures: list[str] = []
    for g in declared:
        name = g.get("name", "<unnamed>")
        cmd = str(g["rejects_test"])
        try:
            argv = shlex.split(cmd)
        except ValueError as exc:
            failures.append(f"{name}: could not parse rejects_test {cmd!r} ({exc})")
            continue
        try:
            proc = subprocess.run(argv, capture_output=True, text=True)
        except OSError as exc:
            failures.append(f"{name}: rejects_test {cmd!r} does not exist ({exc})")
            continue
        if proc.returncode != 0:
            failures.append(f"{name}: rejects_test {cmd!r} did not pass (exit {proc.returncode})")

    if failures:
        return GateResult(
            "can_fail", FAIL,
            "; ".join(failures) + ". A green run is not evidence a gate works. Only a red one is.",
        )
    return GateResult("can_fail", PASS, f"{len(declared)} gate(s) each have a passing rejects_test")


_DEFAULT_LONGRUN_GLOBS = ("benchmarks/**", "**/bench_*.py", "scripts/train_*.py")

# A change to a long-run script must wire the resume contract. The gate checks the working
# file statically for both halves: a resume affordance and a checkpoint write.
_RESUME_RE = re.compile(r"--resume\b|konjo_longrun|add_resume_args")
_CHECKPOINT_RE = re.compile(r"\bCheckpoint\s*\(|\.mark\s*\(")


_MAIN_GUARD_RE = re.compile(r"if\s+__name__\s*==\s*['\"]__main__['\"]")


def _glob_match(path: str, globs: list[str]) -> bool:
    """fnmatch-based glob match, with `**` matching across directories and `**/` patterns
    also matching at the repo root (Path.match does not handle `**` recursively).

    Shared by every profile-glob-routed gate (`longrun_globs`, `security_globs`, ...) so
    the `**`-handling fnmatch logic exists in exactly one place."""
    base = path.rsplit("/", 1)[-1]
    for g in globs:
        if fnmatch.fnmatch(path, g):
            return True
        if "/" not in g and fnmatch.fnmatch(base, g):
            return True
        if g.startswith("**/") and fnmatch.fnmatch(base, g[3:]):
            return True
    return False


def _is_longrun_path(path: str, globs: list[str]) -> bool:
    return _glob_match(path, globs)


def _is_runnable_script(path: str, text: str) -> bool:
    """A glob can name a library that merely shares a benchmark's prefix (e.g. a bench
    adapter under lib/). Only treat a file as a long-run script if it is actually runnable:
    it has a __main__ guard, or it lives under a scripts directory (benchmarks/, scripts/).
    This keeps the gate off importable helpers that are not entry points."""
    if path.startswith(("benchmarks/", "scripts/")) or "/benchmarks/" in path:
        return True
    return bool(_MAIN_GUARD_RE.search(text))


def gate_longrun(changed: list[str], profile: dict) -> GateResult:
    """Long-run scripts must declare the resume contract; this gate never runs the script.

    For a change touching a `longrun_globs` path (default: benchmarks/**, **/bench_*.py,
    scripts/train_*.py) that is a runnable script (a __main__ guard, or under benchmarks/ or
    scripts/), it statically checks the working file for a resume affordance (a --resume flag
    or the konjo_longrun helper) AND a checkpoint write (a Checkpoint(...) or .mark(...)
    call). Missing either fails with guidance. A static check confirms the resume path
    exists, not that it is correct; correctness is the kill-test's job. The gate reads files
    only, never executes them, so the CI runner stays clean.
    """
    globs = list(profile.get("longrun_globs", [])) or list(_DEFAULT_LONGRUN_GLOBS)
    candidates = [p for p in changed if _is_longrun_path(p, globs) and p.endswith(".py")]

    offenders: list[str] = []
    n_scripts = 0
    for path in candidates:
        if not Path(path).exists():
            continue  # deleted file; nothing to enforce
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        if not _is_runnable_script(path, text):
            continue  # an importable library that merely shares the prefix, not a script
        n_scripts += 1
        missing = []
        if not _RESUME_RE.search(text):
            missing.append("--resume/--fresh (or the konjo_longrun helper)")
        if not _CHECKPOINT_RE.search(text):
            missing.append("a checkpoint write (Checkpoint(...) / .mark(...))")
        if missing:
            offenders.append(f"{path} (missing: {', '.join(missing)})")

    if not n_scripts:
        return GateResult("longrun", SKIP, "no changed long-run scripts")
    if offenders:
        return GateResult(
            "longrun",
            FAIL,
            "long-run script(s) lack the resume contract: "
            + "; ".join(offenders)
            + ". Adopt lib/packs/longrun/konjo_longrun (add_resume_args + Checkpoint)",
        )
    return GateResult("longrun", PASS, f"{n_scripts} long-run script(s) wire resume")


def gate_verify_cmd(profile: dict) -> GateResult:
    """Report-only: a repo should declare verify_cmd so the agent can verify its own work.

    The verify-loop (run the repo's own test/bench/browser path before claiming done) is the
    single highest-value habit, made a per-repo contract by the `verify_cmd` profile field. A
    repo with none is a surfaced gap, the way a missing prove threshold is, not a hard block:
    this gate warns, it never fails.
    """
    cmd = profile.get("verify_cmd")
    if isinstance(cmd, str) and cmd.strip() and not cmd.strip().upper().startswith(
        ("TODO", "UNVERIFIED")
    ):
        return GateResult("verify_cmd", PASS, f"declared: {cmd}")
    return GateResult(
        "verify_cmd",
        WARN,
        "no verify_cmd declared; the agent has no machine-checkable verify loop. Add "
        "verify_cmd to the profile (the test/bench/browser path that proves a change works)",
    )


def gate_context_budget(profile: dict) -> GateResult:
    """Report-only: the always-on context (the umbrella skill, ethos included) must stay under
    a token ceiling, so the framework cannot preach token-efficiency and then bloat its own
    preamble. Packs and the on-demand skills are never always-on, so they do not count.

    The token count is a model-free estimate (chars/4); the ceiling carries headroom. WARN
    over the ceiling, never a hard block until calibrated. The 1.0.0 cut requires this PASS on
    the core itself.
    """
    ceiling = int(profile.get("context_budget_tokens", context_budget.DEFAULT_BUDGET_TOKENS))
    used = context_budget.always_on_tokens(KIBAN_ROOT)
    if used <= ceiling:
        return GateResult("context_budget", PASS, f"always-on ~{used} tok <= {ceiling} ceiling")
    return GateResult(
        "context_budget",
        WARN,
        f"always-on ~{used} tok over the {ceiling} ceiling; trim the umbrella skill, or raise "
        "context_budget_tokens with a recorded reason",
    )


def gate_skill_size(profile: dict) -> GateResult:
    """Report-only: no single SKILL.md over a line cap without a recorded justification.

    The mechanical version of "if it could be 50 lines, rewrite it," applied to the
    framework's own prose. A skill that needs its length carries the `konjo-skill-size-ok:`
    marker (a one-way-door justification) and is exempt.
    """
    cap = int(profile.get("skill_line_cap", context_budget.DEFAULT_SKILL_LINE_CAP))
    offenders = context_budget.oversized_skills(KIBAN_ROOT, cap)
    if not offenders:
        return GateResult("skill_size", PASS, f"all skills within {cap} lines (or justified)")
    rendered = ", ".join(f"{p} ({n} lines)" for p, n in offenders)
    return GateResult(
        "skill_size",
        WARN,
        f"SKILL.md over {cap} lines with no justification: {rendered}. Trim it, or add a "
        f"'{context_budget.SKILL_SIZE_OVERRIDE} <reason>' line",
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
    if s.get("incomplete_fixtures"):
        detail.append(
            "incomplete (a specialist did not complete after retry -- fail-closed, not a "
            "verdict): " + ", ".join(s["incomplete_fixtures"])
        )
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


# cargo-mutants defaults. Mutation testing is the single most expensive gate: without
# `--in-diff` it mutates the *entire* crate (the ~20-minute silent CI block that motivated
# the progress heartbeat), and every surviving mutant then has to be re-derived twice by
# the HEAD/base net-new scan. `--in-diff` scopes mutation to the changed lines only -- this
# is what konjo-gate.yml's G3 gate (`cargo mutants --in-diff`) already does. `--jobs`
# parallelizes the surviving mutants across cores, and `--timeout` bounds each mutant's test
# run so a mutation that induces an infinite loop can't hang the gate forever. Both are
# overridable per-repo via env vars so a consuming repo can tune them in CI without a
# profile-schema change.
_MUTANTS_DEFAULT_JOBS = 4
_MUTANTS_DEFAULT_TIMEOUT = 120  # seconds allowed for a single mutant's test run


def _mutants_int(env_var: str, default: int) -> int:
    """A positive-int cargo-mutants tuning value from the environment, or the default."""
    raw = os.environ.get(env_var, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _tool_argv(
    tool: str, py_files: list[str], mutants_diff: str | None = None
) -> list[str] | None:
    files = py_files or ["."]
    if tool == "cargo-mutants":
        # `--in-diff <file>` restricts mutation to the changed lines (G3 parity); it is
        # omitted only when the caller could not produce a diff, in which case cargo-mutants
        # falls back to its whole-crate default.
        argv = ["cargo", "mutants"]
        if mutants_diff is not None:
            argv += ["--in-diff", mutants_diff]
        argv += [
            "--jobs", str(_mutants_int("KONJO_MUTANTS_JOBS", _MUTANTS_DEFAULT_JOBS)),
            "--timeout", str(_mutants_int("KONJO_MUTANTS_TIMEOUT", _MUTANTS_DEFAULT_TIMEOUT)),
        ]
        return argv
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
        "cargo-audit": ["cargo", "audit"],
        # TypeScript tools operate on the whole project; they take no file list. Each still
        # runs through konjo-newonly so only net-new findings block. npm-audit is the JS
        # realization of the supply_chain universal gate.
        "tsc": ["npx", "tsc", "--noEmit"],
        "eslint": ["npx", "eslint", "."],
        "stryker": ["npx", "stryker", "run"],
        "npm-audit": ["npm", "audit"],
        # Mojo tools operate on the project/changed files; the formatter checks, the test
        # runner runs the Mojo test suite. Each still runs through konjo-newonly.
        "mojo-format": ["mojo", "format", "-q", "--check", *files],
        "mojo-test": ["mojo", "test"],
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


def _write_mutants_in_diff(base: str) -> str | None:
    """Write the base->working-tree diff to a temp file for `cargo mutants --in-diff`.

    Mirrors what the net-new scan compares against: the diff of the merge-base of HEAD and
    `base` against the current working tree (committed plus any local changes). cargo-mutants
    reads this file and generates mutants only for lines inside the diff, so the gate mutates
    the changed lines rather than the whole crate. The path is absolute so it resolves from
    both the HEAD checkout and the throwaway base worktree the scan runs in.

    Returns None only when git cannot produce a diff at all (no merge-base, git failure), so
    the caller can fall back to cargo-mutants' whole-crate default rather than a broken run.
    An *empty* diff is still written and returned: nothing changed means nothing to mutate,
    which cargo-mutants reports as a fast no-op -- exactly what we want, not a full-crate run.
    """
    mb = subprocess.run(
        ["git", "merge-base", "HEAD", base], capture_output=True, text=True
    )
    ref = mb.stdout.strip() if mb.returncode == 0 and mb.stdout.strip() else base
    diff = subprocess.run(
        ["git", "diff", ref], capture_output=True, text=True, errors="replace"
    )
    if diff.returncode != 0:
        return None
    fd, path = tempfile.mkstemp(prefix="konjo-mutants-", suffix=".diff")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(diff.stdout)
    except OSError:
        os.unlink(path)
        return None
    return path


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
    probe = _TOOL_PROBE.get(tool)
    if probe is not None and subprocess.run(probe, capture_output=True, text=True).returncode != 0:
        return GateResult(
            f"repo:{tool}", ERROR,
            f"`{' '.join(probe)}` failed; the cargo subcommand for {tool!r} is not "
            f"installed (run `cargo install {tool.removeprefix('cargo-')}`)",
        )
    mutants_diff = _write_mutants_in_diff(base) if tool == "cargo-mutants" else None
    try:
        argv = _tool_argv(
            tool, [c for c in changed if c.endswith(".py")], mutants_diff=mutants_diff
        )
        if argv is None:
            return GateResult(f"repo:{tool}", WARN, "no runner mapping; skipped")
        result = newonly.net_new(argv, base)
    finally:
        if mutants_diff is not None:
            try:
                os.unlink(mutants_diff)
            except OSError:
                pass
    if not result.ok:
        return GateResult(f"repo:{tool}", ERROR, f"could not run {tool}: {result.error}")
    if not result.net_new:
        return GateResult(f"repo:{tool}", PASS, "no net-new findings")
    rendered = "; ".join(result.net_new)
    return GateResult(f"repo:{tool}", FAIL, f"{len(result.net_new)} net-new finding(s): {rendered}")


# --------------------------------------------------------------------------- driver


def _gate_plan(
    profile: dict,
    profile_path: str,
    *,
    base: str,
    changed: list[str],
    diff_text: str,
    mode: str,
    self_test: bool,
    flags: dict[str, bool],
) -> list[tuple[str, Callable[[], GateResult]]]:
    """The ordered list of (label, thunk) gates to run.

    Building the plan up front -- rather than calling each gate inline -- lets the driver
    announce a gate's label *before* it runs, so the heartbeat log names the gate that is
    currently eating wall-clock instead of only the ones that already finished.
    """
    article_globs = list(profile.get("prose_article_globs", []))

    plan: list[tuple[str, Callable[[], GateResult]]] = [
        ("prose", lambda: gate_prose(changed, base, article_globs)),
        ("secrets", lambda: gate_secrets(diff_text)),
        ("one_way_door", lambda: gate_one_way_door(changed, diff_text, base)),
        ("prove", lambda: gate_prove(changed, flags, profile, base)),
        ("threat_model", lambda: gate_threat_model(changed, diff_text, base, profile)),
        ("polarity", lambda: gate_polarity(changed, base, profile)),
        ("claude_contract", lambda: gate_claude_contract(changed, profile)),
        ("can_fail", lambda: gate_can_fail(profile)),
        ("longrun", lambda: gate_longrun(changed, profile)),
    ]
    if self_test:
        plan.append(("self_test", lambda: gate_self_test(profile_path, mode)))
    plan.append(("verify_cmd", lambda: gate_verify_cmd(profile)))
    plan.append(("context_budget", lambda: gate_context_budget(profile)))
    plan.append(("skill_size", lambda: gate_skill_size(profile)))
    plan.append(("specialist_stats", lambda: gate_specialist_stats()))

    repo_tools = list(profile.get("format_lint", [])) + list(profile.get("contract_gates", []))
    mutation = profile.get("mutation", "")
    if isinstance(mutation, str) and mutation and not mutation.startswith("none"):
        repo_tools.append(mutation)
    for tool in repo_tools:
        if tool not in _TOOL_SCOPE:
            continue
        if tool in _NATIVE_TOOLS:
            if tool == "unsafe-budget":
                plan.append((f"repo:{tool}", partial(gate_unsafe_budget, flags, diff_text)))
            continue
        # partial binds `tool` now, so each thunk runs its own tool -- not the loop's last,
        # which a late-bound `lambda: gate_repo_native(tool, ...)` would.
        plan.append((f"repo:{tool}", partial(gate_repo_native, tool, flags, changed, base)))
    return plan


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
    plan = _gate_plan(
        profile,
        profile_path,
        base=base,
        changed=changed,
        diff_text=diff_text,
        mode=mode,
        self_test=self_test,
        flags=flags,
    )

    total = len(plan)
    results: list[GateResult] = []
    for i, (label, thunk) in enumerate(plan, 1):
        progress.log(f"[{i}/{total}] {label}: running...")
        started = time.monotonic()
        result = thunk()
        elapsed = progress.fmt_elapsed(time.monotonic() - started)
        progress.log(f"[{i}/{total}] {label}: {result.status} ({elapsed})")
        results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(prog="konjo-gates")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--changed", nargs="*", default=[])
    parser.add_argument("--mode", default="daily", choices=["daily", "deep"])
    parser.add_argument("--no-self-test", action="store_true")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="stream per-scanner detail (the exact argv and each HEAD/base scan pass with "
        "its duration) to stderr. The per-gate progress heartbeat is always on; this adds "
        "the sub-gate detail. Equivalent to exporting KONJO_GATES_VERBOSE=1.",
    )
    args = parser.parse_args()

    if args.verbose:
        progress.set_verbose(True)

    with open(args.profile, encoding="utf-8") as fh:
        profile = yaml.safe_load(fh) or {}

    changed = _changed_files(args.base, args.changed)
    diff_text = _diff_text(args.base)

    started = time.monotonic()
    progress.log(
        f"starting: {len(changed)} changed file(s), base {args.base}, mode {args.mode}"
        + ("" if progress.is_verbose() else " (pass --verbose for per-scanner detail)")
    )
    results = run_gates(
        profile,
        args.profile,
        base=args.base,
        changed=changed,
        diff_text=diff_text,
        mode=args.mode,
        self_test=not args.no_self_test,
    )
    total_elapsed = progress.fmt_elapsed(time.monotonic() - started)
    progress.log(f"finished all {len(results)} gate(s) in {total_elapsed}")

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
