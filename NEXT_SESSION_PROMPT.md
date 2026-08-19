# Next session: P-0b is the only number that matters now

**P-0a is done. P-0 is not closed.** The Ledger has real content for the first
time -- 27 events, 4 scopes, 2 supersede chains -- and 22 of those were seeded by
hand from decisions already documented in `lopi`, `squish` and `kiban`. That
unblocks the pipeline mechanically and produces a far better fixture than K1's.
It does **not** prove the habit, and a seeded corpus is exactly what three
sprints of "no real data" was really complaining about.

**The number to check, mechanically:**

```bash
python3 - <<'PY'
from ledger.engine import Ledger
CLOSE = "2026-08-19T15:16:52Z"
f = Ledger()._fold()
p0b = [d for d in f if d.decided_at > CLOSE]
print(f"P-0b events since K4 close: {len(p0b)}")
for d in p0b:
    print(f"  {d.decided_at}  {d.scope:12s}  {d.decision[:60]}")
PY
```

**P-0b counts events whose `decided_at` falls after `2026-08-19T15:16:52Z`.**
At K4's close that count is **0**, by construction. Three events were captured
live during K4's own work and are deliberately excluded -- they predate the
close. Do not move the close date to make the number look better, and do not
backdate anything into the window. An event that needs `--decided-at` to land
after the close date is not a captured event.

If the count is still 0 next sprint, say so plainly. That is the honest signal
that the tooling is finished and the habit has not started, and it is more useful
than any further mechanism work.

Sprint K4 ("real data, run on the machine", `CHANGELOG.md` [1.19.0], full
reasoning in `LEDGER.md`'s `Real-Data-1`) was the first session ever to run on
the machine holding the Ledger. Read `Real-Data-1` before starting anything
below -- Findings 1, 2 and 4 each correct something a prior handoff carried as
settled.

## What's already done and should not be re-derived

1. **The Ledger has real data and the fold has run for real.** 27 events, scopes
   `org` / `repo:kiban` / `repo:lopi` / `repo:squish`, 2 supersede chains, 0
   entries without an alternative considered. `konjo-cortex` `main` carries
   `org.md`, `repo-kiban.md`, `repo-lopi.md`, `repo-squish.md`, all pushed.
   `repo-kiban.md` is no longer the K1 fixture projection -- it was overwritten
   with real content. **Do not re-seed.** If you need more corpus, capture it
   (P-0b), don't transcribe more history.

2. **`decided_at` is a schema field now, and `date` is not it.** `date` stays
   append-time because `projected-at` and `lib/doc_staleness.check_projection`
   clock off it; `decided_at` is when the call was made and defaults to `date`.
   `--decided-at` on `decide` and `supersede`, strict UTC, future stamps
   rejected. Legacy events fall back to `date`. **Don't "simplify" these into one
   field** -- `LEDGER.md`'s `Real-Data-1` Finding 2 explains what breaks.

3. **KT-1 is not re-openable by re-running it as written. The threshold is
   unreachable.** `>= 20` points absolute over a keyword baseline that K1
   measured at 100.0% requires a retriever scoring 120%. It can only ever be met
   below an 80% baseline, and this content class does not go there. **Deferred,
   n = 20**, with reasons in `.konjo/killtests/CortexSkis/KT-1-RERUN.md`. Running
   it again unchanged is wasted work. What would make it decisive: a corpus where
   decisions share vocabulary (the natural product of P-0b capture), an
   error-reduction threshold instead of absolute points, and blind question
   authorship. **Changing the threshold is its own decision -- it was not made in
   K4.** `Cortex-Projection-1` (no index) stands.

4. **`kt7-answer` is deleted.** Verified fully merged, then deleted from the
   local clone. `konjo-cortex` now has `main` only. Nothing left to do here.

5. **`konjo-skis` is published and verified end to end on real data.** `recall`
   and `longrun` are in claude.ai account Skills under author "You". Both halves
   of the recall contract were checked: on a surface with no repo access it
   correctly **refused** (cited its own read-path section, did not report "no
   record"); on a session with private repo access it answered correctly from
   the pushed pages -- `428f078209d4`, decided 2026-07-27, confidence 8/10, no
   chain, both rejected alternatives, and a current `projected-at`
   (`2026-08-19T15:01:48Z`). **Don't re-run this to "confirm" it.** The only
   thing untested is the phone as a form factor, using the same read path.

6. **Two pre-existing test failures are not yours and not new.** 3 failures in
   `konjo-newonly` / rust-gate absolute-path handling were present on a clean
   tree before K4 touched anything, and are unchanged. 365 pass.

## Open work

**1. P-0b. Capture decisions as they are taken.** The only item that matters.
Nothing mechanical blocks it -- the CLI works, the path is real, the fold and
push are automatic. What is missing is the habit. Log a call when you take one,
during the work, not in post-flight.

**2. Two recorded readability defects, neither fixed.** Both from K4's human read
(`Real-Data-1` Finding 5). (a) The two pre-existing `ONEWAY-ACK` events carry
shell-quoting debris in `rationale` -- a truncated `chore:` fragment -- meaning
the one-way-door hook interpolates an unescaped commit message into the field.
That is a live defect in the hook's write path; the debris in history is not
worth mutating, but the hook should stop producing it. (b) Pages order by `date`
(append order), not `decided_at`, so seeded history reads out of chronological
order. Changing it is a projection-format decision, not a tweak.

## Non-goals, unchanged from K1/K2/K3/K4

No embeddings, no vector index, no retrieval server -- `KT-1` killed it and K4
showed the re-run as written cannot revive it. No `decide` in `konjo-skis` --
writes stay laptop-only. No fabricated or script-generated events, in either
bucket. No backdating into the P-0b window. No claiming P-0 closed on the
strength of P-0a. No personal versus work scope split. No rewriting kiban's
gates, profiles, or language packages. No mutating the event stream from the
projection path -- cortex stays read-only, hand-edits to a page are a bug. No
touching `lopi`; it has its own queue. No merging
`claude/sign-distribution-channel-heg41d` without asking again.
