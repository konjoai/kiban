# Next session: finish Phase 2 (create konjo-cortex, push, run KT-3), then publish konjo-skis

Sprint K1 ("Cortex Projection and Skis Reach", `CHANGELOG.md` [1.16.0], full
reasoning in `LEDGER.md`'s `Cortex-Projection-1` and `Skis-Reach-1` entries)
shipped everything that doesn't require the `konjo-cortex` repo to already
exist: the fold mechanism, the event-clocked staleness gate, both kill-tests
that could be run without it (KT-1, KT-2, KT-4, all real, all with raw
output in `.konjo/killtests/CortexSkis/`). KT-3 is blocked, not faked --
read that entry in full before starting anything below.

## What's already done and should not be re-derived

1. **`lib/cortex.py` + `konjo-decision project`, shipped and KT-2-verified.**
   Folds a scope into markdown, idempotent by construction (`projected-at` is
   the newest event's own timestamp, not wall-clock time). Do not re-verify
   from scratch -- `tests/test_cortex.py` covers fidelity, chain rendering,
   and idempotency; re-run it if you need to re-check, don't hand-derive the
   same three properties again.
2. **`lib/doc_staleness.check_projection` + `konjo-doc-staleness
   project-scan`, shipped and smoke-tested against the real fixture corpus**
   (fresh right after fold, correctly FAILs once a new event lands in
   scope -- verified live, not just unit-tested). One real bug found and
   fixed while building it: YAML round-trips an ISO-8601 scalar into a
   `datetime`, not a string; `check_projection` normalizes it back before
   comparing.
3. **KT-1 ran for real and the stop rule fired.** Embeddings (real
   `fastembed` dense vectors) lost to keyword search by 6.7 points on a
   30-question sweep, not won by the required 20. **Do not build a
   retrieval index in a future session without a new kill-test that
   contradicts this one on a materially different corpus shape** -- this
   result is corpus-shape-dependent by the brief's own prior (one-line
   decisions with supersede links favor keyword search), and kiban's own
   decision corpus is exactly that shape.
4. **KT-4 passed and `konjo-skis/` exists**, staged inside this repo
   (`konjo-skis/recall/`, `konjo-skis/longrun/`, `konjo-skis/README.md`).
   `decide` was deliberately excluded -- its core function is a Ledger
   write, and writes are laptop-only (see point 6). Don't re-litigate that
   exclusion without new information; the reasoning is in
   `konjo-skis/README.md` and `LEDGER.md`'s `Skis-Reach-1` entry.
5. **The 30-question KT-1 corpus is real content, not fabricated.** No real
   `~/.konjo/state/ledger/decisions.jsonl` exists anywhere reachable from
   this repo or any container it runs in -- confirmed at sprint kickoff, not
   assumed. `evals/fixtures/ledger/gen_k1_corpus.py` transcribes 30 of
   kiban's own real `LEDGER.md` decisions into the Ledger's event schema,
   deterministically (sha1-derived ids -- re-running it reproduces the
   identical file). If a future sprint gets real usage data from the M3,
   KT-1 should be re-run against *that* corpus as the actual validation;
   this sprint's corpus is a legitimate but self-authored substitute, and
   that limitation is recorded in `KT-1.md`, not hidden.

## Open work

**1. Create `konjo-cortex`.** Blocked this sprint:
`mcp__github__create_repository` returned `403 Resource not accessible by
integration` on every attempt -- the GitHub App installation this session
ran under has no account-level repo-creation permission. This is not a
transient failure; do not retry it the same way. Either (a) the repo owner
creates it manually (private, personal account, no need to auto-init --
the first push below provides the initial content) and a future session
gets it added to the GitHub MCP repo scope via `add_repo`, or (b) a future
session runs with a token that has repo-creation scope. Once it exists:

```bash
# from a machine/session with a real KONJO_STATE_DIR (or against the
# committed KT-1 fixture corpus, for a first smoke push):
python3 bin/konjo-decision project --all-scopes --out-dir /tmp/cortex-push
# push /tmp/cortex-push's *.md files to konjo-cortex's main branch
```

**2. Wire the real push into CI/post-flight, not just the checklist line.**
`plugins/konjo/skills/konjo-ship/SKILL.md` now has a conditional checklist
line telling a human/agent to run the fold-and-push by hand at sprint
close-out. That's the honest MVP for this sprint (there was no repo to push
to), but a future sprint should consider whether this belongs in an
automated post-flight step instead of a checklist line someone has to
remember -- same class of gap `Doc-Integrity-Gate-1` found for
`konjo-ship`'s file-list checklist items generally.

**3. Register the GitHub connector, then run KT-3 for real.** `ListConnectors`
confirmed no GitHub connector is installed at the claude.ai org level in
this session -- also a manual, account-level step (claude.ai Settings ->
Connectors), not automatable from any tool available this sprint. Once
`konjo-cortex` exists, is pushed to, and the connector is registered:
create a throwaway Routine whose prompt asks for the active decision on a
known topic from a specific `repo:kiban.md`/`org.md` page and writes the id
to a file, fire it with `fire_trigger`, **open the transcript** (do not
trust a green run status alone -- KT-3's own stop rule says so explicitly),
confirm the id matches, then delete the throwaway Routine and write
`.konjo/killtests/CortexSkis/KT-3.md` following the same format as KT-1/2/4.

**4. Publish `konjo-skis` to claude.ai account skills.** Manual step, no
tool in this session's toolset performs it. Copy `konjo-skis/recall/` and
`konjo-skis/longrun/` in once `konjo-cortex` has real content pushed (so
`recall`'s first live run has something to read) -- verify it answers one
real question correctly on the phone or a fresh cloud routine before
calling this done, per KT-4's own threshold, not just "it uploaded without
an error."

## Non-goals, unchanged from the plan

No embeddings, no vector index, no retrieval server -- KT-1 killed this for
real, don't resurrect it without a new kill-test on different data. No
`decide` in `konjo-skis` -- writes stay laptop-only, unchanged. No personal
versus work scope split. No rewriting kiban's gates, profiles, or language
packages. No mutating the event stream from the projection path -- cortex
stays read-only, hand-edits to a cortex page are a bug, not a fast path.
