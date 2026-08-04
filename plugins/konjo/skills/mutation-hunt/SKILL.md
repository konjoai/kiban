---
name: mutation-hunt
description: Close a real coverage/mutation gap by generating tests against the specific surviving mutant, not a generic "add more tests" prompt. Use when a mutation gate (cargo-mutants for Rust, mutmut for Python) is failing and the fix needs to target real untested logic, not just raise a percentage.
---

# mutation-hunt

The surviving-mutant -> assertion loop (review-pipeline `KONJO_REVIEW_PIPELINE_PLAN.md`
Phase 2, section 3). Backed by `lib/mutation_hunt_loop.py` and the real CLI call site,
`bin/kiban-mutation-hunt` -- this file is not the mechanism, the CLI is.

## Why this beats "write more tests"

A pre-registered pilot (Sprint P2, PF-3) measured mutation-specific test generation
against generic "write tests for this function": 9/10 mutants killed vs 7/10, and the
mutation-informed arm never lost a case the generic arm won. Feed the model the
specific mutation and which existing tests still passed despite it -- not just "this
code is uncovered."

## Run it

```bash
cargo build --release --manifest-path packages/konjo-ast-diff-rs/Cargo.toml
cargo llvm-cov -p <crate> --lcov --output-path lcov.info   # or your repo's coverage tool
bin/kiban-mutation-hunt run \
  --repo /path/to/repo --base-ref HEAD --diff-base-ref origin/main --lcov lcov.info \
  --crate <crate> --path-prefix crates/<crate>/ \
  --round-cap 3 --token-ceiling 150000 \
  --out bench_results/mutation-hunt
```

`--base-ref` is where the worktree starts (usually the PR's own HEAD, already
containing the production change under test). `--diff-base-ref` is what `--in-diff`
scopes mutation testing against (the PR's target branch) -- these must differ, or
`--in-diff` sees no production lines "changed" and tests nothing.

Exits 0 iff the gate passes (zero surviving mutants, or an existing
`Konjo-Mutation-Waived` trailer covering the exact survivor set); exits 1 otherwise.
`--out` writes a JSON artifact with per-round token/cost/kill numbers.

## What each round does

1. Round 1: the top-ranked uncovered item (coverage -> `lib/uncovered_items.py`).
2. `cargo mutants --in-diff` scoped to the production change under test (fixed for
   the whole loop, e.g. `--diff-base-ref origin/main`) -- not the round's own
   test-writing diff, which touches no production lines and would scope to nothing.
3. Surviving mutants -> `lib/mutation_feedback.py`'s structured records (the specific
   mutation, plus which tests still passed) fed back as round 2+'s prompt -- never a
   fresh generic "uncovered items" prompt after round 1.
4. A round whose new tests fail on the *unmutated* tree does not count as progress
   (PF-3's own finding: 3 of 5 generic-arm tests failed on clean code) -- it retries
   within the same round cap instead of running mutants against a broken baseline.
5. Terminates on zero surviving mutants, the round cap, or the per-round token ceiling.

## Waiving instead of fixing

If the loop exhausts its round cap with mutants still surviving, it prints a suggested
`Konjo-Mutation-Waived: <fingerprint> — <reason>` trailer (the same record-and-check
substrate `Konjo-Polarity-Waived` already uses, `lib/oneway.py` -- no second override
channel). Fill in a real reason and add it to a commit message to waive that exact
survivor set; a different survivor set needs a new trailer.

## Consuming repos

squish and vectro pin a kiban ref and call `bin/kiban-mutation-hunt` the same way
lopi's own CI does -- see lopi's `.github/workflows/konjo-gate.yml` G3 job for the
reference wiring (opt-in, `workflow_dispatch`, not a default gate on every PR: this
loop spends real model tokens per round).
