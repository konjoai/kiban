# KT-6 — the staleness gate fails closed, real CLI pipeline (not the unit-level function)

**Verdict: PASS.** Running the actual `konjo-decision` -> `konjo-doc-staleness`
CLI pipeline as real subprocesses (not calling `doc_staleness.check_projection()`
directly, which `tests/test_doc_staleness.py::test_projection_stale_when_newer_event_landed`
already covers at the unit level) proves the gate exits non-zero when a Ledger
write happens and the Cortex fold never re-runs, and clears once it does. This
is what closes Phase 4: the manual checklist line in `konjo-ship/SKILL.md` is
now a call to `plugins/konjo/hooks/cortex_fold_push.sh`, and this test proves
the thing that hook exists to prevent (a stale, silently-wrong Cortex page)
is actually caught by CI if the hook is ever skipped.

## Why a pipeline-level test, not just the existing unit test

`test_projection_stale_when_newer_event_landed` (already present before this
sprint) calls `doc_staleness.check_projection(page, newest_event_at=...)`
directly with hand-built strings — it proves the comparison logic is correct
in isolation, but not that `konjo-decision project`'s real markdown output
and `konjo-doc-staleness project-scan`'s real Ledger read actually wire
together the way the checklist assumes. KT-6 runs the real binaries.

## Command

```
python3 -m pytest tests/test_doc_staleness.py -v -k kt6
```

## Raw output

```
tests/test_doc_staleness.py::test_kt6_project_scan_fails_closed_when_fold_never_reran PASSED [ 50%]
tests/test_doc_staleness.py::test_kt6_project_scan_passes_after_refold PASSED [100%]

2 passed in 1.72s
```

## Method (`test_kt6_project_scan_fails_closed_when_fold_never_reran`)

1. Fresh `KONJO_STATE_DIR` per test (`tmp_path`), so this never touches a
   real Ledger.
2. `bin/konjo-decision decide --scope repo:kt6 ...` (real subprocess) logs
   one decision.
3. `bin/konjo-decision project --all-scopes --out-dir <tmp>/cortex` (real
   subprocess) folds it — confirms `repo-kt6.md` exists.
4. `bin/konjo-doc-staleness project-scan --cortex-dir <tmp>/cortex` — exit
   `0`, page is fresh.
5. Sleep 1.1s (the Ledger's own event timestamp has 1-second resolution;
   this guarantees the next event is provably newer, not a same-second
   race), then log a **second** decision in the same scope via
   `bin/konjo-decision decide` — deliberately **without** re-running
   `project`.
6. Re-run `project-scan` — asserted exit code `1`, output contains `FAIL`.

## Method (`test_kt6_project_scan_passes_after_refold`)

Companion test: logs two decisions, folds once (after both), scans — exit
`0`. Proves the gate isn't permanently red once a page has ever gone stale;
it tracks real fold state.

## Full suite regression check

```
python3 -m pytest -q       # 350 passed, 3 skipped
ruff check .                # All checks passed!
mypy lib ledger evals packages/konjo-gates-py/src/konjo_gates_py   # Success: no issues found in 59 source files
bin/konjo-doc-staleness scan   # 0 OK, 7 WARN, 0 FAIL (46 docs scanned) — all 7 WARNs pre-existing, unrelated to this sprint
```

## What this sprint's Phase 4 shipped

- `plugins/konjo/hooks/cortex_fold_push.sh` — new hook, mirrors
  `preamble_update.sh`'s never-blocks/swallows-its-own-failures contract.
  Real fold-and-push only happens where a real `~/.konjo/state/ledger/decisions.jsonl`
  and a local `konjo-cortex` clone both exist (i.e. Wes's laptop, per this
  sprint's own P-0 finding that the Ledger is laptop-only) — every other
  invocation (every cloud session) is a documented, logged no-op, never an
  error.
- `plugins/konjo/skills/konjo-ship/SKILL.md`'s checklist line replaced: was
  a raw `konjo-decision project --all-scopes --out-dir <cortex clone>,
  commit, push` instruction; now invokes the hook.
- This test file, proving the gate the hook exists to make unnecessary
  still fails closed if the hook is ever skipped by hand.

**Not attempted, and out of scope for this note:** wiring the hook into
cloud CI (`.github/workflows/ci.yml`). That's structurally impossible —
CI runners never have the real Ledger, only the local machine does — so
CI's job is (and, per this test, now is) to prove the gate itself works,
not to run the fold.
