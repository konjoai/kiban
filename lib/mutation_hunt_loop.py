"""Section 3 (review-pipeline Sprint P2b): the mutation-hunt loop and gate.

Coverage -> ranked uncovered items (section 1) -> model writes tests (a real headless
`claude` session against one persistent git worktree) -> `cargo mutants --in-diff`
scoped to the *production* diff under test (fixed for the whole loop -- NOT the
round's own test-writing diff; `--in-diff` only mutates lines present in the given
diff, and a round that only adds tests touches no production lines, so scoping
against its own diff finds nothing to mutate -- confirmed live while building this)
-> surviving mutants -> `format_feedback` (section 2) -> back to "model writes tests".
Round 1 is seeded from section 1's ranked uncovered items;
round 2+ is seeded from the prior round's surviving-mutant feedback only -- the plan's
own step diagram loops "surviving mutants -> feedback -> back to step 2 (model writes
tests)", skipping coverage re-extraction on every round. This is arm B's shape (the
specific mutation, plus which existing tests still passed despite it), not arm A's
("here are some uncovered items") -- PF-3 measured arm B beating arm A 9/10 vs 7/10 and
never losing a case arm A won; feeding a generic uncovered-item prompt on every round
would throw that away.

One worktree persists for the whole loop (unlike `lib.gen_runner`'s one-shot
`LiveGenerationBackend`, which checks out a fresh worktree per call -- wrong for this
loop, where round 2's tests must build on round 1's) via `gen_runner`'s own worktree/
diff/usage primitives (`_make_worktree`, `_run`, `_diff_and_paths`, `_parse_usage`,
`_cleanup_worktree`) -- the same primitives `tests/test_gen_runner.py` already treats
as this module's real seam, not private implementation the loop must not touch.

Gate: zero surviving mutants on the round's changed lines, or an explicit
`Konjo-Mutation-Waived` trailer already present in the commit messages passed in
(`lib.oneway`'s existing record-and-check substrate -- the same one `gate_polarity`
(K1) reuses, not a second override channel).

Generated tests must pass on the unmutated tree before they count as progress (PF-3's
secondary finding: 3 of 5 arm-A tests failed on clean code -- not "insufficiently
tested," "not a working test"). `cargo mutants` itself refuses to run at all against a
tree whose unmutated baseline fails (confirmed, Sprint P2 PF-0's `--timeout 60`
postmortem), so a round whose new tests fail the clean-tree check skips the mutation
run entirely rather than letting it error out, and is reported as a clean-tree failure,
not silently retried as if it were progress.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from lib import gen_runner, headless, mutation_feedback, oneway, uncovered_items

DEFAULT_ROUND_CAP = 3
# Starting point per the plan's own instruction ("start the cap at 3 rounds and revise
# from the measured data, not before it") -- same discipline applied here: generous
# enough for one real coding round (worktree edit + a cargo build/test cycle) without
# being unbounded, to be revised once a real run's per-round numbers exist (see
# LEDGER.md's Review-Pipeline-Phase-2 entry for this sprint's actual measurement).
DEFAULT_TOKEN_CEILING_PER_ROUND = 150_000
DEFAULT_GENERATION_TIMEOUT_S = 900
DEFAULT_MAX_BUDGET_USD = 2.0
DEFAULT_TOOLS = "Read,Write,Edit,Bash,Grep,Glob"

_MUTANT_TIMEOUT_S = 600
_TEST_FAILURE_RE = re.compile(r"^(test\s+\S+)\s+\.\.\.\s+FAILED$", re.MULTILINE)


class MutationHuntError(Exception):
    """The loop could not proceed (a setup failure, not a round outcome)."""


@dataclass
class CleanTreeCheck:
    ok: bool
    failed_tests: list[str] = field(default_factory=list)


@dataclass
class RoundResult:
    round_num: int
    prompt_kind: str  # "uncovered_item" | "mutation_feedback" | "clean_tree_failure"
    changed_paths: list[str]
    generation_ok: bool
    clean_tree: CleanTreeCheck | None
    surviving_count_before: int | None
    surviving_count_after: int | None
    surviving_total_before_cap: int | None  # section 2b: full count, pre-format_feedback cap
    truncated: bool  # section 2b: surviving_total_before_cap > len(feedback)
    feedback: list[dict]
    tokens_input: int | None
    tokens_output: int | None
    tokens_cache_read: int | None
    cost_usd: float | None

    @property
    def mutants_killed(self) -> int | None:
        if self.surviving_count_before is None or self.surviving_count_after is None:
            return None
        return max(0, self.surviving_count_before - self.surviving_count_after)


@dataclass
class LoopResult:
    rounds: list[RoundResult]
    terminated_reason: str
    # "zero_surviving" | "round_cap" | "token_ceiling" | "generation_failed" | "no_diff"
    gate_pass: bool
    waiver_trailer_suggestion: str | None  # set only when gate_pass is False
    worktree: str | None  # None once cleaned up

    @property
    def total_tokens(self) -> int:
        return sum((r.tokens_input or 0) + (r.tokens_output or 0) for r in self.rounds)

    @property
    def clean_tree_failure_count(self) -> int:
        return sum(1 for r in self.rounds if r.clean_tree is not None and not r.clean_tree.ok)


def _run_round_generation(
    worktree: Path,
    prompt: str,
    *,
    timeout: int,
    max_budget_usd: float,
    tools: str,
    model: str | None,
) -> tuple[str, list[str], bool, tuple]:
    """One headless turn against the persistent worktree. Returns (diff_text,
    changed_paths, ok, (tokens_in, tokens_out, cache_read, cost_usd))."""
    extra = ["--max-budget-usd", str(max_budget_usd), "--permission-mode", "acceptEdits"]
    if tools:
        extra += ["--tools", tools]
    argv = headless.headless_argv(prompt, model=model, bare=False, stream_json=True, extra=extra)
    try:
        proc = gen_runner._run(argv, cwd=worktree, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "", [], False, gen_runner._NO_USAGE
    diff_text, changed_paths = gen_runner._diff_and_paths(worktree)
    usage = gen_runner._parse_usage(proc.stdout)
    return diff_text, changed_paths, proc.returncode == 0, usage


def check_clean_tree(
    worktree: Path, *, crate: str | None = None, timeout: int = 300
) -> CleanTreeCheck:
    """PF-3's secondary finding, enforced: a generated test that fails on the
    *unmutated* tree is not a test, and must not count as this round's progress."""
    argv = ["cargo", "test"]
    if crate:
        argv += ["-p", crate]
    proc = subprocess.run(argv, cwd=worktree, capture_output=True, text=True, timeout=timeout)
    combined = proc.stdout + proc.stderr
    failed = _TEST_FAILURE_RE.findall(combined)
    return CleanTreeCheck(ok=(proc.returncode == 0), failed_tests=failed)


def run_cargo_mutants_in_diff(
    worktree: Path, diff_base_ref: str, out_dir: Path, *, crate: str | None = None
) -> Path:
    """`cargo mutants --in-diff` scoped to the *production* diff against
    `diff_base_ref` -- NOT the round's own test-writing diff. `--in-diff` only
    generates mutants for lines present in the given diff; a round that only adds
    tests never touches production lines, so scoping against the round's own diff
    finds nothing to mutate (confirmed live while building this loop: "INFO No
    mutants to filter" against a tests-only diff). `diff_base_ref` is the ref
    *before* the production change under test existed (e.g. the PR's target branch,
    matching `konjo-gate.yml` G3's own `--in-diff <(git diff origin/<base>...HEAD)`)
    and stays fixed for the whole loop; only the model's test-writing changes across
    rounds, not what mutation testing is scoped to.

    `crate` (`-p <crate>`) matters more than it looks: run from a multi-crate
    workspace root with no `-p`/`--file` scope, cargo-mutants can print
    "INFO No mutants to filter" and exit almost instantly even though the diff
    plainly touches the target crate's files -- confirmed live against this
    workspace (Sprint P2b section 3's real verify run) where adding `-p` was the
    difference between 0 and 15 discovered mutants on an identical diff. Always
    pass `crate` when the caller knows it, which `run_mutation_hunt_loop` always does.

    Returns `out_dir`; caller reads `outcomes.json` from `out_dir / "mutants.out"` via
    `lib.mutation_feedback` (section 2 -- not a second parser).
    """
    diff_proc = subprocess.run(
        ["git", "diff", diff_base_ref], cwd=worktree, capture_output=True, text=True, timeout=60
    )
    if not diff_proc.stdout.strip():
        raise MutationHuntError("no diff to scope cargo mutants to")
    diff_path = out_dir.with_suffix(".diff")
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text(diff_proc.stdout)
    argv = [
        "cargo", "mutants", "--in-diff", str(diff_path),
        "--output", str(out_dir), "--jobs", "2",
    ]
    if crate:
        argv += ["-p", crate]
    proc = subprocess.run(
        argv, cwd=worktree, capture_output=True, text=True, timeout=_MUTANT_TIMEOUT_S
    )
    outcomes = out_dir / "mutants.out" / "outcomes.json"
    if not outcomes.exists():
        raise MutationHuntError(
            f"cargo mutants --in-diff produced no outcomes.json:\n"
            f"stdout: {proc.stdout[-2000:]}\nstderr: {proc.stderr[-2000:]}"
        )
    return out_dir


def _uncovered_item_prompt(item: uncovered_items.UncoveredItem) -> str:
    return (
        f"Write Rust unit tests for `{item.qualified_name}` in {item.file} "
        f"(lines {item.start_line}-{item.end_line}), which currently has "
        f"{item.uncovered_count} uncovered line(s): {item.uncovered_lines}. "
        "Add the tests to the existing `#[cfg(test)] mod tests` block in that file "
        "(create one if it does not exist yet). Do not modify production code."
    )


def _feedback_prompt(records: list[dict]) -> str:
    parts = [
        "The following mutations survived your prior tests: existing assertions did "
        "not notice the change. For each, strengthen or add an assertion in the same "
        "test file that would fail against the mutated behavior. Do not modify "
        "production code, only test code.",
        "",
    ]
    for r in records:
        still_passing = (
            ", ".join(r["tests_still_passing"]) or "(no tests currently exercise this line)"
        )
        parts.append(
            f"- {r['file']}:{r['line']} in `{r['function']}`: replacing `{r['original']}` "
            f"with `{r['replacement']}` still passes: {still_passing}\n"
            f"  Enclosing item:\n```rust\n{r['item_source']}\n```"
        )
    return "\n".join(parts)


def _clean_tree_failure_prompt(check: CleanTreeCheck) -> str:
    failed = (
        "\n".join(f"- {t}" for t in check.failed_tests) or "(test names not parsed from output)"
    )
    return (
        "The tests you just added fail on the unmutated tree -- they are not "
        "measuring what they claim to. Fix them so they pass against the current, "
        "un-mutated code, without weakening the assertions to the point they no "
        "longer test real behavior:\n" + failed
    )


def _mutant_fingerprint(feedback: list[dict]) -> str:
    ids = sorted(f"{r['file']}:{r['line']}:{r['replacement']}" for r in feedback)
    return oneway.fingerprint(ids)


def run_mutation_hunt_loop(
    repo: Path,
    base_ref: str,
    *,
    uncovered_by_file: dict[str, set[int]],
    ast_diff_binary: Path | None,
    diff_base_ref: str | None = None,
    crate: str | None = None,
    round_cap: int = DEFAULT_ROUND_CAP,
    token_ceiling_per_round: int = DEFAULT_TOKEN_CEILING_PER_ROUND,
    feedback_cap: int = 20,
    generation_timeout_s: int = DEFAULT_GENERATION_TIMEOUT_S,
    max_budget_usd: float = DEFAULT_MAX_BUDGET_USD,
    tools: str = DEFAULT_TOOLS,
    model: str | None = None,
    keep_worktree: bool = False,
    commit_messages_for_waiver_check: str = "",
) -> LoopResult:
    """`base_ref` is where the worktree is checked out (typically the PR's own HEAD,
    already containing whatever production change is under test). `diff_base_ref`
    (default: same as `base_ref`) is what `cargo mutants --in-diff` scopes against --
    pass the PR's target branch explicitly when `base_ref` already contains the
    production change, so mutation testing sees it as "changed" (see
    `run_cargo_mutants_in_diff`'s docstring for why these must not be the same ref
    when the worktree already contains the change under test).
    """
    diff_base_ref = diff_base_ref or base_ref
    ranked = uncovered_items.extract_uncovered_items(
        repo, uncovered_by_file, ast_diff_binary=ast_diff_binary
    )
    if not ranked:
        raise MutationHuntError("no uncovered items found -- nothing for the loop to target")
    target = ranked[0]

    worktree = gen_runner._make_worktree(repo.resolve(), base_ref, "mutation-hunt")
    rounds: list[RoundResult] = []
    feedback_records: list[dict] = []
    surviving_before: int | None = None
    reason = "round_cap"

    try:
        for round_num in range(1, round_cap + 1):
            last_clean = rounds[-1].clean_tree if rounds else None
            if last_clean is not None and not last_clean.ok:
                prompt, prompt_kind = _clean_tree_failure_prompt(last_clean), "clean_tree_failure"
            elif feedback_records:
                prompt, prompt_kind = _feedback_prompt(feedback_records), "mutation_feedback"
            else:
                prompt, prompt_kind = _uncovered_item_prompt(target), "uncovered_item"

            diff_text, changed_paths, gen_ok, usage = _run_round_generation(
                worktree, prompt,
                timeout=generation_timeout_s, max_budget_usd=max_budget_usd,
                tools=tools, model=model,
            )
            tokens_in, tokens_out, cache_read, cost = usage
            round_tokens = (tokens_in or 0) + (tokens_out or 0)

            if not gen_ok or not diff_text.strip():
                rounds.append(RoundResult(
                    round_num=round_num, prompt_kind=prompt_kind, changed_paths=changed_paths,
                    generation_ok=gen_ok, clean_tree=None,
                    surviving_count_before=surviving_before, surviving_count_after=surviving_before,
                    surviving_total_before_cap=surviving_before, truncated=False, feedback=[],
                    tokens_input=tokens_in, tokens_output=tokens_out,
                    tokens_cache_read=cache_read, cost_usd=cost,
                ))
                reason = "generation_failed" if not gen_ok else "no_diff"
                break

            if tokens_in is not None and round_tokens > token_ceiling_per_round:
                rounds.append(RoundResult(
                    round_num=round_num, prompt_kind=prompt_kind, changed_paths=changed_paths,
                    generation_ok=True, clean_tree=None,
                    surviving_count_before=surviving_before, surviving_count_after=surviving_before,
                    surviving_total_before_cap=surviving_before, truncated=False, feedback=[],
                    tokens_input=tokens_in, tokens_output=tokens_out,
                    tokens_cache_read=cache_read, cost_usd=cost,
                ))
                reason = "token_ceiling"
                break

            clean = check_clean_tree(worktree, crate=crate)
            if not clean.ok:
                rounds.append(RoundResult(
                    round_num=round_num, prompt_kind=prompt_kind, changed_paths=changed_paths,
                    generation_ok=True, clean_tree=clean,
                    surviving_count_before=surviving_before, surviving_count_after=surviving_before,
                    surviving_total_before_cap=surviving_before, truncated=False, feedback=[],
                    tokens_input=tokens_in, tokens_output=tokens_out,
                    tokens_cache_read=cache_read, cost_usd=cost,
                ))
                continue  # next round retries against the same worktree, within round_cap

            out_dir = worktree / ".mutation-hunt-out" / f"round-{round_num}"
            run_cargo_mutants_in_diff(worktree, diff_base_ref, out_dir, crate=crate)
            mutants_dir = out_dir / "mutants.out"
            all_missed = mutation_feedback.load_missed_mutants(mutants_dir)
            feedback_records = mutation_feedback.format_feedback(
                worktree, mutants_dir, cap=feedback_cap
            )
            surviving_total = len(all_missed)
            truncated = surviving_total > len(feedback_records)

            rounds.append(RoundResult(
                round_num=round_num, prompt_kind=prompt_kind, changed_paths=changed_paths,
                generation_ok=True, clean_tree=clean,
                surviving_count_before=surviving_before, surviving_count_after=surviving_total,
                surviving_total_before_cap=surviving_total, truncated=truncated,
                feedback=feedback_records,
                tokens_input=tokens_in, tokens_output=tokens_out,
                tokens_cache_read=cache_read, cost_usd=cost,
            ))
            surviving_before = surviving_total

            if surviving_total == 0:
                reason = "zero_surviving"
                break
        else:
            reason = "round_cap"

        gate_pass = bool(rounds) and rounds[-1].surviving_count_after == 0
        waiver_suggestion = None
        if not gate_pass and rounds and rounds[-1].feedback:
            fp = _mutant_fingerprint(rounds[-1].feedback)
            already_waived = bool(commit_messages_for_waiver_check) and oneway.find_trailer(
                commit_messages_for_waiver_check, oneway.MUTATION_WAIVED_TRAILER, fp
            )
            gate_pass = already_waived
            if not gate_pass:
                trailer = oneway.make_trailer(oneway.MUTATION_WAIVED_TRAILER, fp)
                waiver_suggestion = f"{trailer} — <reason>"

        return LoopResult(
            rounds=rounds, terminated_reason=reason, gate_pass=gate_pass,
            waiver_trailer_suggestion=waiver_suggestion,
            worktree=str(worktree) if keep_worktree else None,
        )
    finally:
        if not keep_worktree:
            gen_runner._cleanup_worktree(repo.resolve(), worktree)
