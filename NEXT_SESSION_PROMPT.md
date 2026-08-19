# Next session: real Ledger data is still the blocker on everything left

Sprint K2 ("close the loop", `CHANGELOG.md` [1.17.0], full reasoning in
`LEDGER.md`'s `Sprint-K2-Close-The-Loop` entry) shipped everything that
doesn't require real Ledger usage data or account-level manual setup: the
fold-and-push automation (`plugins/konjo/hooks/cortex_fold_push.sh`) and its
proof the staleness gate fails closed (KT-6), plus a portable-skill test
against the real, already-pushed `konjo-cortex` repo (KT-5, fixture-scoped).
Phase 2 (real projection) and Phase 1's full resolution (KT-3) are blocked,
not faked -- read `LEDGER.md`'s entry in full before starting anything below.

## What's already done and should not be re-derived

1. **The fold mechanism, staleness gate, and `konjo-skis` -- shipped K1,
   re-verified K2.** `lib/cortex.py`, `konjo-decision project`,
   `lib/doc_staleness.check_projection`, `konjo-doc-staleness project-scan`
   all unchanged in behavior this sprint. Don't re-verify from scratch --
   `tests/test_cortex.py` and `tests/test_doc_staleness.py` (including two
   new KT-6 pipeline-level tests) cover it; re-run them if you need to
   re-check.
2. **Fold-and-push is now automated, not a manual checklist line.**
   `plugins/konjo/hooks/cortex_fold_push.sh` does the real work when run on
   a machine with both `~/.konjo/state/ledger/decisions.jsonl` and a local
   `konjo-cortex` clone (set `KONJO_CORTEX_DIR` if it's not at the default
   `$KONJO_HOME/cortex`); it's a safe, logged no-op everywhere else,
   including every cloud session. `konjo-ship/SKILL.md`'s checklist now
   calls it instead of naming a raw command.
3. **KT-3 is still BLOCKED, but not for the reason K1 and K2 both recorded.**
   The claim that no GitHub connector is registered was **false** -- see
   `LEDGER.md`'s `Routine-Reach-1` entry and the correction appended to
   `.konjo/killtests/CortexSkis/KT-3.md`. **GitHub Integration is connected
   and always was**; `ListConnectors` simply does not enumerate it (filtered
   on `github` it returns `[]`), so re-running that tool will not tell you
   otherwise. Do not send anyone to Settings -> Connectors to add it again.
   The actual blocker: `create_trigger` rejects the `connectors` parameter
   outright for this org, and without it a fired session's `allowed_tools`
   has zero `mcp__` entries. **Do not re-attempt the bare-routine mechanism
   from this tool** -- it cannot carry a connector by construction. The one
   remaining route is the claude.ai Routines UI, which is browser-only.
4. **KT-5 ran against the real repo, and the mechanism holds.**
   `konjo-skis/recall`'s procedure, followed by hand against
   `wesleyscholl/konjo-cortex`'s actual pushed `repo-kiban.md`, correctly
   resolves a supersede chain and a redacted item with freshness citation.
   Still fixture-scoped content (see point 5) -- the mechanism is proven,
   the data underneath it is not real.
5. **The K1 fixture corpus is still the only content anywhere in this
   pipeline, and that's checked every sprint, not assumed.** Confirmed again
   this sprint: `~/.konjo/state/ledger/decisions.jsonl` on this container is
   still the same 35-event K1 fixture (byte-for-byte), still not real usage
   data. **Do not fabricate events to clear the P-0 threshold (>=10 events,
   >=2 scopes) in a future session** -- this is the sprint brief's own
   explicit #1 risk, called out by name in K1 and K2 alike.
6. **`claude/sign-distribution-channel-heg41d` is real, reviewed, mergeable
   work, closed unmerged by Wes's explicit choice.** Not a rejection -- Wes
   is deferring signing adoption, not declining it. Don't merge it or adopt
   release-tag signing in a future session without asking again; the branch
   itself is untouched and still mergeable when wanted.

## Open work

**1. Get real Ledger data into this pipeline.** The only thing that unblocks
Phase 2 (and, by extension, re-running KT-1's retrieval question against
real content instead of a self-authored corpus, per K1's own
`NEXT_SESSION_PROMPT.md` point 5, still unresolved). This needs a session
that actually runs on the machine holding
`~/.konjo/state/ledger/decisions.jsonl` -- no cloud container this project
has run in so far has that, by design (K1's and K2's own P-0 findings,
independently confirmed). If a future session runs there:

```bash
python3 bin/konjo-decision project --all-scopes --out-dir <konjo-cortex clone>
# or just: bash plugins/konjo/hooks/cortex_fold_push.sh
# then check it committed and pushed, and re-run konjo-doc-staleness project-scan
```

**2. Finish KT-3 from the claude.ai Routines UI, or accept KT-7 in its place.**
`create_session` + `source_url` is now tested and passes
(`.konjo/killtests/CortexSkis/KT-7.md`, 4/4 on questions pre-registered before
the run), so the "can anything that is not my laptop read a Cortex page"
question has a real affirmative answer. What KT-7 does *not* answer is KT-3's
narrower one: whether a routine that must go *find* the repo, rather than being
handed it, can reach it. Testing that needs a Routine created in the claude.ai
Routines UI with the GitHub connector attached there, because the MCP
`create_trigger` path cannot attach one. If that is not worth a browser trip,
close KT-3 as superseded by KT-7 rather than leaving it open a third sprint.

**Whatever you test, deposit an artifact.** The reason KT-3 could not be graded
was never the mechanism; it was that no tool can retrieve a fired session's
transcript, and `list_events` is not available either. KT-7's pattern works:
have the spawned session commit its answer to a branch, then read that commit
back through the GitHub API. Pre-register the questions and expected answers in
the kill-test file *before* spawning anything, and pick questions whose answers
do not exist inside `kiban` -- the fixture ids and their decision text are in
`evals/fixtures/ledger/`, so a session with kiban access can answer KT-3's
original question without reading the Cortex page at all.

**3. Publish `konjo-skis` to claude.ai account skills.** Manual step, no
tool in any session's toolset performs it. Copy `konjo-skis/recall/` and
`konjo-skis/longrun/` in -- KT-5 already confirmed `recall` answers real
questions correctly against the pushed repo, so this is a pure upload step
now, not a "does it work" question. Verify one real question on the phone
or a fresh cloud routine before calling this done.

## Non-goals, unchanged from K1 and K2

No embeddings, no vector index, no retrieval server -- KT-1 killed this for
real, don't resurrect it without a new kill-test on different data. No
`decide` in `konjo-skis` -- writes stay laptop-only, unchanged. No personal
versus work scope split. No rewriting kiban's gates, profiles, or language
packages. No mutating the event stream from the projection path -- cortex
stays read-only, hand-edits to a cortex page are a bug, not a fast path. No
fabricated events to clear P-0, ever -- checked fresh every sprint, not
carried forward as an assumption.
