# Next session: real Ledger data is still the only thing left, third check running

**P-0 is unmet a third consecutive sprint, and this time `~/.konjo` does not
exist at all in this container** -- not even the K1 fixture that K1 and K2
both found sitting at the real state path. Real event count: 0. Real scope
count: 0. Threshold (>=10 events, >=2 scopes) not met. Every piece of content
this project has ever reasoned over -- `repo-kiban.md`, `KT-5`, `KT-7`, the
live-routine run that resolved `KT-3` -- still traces to the K1 fixture
corpus, transcribed from `kiban`'s own real `LEDGER.md` prose, not real
`konjo-decision decide` usage. **Do not fabricate events to clear this.**
Named the #1 risk in K1's brief, K2's brief, and this sprint's; the pressure
to cut this corner is now higher than either prior check, precisely because
everything else keeps working around it instead of on it.

Sprint K3 ("skis contract, KT-3 disposition, verification hygiene",
`CHANGELOG.md` [1.18.0], full reasoning in `LEDGER.md`'s `Skis-Contract-1`
entry) shipped the skis contract as a gated mechanism, closed KT-3 with a
taxonomy correction, and made the false-premise lesson structural via the
kill-test template. Read `LEDGER.md`'s entry in full before starting
anything below -- it corrects a claim two prior handoffs both carried
forward as settled.

## What's already done and should not be re-derived

1. **The fold mechanism, staleness gate, and fold-and-push automation --
   unchanged since K2, still not re-verified from scratch needed.**
   `lib/cortex.py`, `konjo-decision project`,
   `lib/doc_staleness.check_projection`, `konjo-doc-staleness project-scan`,
   `plugins/konjo/hooks/cortex_fold_push.sh`. `tests/test_cortex.py` and
   `tests/test_doc_staleness.py` cover it; re-run them if you need to
   re-check, don't re-derive.

2. **KT-3 is closed. Verdict: INVALID PREMISE. Do not reopen it as
   unfinished work.** Two separate corrections stacked on this across two
   sprints, and the second one is the one that actually resolves it. First
   (post-K2 continuation): the claim that no GitHub connector was registered
   was false -- `GitHub Integration` was connected the whole time,
   `ListConnectors` simply does not enumerate it. Second, this sprint
   (`LEDGER.md`'s `Skis-Contract-1`, Finding 1): calling that integration a
   "connector" at all was the deeper error. Cloud sessions reach a private
   repo through an account-level GitHub App installation or personal access
   token, configured directly against a session or routine (a routine's own
   Repositories field, or `create_session`'s `source_url`) -- never through
   the connector plane. KT-3's question ("can a routine that must go *find*
   a repo, rather than being *handed* one, reach it") has no referent in the
   product: every routine is handed its repositories by configuration.
   There is no "go find it" mode to test, so there is nothing left to test.
   **Do not attempt a Routines-UI test to "finish" KT-3 -- the question
   itself does not correspond to anything the product does; a browser trip
   would resolve nothing new.** Full taxonomy correction and the resolving
   evidence (with its own honest asterisk: not pre-registered, so recorded
   as a premise resolution, not a graded pass): `.konjo/killtests/CortexSkis/KT-3.md`.

3. **The skis contract is built and gated, not just declared.**
   `konjo-skis/CONTRACT.yml` declares which content must match verbatim
   between `plugins/konjo/skills/<name>/SKILL.md` and its
   `konjo-skis/<name>/SKILL.md` portable variant, and which is allowed to
   diverge on purpose, with a required reason per divergence.
   `lib/skis_contract.py` / `bin/konjo-skis-check` enforce it, wired
   BLOCKING into `.github/workflows/ci.yml`, no `continue-on-error`.
   `KT-8` (`.konjo/killtests/CortexSkis/KT-8.md`) demonstrated both required
   failure modes -- a real correctness regression in a must-match section
   gets rejected naming the section and both paths; a real edit in a
   declared-divergent section leaves the gate silent -- before the gate
   shipped, not after. `recall`: 4 must-match sections (chain reasoning,
   freshness citation, redacted-vs-absent, output shape), 1 declared
   divergent (the read mechanism itself -- CLI shell-out vs Cortex-page
   read, genuinely different by design). `longrun`: 2 must-match sections
   (the four-point resume contract, the helper code sample), 0 divergent --
   the two variants were already substantively aligned before this sprint.
   **If a future sprint adds a third paired skill, extend
   `konjo-skis/CONTRACT.yml` and mark sections with the same
   `<!-- skis-contract:<id> -->` convention -- don't invent a new mechanism.**

4. **Verification hygiene is now a template, not just a LEDGER paragraph.**
   `.konjo/killtests/TEMPLATE.md` -- copy it for any new kill-test. Two
   sections are required, not optional: an absence-of-evidence check
   (whenever a verdict rests on a tool returning nothing, or on treating
   something as a given category) and a positive control (show the same
   mechanism *can* produce a positive before trusting a negative). Both
   exist because `Routine-Reach-1`/`Skis-Contract-1` Finding 1's
   misclassification survived two sprints of review precisely because
   nobody asked either question of it. The template also documents the
   deposit-an-artifact grading pattern (`KT-7`, `KT-8`'s own method) as the
   standard for grading anything running outside the current session,
   including the kiban-contamination guard (`evals/fixtures/ledger/`
   carries the K1 corpus's own ids and decision text -- don't pick a
   question a `kiban`-checkout session could answer from its own fixtures).

5. **`konjo-cortex`'s branch policy is extended** (in that repo's own
   `README.md`, not here): `main` stays projected-pages-only; branches may
   hold verification artifacts; an artifact branch is deleted once its
   verdict is accepted. **Known, logged exception: `main` currently carries
   `ANSWER-KT7.md`** (merged by Wes directly -- not reversed without asking).
   **`kt7-answer` is fully merged and safe to delete but was not deleted
   this sprint** -- no GitHub MCP tool exposes branch deletion, and a direct
   `git push origin --delete kt7-answer` returned `403`. Needs a token with
   that scope, or the GitHub UI, done by hand.

6. **`konjo-skis`'s location and visibility are confirmed and logged**
   (`konjo-skis/README.md`): stays in `kiban`, public, org not personal.
   Exposure scan this sprint (`konjo-skis/`, `plugins/konjo/skills/`):
   1 finding (`wesleyscholl/konjo-cortex` named in a public README, logged
   as a decision -- a name grants no access), 0 secrets
   (`lib/redact.py.scan_paths`, 12 files).

7. **`claude/sign-distribution-channel-heg41d` is real, reviewed, mergeable
   work, closed unmerged by Wes's explicit choice.** Unchanged this sprint.
   Don't merge it or adopt release-tag signing without asking again.

## Open work

**1. Get real Ledger data into this pipeline. Still the only thing that
matters here.** The only thing that unblocks Phase 2 (real projection) and,
by extension, re-running `KT-1`'s retrieval question against real content
instead of a self-authored corpus. Needs a session that actually runs on the
machine holding `~/.konjo/state/ledger/decisions.jsonl` -- no cloud
container this project has run in, across three sprints, has had that file
present at all. If a future session runs there:

```bash
python3 bin/konjo-decision project --all-scopes --out-dir <konjo-cortex clone>
# or just: bash plugins/konjo/hooks/cortex_fold_push.sh
# then check it committed and pushed, and re-run konjo-doc-staleness project-scan
```

**2. Publish `konjo-skis` to claude.ai account skills.** Manual step, no
tool in any session's toolset performs it. Copy `konjo-skis/recall/` and
`konjo-skis/longrun/` in -- `KT-5` already confirmed `recall` answers real
questions correctly against the pushed repo, so this is a pure upload step,
not a "does it work" question. Verify one real question on the phone or a
fresh cloud routine before calling this done.

**3. Delete `kt7-answer` on `konjo-cortex`.** Fully merged, safe, blocked
this sprint only by tooling (see point 5 above). A token with branch-delete
scope, or the GitHub UI, clears it in one step.

## Non-goals, unchanged from K1/K2/K3

No embeddings, no vector index, no retrieval server -- `KT-1` killed this for
real, don't resurrect it without a new kill-test on different data. No
`decide` in `konjo-skis` -- writes stay laptop-only, unchanged. No personal
versus work scope split. No rewriting kiban's gates, profiles, or language
packages. No mutating the event stream from the projection path -- cortex
stays read-only, hand-edits to a cortex page are a bug, not a fast path. No
fabricated events to clear P-0, ever -- checked fresh every sprint, not
carried forward as an assumption. No re-testing Cortex reachability --
`KT-7`/`KT-8` settled the mechanism question; `KT-3` is closed, not
reopenable by a Routines-UI trip. No separate `konjo-skis` repo without one
of the three named split-out triggers (`konjo-skis/README.md`) actually
firing. No merging the signing branch without asking again.
