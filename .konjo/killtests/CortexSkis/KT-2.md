# KT-2 — Projection fidelity (BLOCKING)

**Verdict: PASS.** A folded markdown page is a faithful read model of the event
stream: exact match on the active set, full A→B→C supersede chain visible with
no field loss, and the redacted item excluded from active but preserved
(with its reason) in the page's Retired section. Idempotent: identical stream in
produces byte-identical markdown out on a second run.

## Command

```
python3 -m pytest tests/test_cortex.py -v
```

## Fixture (`tests/test_cortex.py::test_kt2_chain_and_redact_fidelity`)

`decide` A ("Use SQLite for local cache"), `supersede` A→B ("...with WAL mode"),
`supersede` B→C ("...with WAL mode and a busy_timeout"), `decide` D ("Log at INFO
by default", unrelated), `redact` D.

## Raw output

```
tests/test_cortex.py::test_kt2_chain_and_redact_fidelity PASSED          [ 25%]
tests/test_cortex.py::test_idempotent_fold_is_byte_identical PASSED      [ 50%]
tests/test_cortex.py::test_empty_scope_renders_without_erroring PASSED   [ 75%]
tests/test_cortex.py::test_scope_slug PASSED                             [100%]
4 passed in 0.02s
```

## What was checked, against the threshold's exact wording

- **Exact match on the active set**: the Active section contains C
  (`Use SQLite with WAL mode and a busy_timeout`) and nothing else at top level.
- **Full chain visible**: `A -> B -> C` (the real ids) appears literally in the
  Active section's `chain:` line, and each of A's and B's full records
  (decision, rationale, alternatives, confidence, date, author) are rendered
  inline above C's own record -- not just their ids.
- **No field loss**: every one of A's, B's, and C's `rationale`,
  `alternatives_considered`, and `confidence` strings/values are asserted
  present verbatim in the rendered page.
- **D omitted from active, not erased**: `Log at INFO by default` does not
  appear in the Active section; it does appear in the Retired section, together
  with the real redact `reason` text.
- **Idempotent**: a second `render_scope()` call against the same unmutated
  stream produces a string equal by `==` to the first -- byte-identical, not
  just structurally equivalent. This is by construction, not luck:
  `projected-at` is stamped as the newest event's own timestamp in scope (a
  property of the data), never wall-clock time, so a re-fold with no new events
  can never introduce a diff. Also verified against the full 30-topic KT-1
  corpus (`evals/fixtures/ledger/run_kt1.py`'s own generation step calls
  `render_scope` once; re-running `konjo-decision project` twice against the
  same fixture state dir, checked with `diff`, produces zero output).

## Design note carried forward

Superseded-but-not-redacted chain members (A, B above) never get their own
top-level `### ` heading -- they render only inline, nested under the active
decision that superseded them. This was a deliberate reading of "chains shown
inline" (Phase 1 brief): a scope with a long supersede chain does not produce
one heading per historical link, only one heading per *live topic*, with its
full history nested underneath. If a future sprint wants standalone
navigability into superseded-but-not-redacted history (e.g. a permalink to B on
its own), that is a rendering change, not a fidelity gap -- KT-2 only requires
the chain and its fields to be *visible*, not independently addressable.
