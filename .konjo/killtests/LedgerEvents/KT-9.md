# KT-9 -- Does fold determinism hold across machines, not just across runs on one?

## Pre-registration (write this section BEFORE running anything)

Claim under test: the same event set produces byte-identical Cortex pages on a
GitHub-hosted Actions runner and on the machine that wrote them. `KT-2`
(`.konjo/killtests/CortexSkis` era, cited in `LEDGER.md`'s `Cortex-Projection-1`)
already proved idempotency -- refolding an unchanged stream *on one machine* is
byte-identical to the prior fold. KT-9 is a different, stronger claim: the same
determinism holds *across* machines, which is the entire basis Sprint K5 Phase 3's CI
verifier depends on (it re-folds `ledger/events/` on a GitHub runner and diffs
against the committed pages -- if that diff can differ from what the writing machine
produced for reasons that have nothing to do with real drift, the check is unusable).

Threshold: zero-byte diff between the same fold run on two genuinely different
machines.

Stop rule (stated before running anything, per the brief): if the fold is not
reproducible across environments, the CI check cannot exist and Sprint K5 stops at
Phase 2 -- this is not a result to paper over with a fuzzy/whitespace-tolerant
comparison. A check that tolerates differences cannot tell real drift from noise,
which defeats the entire point of Phase 3.

**Known constraint on this session, stated up front, not discovered partway
through:** this is a cloud sandbox session with no access to Wes's M3 laptop -- the
actual second machine the sprint brief names. What this session *can* do is fold on
this container and, separately, let `konjo-cortex`'s own Phase 3 CI workflow re-fold
the same event set on a GitHub-hosted Actions runner -- a genuinely different
machine (different OS image, different filesystem, different locale/timezone
defaults) from this sandbox, even though it is not literally the M3. That two-machine
comparison (sandbox vs. GitHub Actions runner) is what this test actually runs;
the M3-specific leg is out of reach here and is named as a gap in the verdict below,
not silently substituted for.

## Absence-of-evidence check

This test's verdict rests partly on "no diff found" between two independently
produced fold outputs -- exactly the shape this section exists to interrogate.

1. **What tool or assumption is the negative resting on?** A byte-for-byte `diff`
   (or hash comparison) between this sandbox's local fold output and the GitHub
   Actions runner's fold output of the identical `ledger/events/` directory (same
   commit, same content).
2. **What was it expected to enumerate, and is that documented or assumed?** The
   comparison is expected to catch any of: locale-dependent string sorting, timezone
   handling in timestamp fields, line-ending differences (`\n` vs `\r\n`), or JSON
   key/dict-ordering differences. This is not assumed to be exhaustive by inspection
   alone -- the code audit in Method below checks each one directly against the
   actual source, not by trusting that "it's probably fine."
3. **Flag as unconfirmed until the positive control passes.** A "zero diff" reading
   is provisional until the mechanism is shown capable of reporting a *nonzero* diff
   on the same data, by the same method (below).

## Positive control

Worked directly: before trusting "zero diff" between two real fold runs, deliberately
produce two fold outputs that *should* differ (e.g. fold the corpus, then fold it
again after adding one more event) and confirm the same comparison mechanism reports
a nonzero diff. If the comparison tool cannot detect a real, known difference, a
"zero diff" reading on the real cross-machine case would be worthless.

## Method

1. **Code audit** (static, not empirical) of every place nondeterminism could enter
   `ledger/engine.py::_fold()` and `lib/cortex.py::render_scope()`:
   - Sort keys: `_event_sort_key` sorts on plain Python string tuples
     (`decided_at`, `date`, `id`) -- ordinal `str` comparison, not `locale.strcoll`
     or anything locale-sensitive. `cortex.py`'s own `ordered_ids` sort uses the
     identical shape. Neither imports or calls the `locale` module.
   - Timestamps: every timestamp in the system (`_now_iso()` in `ledger/engine.py`)
     is `datetime.now(UTC).strftime(...)`, explicit UTC, never local time. No
     `datetime.now()` (naive/local) call exists anywhere in `ledger/` or the parts
     of `lib/` this store touches.
   - Line endings: `lib/event_store.py::write_event` writes via `os.fdopen(fd, "w",
     encoding="utf-8")` and explicit `"\n"` -- Python text mode on POSIX (both this
     sandbox and a GitHub Actions `ubuntu-latest` runner) does not translate `\n` to
     `\r\n`; that translation is a Windows-only default this code never exercises.
   - Directory/dict ordering: `event_store.iter_events` explicitly sorts directory
     entries (`sorted(target_dir.iterdir())`) before reading, so raw OS directory
     enumeration order (which is unspecified and can vary by filesystem) never
     reaches the fold. `json.dumps` on a `dict` serializes in insertion order, which
     is fixed by the source code building each event dict field-by-field in the same
     order every time -- not by hash-based iteration order.
2. **Empirical, same-environment repeatability** (this sandbox only): fold the K1
   fixture corpus (`evals/fixtures/ledger/gen_k1_corpus.py`, 35 events) twice in a
   row and diff.
3. **Empirical, cross-environment**: once `konjo-cortex`'s Phase 3 CI workflow
   (`.github/workflows/verify-ledger.yml`) exists and runs on a real push, compare
   this sandbox's local fold hash of the same `ledger/events/` commit against what
   the GitHub Actions runner computed (read from the workflow's own log/output).

## Grading anything that runs outside this session

The Phase 3 CI run (step 3 above) executes on a GitHub-hosted runner outside this
session's direct observation. Graded per the standard method: not from the workflow's
green/red status alone, but by reading back the actual computed values (the runner's
logged fold-output hash or diff) via the GitHub API/Actions log, independently of
whatever the workflow's own pass/fail badge claims.

## Stop rule

A green CI run alone does not confirm cross-machine determinism -- the workflow could
be green because it never actually ran a comparison (e.g. a step silently skipped, or
comparing a file against itself). The verdict below reads the actual logged fold
output and diff command, not just the workflow's final exit status.

---

# Verdict: PASS on the checks performed, INVALID PREMISE on the literal M3 leg (2026-08-19)

## Positive control (run first, per the pre-registration)

```
$ KONJO_STATE_DIR=/tmp/k1fix_pc python3 evals/fixtures/ledger/gen_k1_corpus.py
generated 25 pristine + 3 chains + 2 redacts = 30 topics
$ python3 - <<'PY'
# fold repo:kiban, add one more decide event, fold again, sha256 both
PY
first_hash  24e85e1a1529d496365c48a6ea834309aa0ec59f5326126faba689373125b862
second_hash bf322cf4091c8eb34b5bb2cc313d6d1d5fc8dcd66ceae3d7c0dd6fb857360ea2
differ: True
```
Confirmed: hashing/diffing two fold outputs that are supposed to differ correctly
reports a difference (a plain `sha256` over the rendered page changes when a new
active decision is added). The comparison mechanism is not a rubber stamp.

## Code audit (Method step 1)

Every nondeterminism source named in the pre-registration was checked directly
against the current source (`ledger/engine.py`, `lib/cortex.py`,
`lib/event_store.py`) as of this commit. None found: no locale-sensitive sort, no
naive/local timestamps, no platform-dependent line-ending translation, no
unsorted directory or hash-order-dependent iteration reaching the fold. This is a
static review, not a substitute for the empirical checks below -- recorded as
evidence *for* the claim, not as the claim itself.

## Same-environment repeatability (Method step 2)

```
$ KONJO_STATE_DIR=/tmp/k1fix python3 evals/fixtures/ledger/gen_k1_corpus.py
generated 25 pristine + 3 chains + 2 redacts = 30 topics
$ python3 -c "... render_scope twice, compare ..."
idempotent: True
```
35 event files, two folds of the same directory, byte-identical (`==` on the
rendered string, not a structural comparison). Confirms `KT-2`'s idempotency claim
holds at K1-corpus scale, in this environment.

## Cross-environment (Method step 3): NOT YET RUN AT PRE-REGISTRATION TIME

This leg depends on `konjo-cortex`'s Phase 3 CI workflow existing and running on a
real push (Sprint K5 Phase 3, this same session, after this file was pre-registered).
**This verdict section is written before that workflow has run** -- per the
pre-registration's own grading rule, the result will be appended here once the
GitHub Actions run's actual logged output can be read back, not asserted in advance.

## What this PASS does and does not establish

Establishes: no source of nondeterminism was found in a direct code audit, the
comparison mechanism used to check for drift correctly detects a real difference
when one exists (positive control), and repeated folds are byte-identical within
this one environment at realistic scale (35 events).

Does not establish, and is not overclaimed as established: byte-identical output
between this sandbox and Wes's actual M3 laptop specifically. This session has no
access to that machine -- confirmed by construction (a cloud sandbox container was
never going to have it), not discovered as a surprise partway through. The
cross-environment leg that *is* reachable from this session (sandbox vs. a GitHub
Actions runner, a real second machine) is either still pending at the time this file
was committed, or appended above once run -- see the dated addendum, if any, in this
same file's git history for which. **Recommendation to Wes:** before treating the
Phase 3 CI verifier as fully proven rather than "proven except for the specific
second machine named in the brief," run the fold once on the M3 against the same
`ledger/events/` commit CI verified, and confirm the hash matches. That single check
closes the one gap this session structurally could not close itself.
