# evals: the meta-gate corpus

The gates test themselves. A gate that stops catching a known bug class is itself a
defect, so kiban keeps a corpus of fixtures and measures the gates against it. This is
the meta-gate.

## How a fixture works

Each fixture is a directory with two files:

- `diff.patch`: a change to feed the gate.
- `expect.json`: what the gate must do with it.

Two expectation shapes:

```json
{ "must_flag": { "category": "numerics", "severity": "CRITICAL" } }
```
The gate must flag this change, in the named category at the named severity. A miss is a
regression.

```json
{ "must_be_silent": true }
```
The gate must stay silent. A flag here is a false positive.

## Corpus rules

- Every fixture maps to a real bug class, not a synthetic one. The `dtype_promotion`
  fixture reintroduces the fp16 to fp32 KV-cache promotion bug squish actually hit.
- Keep a clean control (`_clean_control`) so false-positive rate is measured, not
  assumed. A gate that flags the boring correct change is too noisy to block.
- The runner records `detection_rate`, `false_positives`, and `missed_bugs` and fails
  the build if the gate regresses below the prove baseline.

## Running it

```bash
konjo-eval --runs 3                  # default profile is squish
konjo-eval --runs 3 --json           # raw report
```

The harness calls the same `review_diff` the live gate uses, `runs` times (default 3),
and records per-run detection plus the aggregate. It exits nonzero on a missed CRITICAL
bug or a control that fired. A single-run detection rate is never treated as final.

## Status

The corpus covers all four squish specialists as of 0.6.0: numerics (dtype_promotion),
memory-bandwidth (memory_bandwidth_copy), concurrency (concurrency_race), and api-surface
(api_contract_break), each a planted bug flagged at CRITICAL, plus the `_clean_control`
and `_clean_control_mlx` silence controls. `konjo-eval run --replay` is the deterministic
CI path; a missing cassette key hard-errors rather than passing as zero findings.
