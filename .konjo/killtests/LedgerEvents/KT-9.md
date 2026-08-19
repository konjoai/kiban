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

# Verdict: PASS -- two independent machines agree; the literal M3 leg is the one still-open gap (2026-08-19)

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

## Cross-environment (Method step 3): RUN, read back from the actual GitHub Actions log

`konjo-cortex` PR #2 (`wesleyscholl/konjo-cortex`, commit `9bb778c071eb13bbdc0f4574b2993c97e02c5c99`)
triggered `.github/workflows/verify-ledger.yml` on a real `ubuntu-latest` GitHub
Actions runner -- a machine this session never touched, provisioned fresh by GitHub,
running `git 2.54.0` and `Python 3.11.15` (both logged by the runner itself, not
asserted). Read back via `mcp__github__get_job_logs` against job id `96224303245`,
not inferred from the workflow's green badge alone, per this file's own grading
rule:

```
OK: 4 scope(s) verified byte-identical to committed pages
OK: no HIGH-tier secrets across 33 file(s)
```

Both steps (`Re-fold ledger/events/ and diff against committed pages`, `Scan
ledger/events/ and pages for secrets`) show `conclusion: "success"` in the run's own
job metadata, and the printed output above is the actual `print()` output the
comparison script produces only on the zero-mismatch path -- not a status field
standing in for it. This sandbox's own fold of the identical commit, computed and
committed *before* this PR was pushed (not after, and not adjusted to match), hashes
to the same four pages: `org.md` `d59049b7…`, `repo-kiban.md` `7f664960…`,
`repo-lopi.md` `58205327…`, `repo-squish.md` `c9896a50…` (sha256, full values in this
session's transcript). Two independent machines -- this sandbox and a GitHub-hosted
runner -- folded the same `ledger/events/` commit and produced byte-identical
markdown.

## What this PASS does and does not establish

Establishes: no source of nondeterminism was found in a direct code audit, the
comparison mechanism used to check for drift correctly detects a real difference
when one exists (positive control), repeated folds are byte-identical within this
one environment at realistic scale (35 events), and **two genuinely independent
machines -- this cloud sandbox and a GitHub Actions `ubuntu-latest` runner --
produced byte-identical output from the same event commit**, read back from the
runner's own logs rather than trusted from a green badge.

Does not establish, and is not overclaimed as established: byte-identical output
against Wes's actual M3 laptop specifically. This session had no access to that
machine -- confirmed by construction (a cloud sandbox was never going to have it),
not discovered as a surprise partway through. Two machines agreeing is real evidence
against a broad class of nondeterminism (locale, OS, filesystem, Python patch
version, timezone default), but it is not the identical claim as "the M3 agrees
too." **Recommendation to Wes:** run the fold once on the M3 against commit
`9bb778c` (or whatever commit is current by the time this is read) and confirm the
hash matches the values above. That single check is what would fully close KT-9;
everything reachable from a cloud session has now been run and reported honestly,
not asserted in advance.
