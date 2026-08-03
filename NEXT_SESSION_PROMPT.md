# Next session: Phase 2 build (sections 1-4), review-pipeline plan

Sprint P2's pre-flight (`CHANGELOG.md` [1.12.0], full reasoning in `LEDGER.md`'s
`Review-Pipeline-Phase-2-PF`) ran all four pre-flight items -- PF-0 through
PF-3/KT-2A/KT-2B -- against real code, real compiles, real test runs. **PF-3/KT-2B
passed 10/10 vs 2/10**, clearing the pre-registered stop rule ("B beats A by >= 3
kills") by a margin of 8. Nothing in sections 1-4 (uncovered-item extraction, the
surviving-mutant feedback formatter, the loop+gate, the `konjo/mutation-hunt` skill)
was built this session -- read `LEDGER.md`'s `Review-Pipeline-Phase-2-PF` entry first,
it is not summarized twice here.

## What's already established, do not re-derive

1. **cargo-mutants' own `mutants.json`/`outcomes.json` already carries everything
   section 2's formatter needs**: file, line+column span (mutated expression *and*
   enclosing item), qualified function name, replacement text, and a ready unified
   diff. Confirmed empirically (PF-2/KT-2A) against a real scoped run. **No new AST
   resolver is needed for this** -- `konjo-ast-diff-rs` is a different tool (before/after
   two-version diff by name, no span tracking at all currently) and was confirmed not
   to be the right building block here. Don't reach for it for section 2; it may still
   be the right tool for section 1's uncovered-line-to-item mapping (lcov gives line
   numbers, not spans, so *something* has to walk `syn` AST for that) -- but that's a
   `--line <N>` lookup mode `konjo-ast-diff-rs` does not have today, not a reuse of its
   existing before/after diff mode.
2. **The existing mutation gate that can actually reject is lopi's own
   `.github/workflows/konjo-gate.yml` G3 job** (`grep`s cargo-mutants' one-line summary,
   hard `exit(1)` over 10% survival, no `continue-on-error`). `konjo_gates_py.cli`'s
   generic dispatcher is deliberately disabled for lopi (`mutation: "none -- ..."` in
   `.konjo/profile.yml`) because its text-diff net-new mechanism false-positives on
   every run against cargo-mutants' timing-carrying output. Section 3's "the gate must
   be able to reject" instruction is about **building a new gate for the loop's own
   round output**, not fixing the existing G3/dispatcher split -- that split is a known,
   working (if awkwardly duplicated) arrangement, not a bug to route around here.
3. **`lib/bench.py` had three real, now-fixed bugs** (two found and fixed this
   session, one pre-existing from Phase 0): nextest-missing fallback exit-code check,
   the Baseline-entry crash in the per-crate breakdown, and the `--jobs 2` hardcode.
   `bench_results/lopi/` will have a real completed artifact once the retried PF-0
   baseline (launched 22:04:23Z, 8h cap) finishes -- check there first before
   re-running anything. If it's still running or the log shows it finished, see the
   next section.

## PF-0 baseline: check status first

The retried run may have finished, still be running, or have hit the 8h cap by the
time this is read. Check:
```
cat bench_results/lopi/*.json 2>/dev/null | tail -30   # a completed artifact, if one landed
ps aux | grep kiban-bench                              # still running?
```
If still running and you need the box for other work, **do not run another heavy
`cargo` job against lopi's own workspace concurrently** -- that is exactly what caused
the first PF-0 attempt to fail (a nested-cargo-spawn test in `lopi-spec` starved under
self-contention and blew its 120s timeout; see `LEDGER.md` for the full diagnosis).
Small, scoped fixture runs (e.g. section 3's `evals/fixtures/rust/` end-to-end verify)
are lower risk since they don't touch lopi's own `cargo test --workspace`, but still
avoid running two heavy cargo/rustc jobs on this 4-core box at once.

Once it completes, record the real number in `LEDGER.md` (KT-D's input) -- do not
report a still-running or capped-out partial as the baseline.

## Phase 2 build: sections 1-4

Full detail in `KONJO_REVIEW_PIPELINE_PLAN.md`'s Sprint P2 companion doc §1-§4. In
order, since each depends on the last:

1. **§1 Uncovered-item extraction.** Parse lcov (lopi) / coverage.py (squish), map
   uncovered lines to enclosing items, rank by uncovered-line count. This needs a
   file+line -> enclosing-item lookup that doesn't exist yet -- likely a new mode on
   `konjo-ast-diff-rs` (add span tracking to `ItemSig`, since it currently has none;
   `syn`'s spans are available via `proc-macro2`'s span-locations feature). Verify
   against lopi at HEAD (coverage run needs `cargo-llvm-cov` installed -- not present
   in this session's environment, install it first), hand-check 3 items against the
   lcov report directly.
2. **§2 Surviving-mutant feedback formatter.** One structured record per surviving
   mutant: enclosing item source, exact mutation, file:line, tests that exercise the
   item and still passed. That last field has no existing per-test coverage
   attribution in either repo (lcov/coverage.py give hit counts, not per-test
   attribution) -- a first cut will likely need to approximate this (e.g. grep test
   bodies for call-sites referencing the mutated item's qualified name) and should say
   so explicitly rather than overclaim precision. Verify against 10 real surviving
   mutants (the PF-3 sample, or a fresh scoped run) -- confirm every record resolves to
   a real item and mutation.
3. **§3 The loop and the gate.** Round cap and per-round token ceiling are both
   required (L25 precedent) -- this is explicitly called out as the most plausible
   runaway-cost surface in the whole plan; do not skip either. The gate must reject on
   real conditions, not just format nicely. Verify with one real end-to-end run on a
   deliberately under-tested fixture in `evals/fixtures/rust/` (this is a kiban-owned
   fixture directory, not a lopi one -- low contention risk). Report rounds taken,
   mutants killed per round, tokens spent per round.
4. **§4 `konjo/mutation-hunt` skill.** Package §2+§3 as a reusable skill, squish/vectro
   consume via pin bump. Per Sprint S13's own rule: wire a real call site, a skill file
   nobody invokes is not a shipped feature.

## Non-goals, still

Same as PF's own non-goals list: no critic, router, or `routing.toml`; no
`planner_executor` wiring into `AgentRunner::run()`; no `RepoProfile`/
`allow_self_modify`/cost-breaker fixes; no `auth`/`path_construction` trigger
detection; no Kani; no coverage-floor changes.
