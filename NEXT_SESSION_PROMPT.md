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
3. **KT-3 is still BLOCKED, and re-running the identical mechanism will
   reproduce the identical result.** No GitHub connector is registered at
   the claude.ai org level (`ListConnectors`, confirmed multiple times
   across two sprints), a bare `create_trigger` Routine gets zero `mcp__`
   tools by default, and a fired session's transcript could not be
   retrieved by any tool available to the firing session (`ListAgents`,
   `SendMessage`, `list_sessions`, `WebFetch` all tried, all failed --
   `.konjo/killtests/CortexSkis/KT-3.md` has the full method). **Do not
   re-attempt this exact mechanism again without first registering a GitHub
   connector** (claude.ai Settings -> Connectors, manual, account-level, not
   automatable from any tool available so far) **or** designing a materially
   different reachability test (e.g. `create_session` with `source_url`,
   which really does clone a repo, untested this sprint by explicit choice
   -- the existing BLOCKED verdict was judged sufficient this cycle).
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

**2. Register the GitHub connector, then design a real KT-3 attempt.**
Manual, account-level (claude.ai Settings -> Connectors), not automatable.
Once it exists, either retry `create_trigger` with `connectors: ["GitHub"]`,
or test `create_session`'s `source_url` param (materially different
mechanism -- a fresh session with the repo already checked out, not a bare
routine) as a narrower but real reachability proof.

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
