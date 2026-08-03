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

## Plan revision after P0 shipped (read this before starting Phase 1)

The plan document was updated after this sprint's P0 work was already committed
(`KONJO_REVIEW_PIPELINE_PLAN.md`, diffed byte-for-byte against the version P0 was
scoped against). Phase 0 itself is untouched by the update — the new text does not
change anything already shipped. Three things are new, all Phase 1/3-scoped:

1. **§2.4's scope-escape router rule now has a fail-open fix**: escalate to Tier 2 not
   just on scope escape, but also when the plan artifact's scope field is absent, empty,
   or schema-invalid. Directly relevant to Phase 1's plan-artifact schema — design the
   schema so "no scope declared" is representable as invalid, not as an empty-but-valid
   field a router could silently read as "nothing to escape."
2. **New §7, "Borrowed patterns, remixed"** — five design patterns for later phases, each
   a reworked (not adopted) idea from an external orchestrator, with the divergence
   stated. Two matter directly for Phase 1:
   - **§7.3** (validated artifacts): the plan artifact needs a JSON Schema *and* a
     fixture-suite check (once the router exists) — schema catches malformed, fixtures
     catch wrong. Design the plan-artifact schema now with that two-level check in mind,
     even though the fixture suite itself is Phase 3 work.
   - **§7.2** (context layered by volatility): `invariant`/`state`/`volatile` layers
     split by rate-of-change (cache boundary), not by topic. Relevant to how the
     Executor's system prompt (the plan artifact) gets assembled — the plan artifact
     itself is `volatile` (per-call, never cached), but whatever surrounds it in the
     Executor's prompt should sort into the other two layers deliberately, not by
     habit. Measured, not assumed: P0's `tokens_cache_read`/`tokens_input` fields
     already exist to check whether this actually earns its complexity — don't build
     the layering without a before/after comparison to justify it.
   - §7.1 (projection with provenance) and §7.4 (declarative pipeline, authority
     stripped) are Phase 3/kiban-distribution scoped, not immediate Phase 1 blockers.
   - **§7.5 is a new standing rule, effective now**: record in `LEDGER.md`, per external
     (non-Konjo) repo read, URL/commit SHA/license/whether the outcome was pattern-only
     or code-derived. P0 read no external repos (kiban/lopi/squish are all Konjoai's
     own), so no retroactive entry was needed — but Phase 1 may read an external
     orchestrator's source for design ideas the way §7 itself did, and that read needs
     the same citation discipline §7.5 now requires.
3. **Two new non-goals** (§8, renumbered from the old §7): don't adopt any external
   orchestrator as a dependency (§7's patterns are reworked, not imported), and don't
   lift code from noncommercially-licensed sources into any Konjo repo (pattern-only for
   those; permissively-licensed sources are code-liftable with attribution).

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
