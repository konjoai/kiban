# Next session: Phase 1 of the review-pipeline plan (Planner/Executor split, in lopi)

Sprint P0 (`CHANGELOG.md` [1.10.0], full reasoning in `LEDGER.md`'s
`Review-Pipeline-Phase-0-1`) built the measurement instrumentation
`KONJO_REVIEW_PIPELINE_PLAN.md` needs before any gate, critic, or router is justified.
Nothing below is a critic, a gate, or a router — those stay out of scope until Phase 3.

## What P0 actually found, corrected against the plan's assumptions

1. **Coverage tool: not tarpaulin.** Neither lopi nor squish uses it. `kiban bench` uses
   each repo's own tool (`cargo llvm-cov nextest`, `pytest --cov`). If a future sprint
   adds a third target repo, check its real tool before assuming tarpaulin — it has been
   wrong twice for zero for two repos now.
2. **`cargo-mutants` was already wired, diff-scoped only.** `kiban bench`'s full-repo run
   is the new thing, not the wiring itself.
3. **Full-workspace mutation testing on lopi is a multi-hour job.** A 35-minute capped
   run reached 109 of an estimated ~1,500-2,000 mutants (49 caught / 53 missed / 7
   unviable, 52.0% survival on what ran). **This is not a baseline to build KT-A/KT-B
   conclusions on yet** — it's an order-of-magnitude sample. Before Phase 3's exit gate
   (L20, "zero escapes across 30 sampled Tier 0 PRs") means anything, run
   `cargo mutants --workspace --jobs 4` (or higher, if more cores are available) to
   completion, detached, likely overnight or via a dedicated long-running job — not
   inside a single interactive session. `kiban bench` already supports this
   (`--mutation-timeout` with a large value); it just needs the wall-clock budget.
4. **lopi already had three overlapping-but-incomplete cost-control mechanisms** before
   this sprint's work order: a per-session USD ceiling (reactive, 10s poll), a mid-stream
   CLI-budget kill (reactive, 95% threshold), and an explicitly-unwired
   `BudgetGovernor`. None of them is a pre-call, per-day token gate. The work order
   (`lopi/docs/work-orders/cost-circuit-breaker.md`) is the precise integration spec;
   the pure decision logic already shipped and is unit-tested
   (`lopi/crates/lopi-core/src/cost_breaker.rs`).

## Backfill result (§3), for whoever builds on the per-PR telemetry next

204 of 204 lopi merge commits backfilled (the repo's entire history — it's younger than
the 90-day window), zero unparseable `.rs` files. Hand-check on 5 random samples: exact
match on every git-derivable field except one (`removed_test_fn`, off by 3 of 45 on the
largest sampled commit, traced to git's line-diff algorithm double-counting a
moved-but-unchanged test function — the `syn`-based count is the more defensible one, not
a bug). **`auth` and `path_construction` trigger-surface categories are not detected at
all** (`konjo-ast-diff-rs`'s `TRIGGER_PATHS` table has no entry for either) — no syn-safe
call-path signature exists for them without an unacceptable false-positive rate. If
Phase 3's router ever wants these signals, they need real design work, not a quick regex
bolt-on (the plan is explicit: no regex guesses for this category).

## Phase 1 itself: Planner/Executor split in lopi

Per the plan (section 4, Phase 1): tool profiles on agent spawn (`readonly` vs
`mutating`), a structured plan artifact (files in scope, invariants, test strategy,
explicit non-goals, TOON-encoded), the Executor receiving the plan as system prompt and
never seeing the raw user prompt (first injection boundary), the plan artifact logged to
kledger as the routing input for scope fidelity and the future Contract critic's spec.

**Before starting Phase 1, read `lopi/crates/lopi-agent/src/claude.rs`'s `ClaudeCode`
struct and its builder chain (`claude_builders.rs`) — P0's cost-circuit-breaker work
order found this struct holds zero cross-cutting state today (no config handle, no
memory handle). Phase 1's Planner/Executor split needs the same kind of plumbing
(a plan artifact threaded into Executor construction) — worth designing that plumbing
once, for both needs, rather than adding two separate ad-hoc threading mechanisms in two
different sprints.**

## Do not build yet (still Phase 3+ per the plan)

The router, `routing.toml`, any critic, any new/blocking gate, the mutation-guided test
loop (Phase 2), Kani harnesses, or any change to a coverage threshold anywhere.
