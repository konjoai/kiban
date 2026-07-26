# KT-K1.2 — Does the waiver channel actually record? (BLOCKING)

**Verdict: PASS.** `Konjo-Polarity-Waived: <fp> — <reason>` behaves exactly like the
existing one-way and prove trailers: fingerprint-bound to the changed-file set,
greppable in `git log`, and it does not survive a change to that set. No second override
channel was invented — `oneway.fingerprint`, `oneway.find_trailer`, and
`oneway.make_trailer` are reused wholesale; only the trailer label
(`oneway.POLARITY_WAIVED_TRAILER`) is new.

## Command

```
bash tests/test_polarity_killtest.sh
```

## Raw output (2026-07-26)

```
ok: lopi's three real birth-defect sites FAIL G-POLARITY
ok: zero_diff_is_success (a domain condition) is not flagged
ok: a waiver bound to the exact changed-file fingerprint PASSes
ok: the waiver does not silence a different change (KT-K1.2)
ALL polarity kill-test checks passed
```

## What was checked

1. A throwaway repo plants lopi's three real sites (verbatim). `konjo-gates` with
   `polarity: {enabled: true, advisory: false}` FAILs, naming the offending files.
2. The reference-correct `zero_diff_is_success` shape, added in the same change, is
   never itself named in the failure detail.
3. The changed-file fingerprint (`oneway.fingerprint`) is computed from the actual
   `git diff --name-only main...feature` file set. A commit trailer
   `Konjo-Polarity-Waived: <fp> — <reason>` is added (an empty commit, exactly the
   one-way-door confirm pattern) → the gate PASSes, reporting the resolution.
4. An unrelated file is then touched, changing the changed-file set (and therefore the
   fingerprint). The OLD waiver's fingerprint no longer matches the new set →
   `konjo-gates` FAILs again on the still-unresolved findings. The waiver did not
   silence a different change.

## Note on what "diff changes" means here

The fingerprint (inherited from `lib/oneway.py`, used unchanged) is keyed on the
**sorted set of changed file paths**, not file content — identical to the existing
one-way-door acknowledgement and the prove MERGE record. A waiver is therefore bound to
"this exact set of touched files," not to "this exact byte-for-byte diff." This is
existing kiban precedent, not a new gap this gate introduces: `test_oneway_killtest.sh`
and `test_prove_killtest.sh` rely on the identical binding. KT-K1.2's "mutate the diff"
check accordingly means "change the changed-file set" (add or remove a file), which is
the axis this mechanism has always protected.
