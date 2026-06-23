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

## Status

`runner.py` is a Phase-1 stub. The fixtures are real and in place so the Phase-1 harness
has a corpus to run on day one.
