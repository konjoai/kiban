"""Phase 14, Phase 1: the task-to-diff loop.

`lib/headless.py` builds a single `claude -p` invocation -- a generic primitive other
tooling builds on (a summarize step, a status check, a classify step). It has no notion
of "task description in, diff out": no repo checkout, no diff capture, no apply/verify
loop. `.konjo/killtests/P13/KT-13.1.md` named exactly this gap as the reason the
empirical protocol behind Phase 2's six candidate invariants could not run.

This module is that missing loop, and it is a *consumer* of `lib.headless`, not a
replacement for it -- `headless_argv`'s `--verbose`-with-stream-json correctness still
matters here, so `LiveGenerationBackend.generate` builds its argv the same way generic
callers do, then adds the pieces a real autonomous coding session needs that a one-shot
headless call does not: an isolated git worktree (so a throwaway measurement session
never touches the caller's own checkout or gets pushed anywhere), explicit context
injection (`--append-system-prompt`, needed regardless of `--bare` -- a measurement
harness needs to control exactly what context a run saw, not rely on ambient
CLAUDE.md discovery), a way to edit files non-interactively (see `DEFAULT_TOOLS` and
the class docstring below for why this is `--permission-mode acceptEdits` + an
explicit tool allowlist here, not `--dangerously-skip-permissions`), and a spend
ceiling (`--max-budget-usd`) so one runaway session cannot consume an unbounded amount
of an experiment's budget.

Deterministic where it can be (the worktree is checked out at a pinned commit, the
prompt and context are recorded verbatim), seeded and recorded where it cannot (the
model call itself); see `evals/gen_cassettes.py` for the record/replay wrapper that
makes a recorded run replay offline, the same cassette discipline
`evals/cassettes.py` already established for the review gate.
"""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lib import headless

DEFAULT_TIMEOUT_S = 900
DEFAULT_MAX_BUDGET_USD = 2.0


@dataclass(frozen=True)
class GenTask:
    id: str
    prompt: str
    context_label: str
    source: str
    repo: str  # local path to the repo checkout this task runs against
    base_ref: str  # commit-ish to check the worktree out at before running the task


@dataclass
class GenerationResult:
    task_id: str
    context_label: str
    diff_text: str
    changed_paths: list[str]
    returncode: int
    ok: bool  # True iff the session exited 0 AND produced a non-empty diff
    stdout_tail: str  # last ~2000 chars, for debugging a failed/empty run -- not the
    # full transcript, which cassettes.py-style recording does not
    # want to carry either (see gen_cassettes.py)
    model: str | None
    duration_s: float
    worktree: str | None  # None once cleaned up
    # Real per-call token usage, from the CLI's own stream-json `result` event --
    # only populated when the caller opts into `capture_usage` (review-pipeline
    # Sprint P2b, section 3's per-round token-ceiling reporting). None, not 0, when
    # not requested or when the result event could not be parsed -- a real round
    # with zero tokens is not a thing, so None means "not measured," not "measured
    # zero."
    tokens_input: int | None = None
    tokens_output: int | None = None
    tokens_cache_read: int | None = None
    cost_usd: float | None = None


class GenerationBackend(Protocol):
    def generate(
        self, task: GenTask, context_text: str, *, model: str | None = None
    ) -> GenerationResult: ...


def _run(argv: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)


_NO_USAGE = (None, None, None, None)


def _parse_usage(stdout: str) -> tuple[int | None, int | None, int | None, float | None]:
    """Pull real token usage/cost from a stream-json session's terminal `result` event.

    `--output-format stream-json` emits one JSON object per line; the last line with
    `"type":"result"` carries the whole session's `usage` (input_tokens, output_tokens,
    cache_read_input_tokens) and `total_cost_usd` -- confirmed live against the
    installed CLI (Sprint P2b PF-*, section 3 token-per-round reporting). Scanned from
    the end since `result` is always the final event; a malformed or missing line
    returns all-None rather than raising -- this is enrichment, not something a
    generation round should fail over.
    """
    for line in reversed((stdout or "").splitlines()):
        line = line.strip()
        if not line or '"type":"result"' not in line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        usage = data.get("usage") or {}
        return (
            usage.get("input_tokens"),
            usage.get("output_tokens"),
            usage.get("cache_read_input_tokens"),
            data.get("total_cost_usd"),
        )
    return _NO_USAGE


def _make_worktree(repo_root: Path, base_ref: str, label: str) -> Path:
    """A fresh, isolated git worktree of `repo_root` at `base_ref`. Never the caller's
    own checkout -- a generation session's edits (and its git history, if it commits)
    must not leak into the repo the harness itself is running from."""
    worktree_root = repo_root.parent / ".konjo-gen-worktrees"
    worktree_root.mkdir(exist_ok=True)
    branch = f"konjo-gen/{label}/{uuid.uuid4().hex[:8]}"
    path = worktree_root / branch.replace("/", "__")
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(path), base_ref],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    subprocess.run(
        ["git", "checkout", "-B", branch],
        cwd=path,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return path


def _cleanup_worktree(repo_root: Path, worktree: Path) -> None:
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _diff_and_paths(worktree: Path) -> tuple[str, list[str]]:
    # untracked new files don't show in a plain `git diff` -- stage everything first so
    # a task that creates a new file is not silently invisible to the classifier.
    subprocess.run(["git", "add", "-A"], cwd=worktree, capture_output=True, text=True, timeout=60)
    diff = subprocess.run(
        ["git", "diff", "--no-color", "--cached"],
        cwd=worktree,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout
    changed_paths = sorted(
        {
            line.split()[-1].removeprefix("b/")
            for line in diff.splitlines()
            if line.startswith("+++ ")
        }
    )
    return diff, changed_paths


#  A non-interactive session needs some way to edit files without an approval prompt
# it can never answer. `--dangerously-skip-permissions` is the standard answer for
# headless CI automation running as a non-root user with its own API key -- neither is
# guaranteed here: the CLI itself refuses that flag under root ("cannot be used with
# root/sudo privileges for security reasons", confirmed against the installed CLI, not
# assumed), and `--bare` mode's auth is "strictly ANTHROPIC_API_KEY... OAuth and
# keychain are never read" (per `claude --help`), which fails closed in an environment
# whose only credential is a host-managed provider token -- also confirmed directly: a
# `--bare` call here gets "Authentication error," the identical prompt without `--bare`
# succeeds. So this backend defaults to `bare=False` (host-managed auth still resolves)
# and `--permission-mode acceptEdits` with an explicit tool allowlist (no WebFetch/
# WebSearch -- a generation session has no business reaching the network) instead of a
# blanket bypass. Both are overridable for a caller running as a non-root CI user with
# its own key, where the faster `--bare` + full-bypass combination is the better fit.
DEFAULT_TOOLS = "Read,Write,Edit,Bash,Grep,Glob"


class LiveGenerationBackend:
    """Drives a real autonomous coding session against an isolated worktree."""

    def __init__(
        self,
        *,
        timeout: int = DEFAULT_TIMEOUT_S,
        max_budget_usd: float = DEFAULT_MAX_BUDGET_USD,
        keep_worktree: bool = False,
        bare: bool = False,
        permission_mode: str = "acceptEdits",
        tools: str = DEFAULT_TOOLS,
        capture_usage: bool = False,
    ) -> None:
        self.timeout = timeout
        self.max_budget_usd = max_budget_usd
        self.keep_worktree = keep_worktree
        self.bare = bare
        self.permission_mode = permission_mode
        self.tools = tools
        # Opt-in: switches to stream-json so the real `result` event's usage/cost can
        # be parsed. Default False keeps existing callers (plain text stdout) unchanged.
        self.capture_usage = capture_usage

    def generate(
        self, task: GenTask, context_text: str, *, model: str | None = None
    ) -> GenerationResult:
        repo_root = Path(task.repo).resolve()
        worktree = _make_worktree(repo_root, task.base_ref, task.id)
        start = time.monotonic()
        try:
            extra = ["--max-budget-usd", str(self.max_budget_usd)]
            if self.permission_mode:
                extra += ["--permission-mode", self.permission_mode]
            if self.tools:
                extra += ["--tools", self.tools]
            if context_text.strip():
                extra += ["--append-system-prompt", context_text]
            argv = headless.headless_argv(
                task.prompt,
                model=model,
                bare=self.bare,
                stream_json=self.capture_usage,
                extra=extra,
            )
            proc = _run(argv, cwd=worktree, timeout=self.timeout)
            diff_text, changed_paths = _diff_and_paths(worktree)
            duration = time.monotonic() - start
            usage = _parse_usage(proc.stdout) if self.capture_usage else _NO_USAGE
            return GenerationResult(
                task_id=task.id,
                context_label=task.context_label,
                diff_text=diff_text,
                changed_paths=changed_paths,
                returncode=proc.returncode,
                ok=(proc.returncode == 0 and bool(diff_text.strip())),
                stdout_tail=(proc.stdout or "")[-2000:],
                model=model,
                duration_s=duration,
                worktree=str(worktree) if self.keep_worktree else None,
                tokens_input=usage[0],
                tokens_output=usage[1],
                tokens_cache_read=usage[2],
                cost_usd=usage[3],
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start
            return GenerationResult(
                task_id=task.id,
                context_label=task.context_label,
                diff_text="",
                changed_paths=[],
                returncode=-1,
                ok=False,
                stdout_tail=f"TIMEOUT after {self.timeout}s: {exc}",
                model=model,
                duration_s=duration,
                worktree=str(worktree) if self.keep_worktree else None,
            )
        finally:
            if not self.keep_worktree:
                _cleanup_worktree(repo_root, worktree)
