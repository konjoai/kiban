# Next session: KT-D still blocked, finish PF-0b, cut a release and bump lopi's pin

Sprint P2b (`CHANGELOG.md` [1.13.0], full reasoning in `LEDGER.md`'s
`Review-Pipeline-Phase-2b`, lopi's own `LEDGER.md` entry of the same name for the
per-crate baseline detail) shipped sections 1, 3, and 4 -- all real, all verified with
a live run, not simulated. Read `LEDGER.md`'s `Review-Pipeline-Phase-2b` entry in full
before starting anything below.

## What's already done and should not be re-derived

1. **Section 1 (uncovered-item extraction) shipped and verified, 0 disagreements.**
   `lib/uncovered_items.py` + `konjo-ast-diff-rs --items`. Do not re-verify from
   scratch; if you need to re-check, hand-check different items, not the same three.
2. **Section 2b (cap-detection) wired into the loop.** No further work needed.
3. **Section 3 (the loop + gate) shipped, two real bugs found and fixed while
   building it** (both documented in `lib/mutation_hunt_loop.py`'s own docstrings):
   `--in-diff` must scope against the production diff under test via `diff_base_ref`,
   not the round's own test-writing diff; `--in-diff` needs `-p <crate>` or it can
   silently find zero mutants in a multi-crate workspace. **A real end-to-end run
   against `evals/fixtures/rust/undertested/` produced real numbers**: 3 rounds,
   8/5/0 mutants killed per round, 1,989/8,602/12,571 tokens per round (23,162
   total), 0 clean-tree failures, terminated at the round cap on 2 genuinely
   equivalent mutants with a real suggested waiver trailer. Do not re-run this exact
   fixture expecting a different outcome -- the 2 survivors are mathematically
   unkillable at this fixture's chosen boundary values, by design of the fixture as
   currently written. If a future session wants a fixture with zero equivalent
   mutants, that's a fixture-design change, not a loop bug.
4. **Section 4 (skill) packaged with a real CLI call site, `bin/kiban-mutation-hunt`
   -- proven live by section 3's run above, not a stub.** The CI call site in lopi's
   `konjo-gate.yml` (`mutation-hunt` job, `workflow_dispatch` only) is real but NOT
   live-runnable yet -- see the pin gap below.

## Open work

**1. Cut a kiban release and bump lopi's three pins.** lopi's `konjo-gate.yml`
`mutation-hunt` job clones kiban at the pinned `v1.8.0` tag, which predates this
sprint -- `bin/kiban-mutation-hunt` does not exist there. Bump `.konjo/kiban.ref` and
`konjo-gate.yml`'s two `KIBAN_REF` values together (lopi's own CLAUDE.md "Pinning"
section), only after a release actually contains this sprint's work. Then the CI job
becomes live-runnable; test it once via manual `workflow_dispatch` against a real
crate (e.g. `lopi-ratelimit`, which PF-3's pilot already knows has real surviving
mutants) before trusting it further.

**2. PF-0b: finish the remaining lopi crates.** See lopi's own `LEDGER.md` entry for
the exact per-crate list and numbers as of this sprint's end -- do not re-derive from
`bench_results/lopi/pf0b_summary.jsonl`, which is gitignored and will not survive a
container restart; the ledger entry is the durable record. Resume with
`scripts/pf0b_mutation_baseline.sh` from lopi's repo root -- it's idempotent per
crate (each crate gets its own timestamped output dir), so re-running it re-does
completed crates too unless you trim the `CRATES` array to the remaining ones first.
**KT-D (the 30-run paired Wilcoxon) is still blocked** on the full 5,315-mutant
baseline completing -- per-crate progress is real progress toward it, but is not
itself KT-D's control until every crate is done.

**3. Section 1's squish path is unit-tested against a synthetic fixture only.**
`parse_coverage_json`/`map_python_items` were built to match `coverage.py`'s
documented `coverage json` schema, but squish is out of this session's repo scope --
verify against a real squish `coverage json` run when squish is in scope, the same
way section 1's Rust path was verified against a real lopi lcov report this sprint.

## Non-goals, unchanged from the plan

Any critic, router, tier, or `routing.toml`; wiring `planner_executor` into
`AgentRunner::run()`; the `RepoProfile`/`allow_self_modify`/cost-breaker gaps from
Phase 1's audit table; `auth`/`path_construction` trigger detection; Kani harnesses;
changing any coverage floor.
