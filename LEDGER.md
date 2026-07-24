# Ledger

A running log of load-bearing design decisions — the ones that would be expensive to
silently re-litigate in a later sprint. One entry per sprint, newest first. Not a
changelog (that's `CHANGELOG.md`) — this is *why*, not *what*. (kiban's runtime
decision Ledger — `ledger/engine.py`, `bin/konjo-decision` — records the durable calls
a *consuming* repo makes during a session, scoped `org`/`repo:<name>`, in
`~/.konjo/state/ledger/decisions.jsonl`; this file is kiban's own project-level
record of its architecture, the way `lopi`'s `LEDGER.md` records lopi's.)

## Doc-Integrity-Gate-1 — the konjo-* plane decision, and the Konjo-Doc-Verified trailer

**The konjo-* skill family is absorbed into the global plane — a one-way door,
confirmed with Wes before any code was written, not decided by the agent.** A
source-level audit of `konjoai/lopi` @ `63908a5` found `docs/LOOP_ENGINEERING_ROADMAP.md`
asserting four capability gaps (no MCP, no real worktrees, no runtime skill engine, no
maker/checker split) all closed on `main`. The cause: `konjo-ship/SKILL.md`'s Sprint
Completion Checklist names three filenames (`CHANGELOG.md`, `PLAN.md`, `README.md`);
the roadmap is on none of them and referenced by no skill or instruction file anywhere
in the repo, so it decayed unnoticed. Pre-flight verified, not assumed, before this
call: (1) `konjo-ship` has no canonical source anywhere in `kiban` — the whole tree was
grepped; (2) `lib/self_update.sh` fast-forwards only the global clone at
`$KONJO_HOME/kiban`, never a consuming repo's `.claude/skills/` — read line by line,
not inferred; (3) `konjo-ship/SKILL.md` is byte-identical between `konjoai/lopi` and
`konjoai/miru` (`diff -rq`, zero output) — a hand-copy that has never been re-synced,
across two repos in two different languages (`lopi` is Rust, the checklist's own
`cargo test`/`cargo clippy` lines were wrong for `miru` the whole time). Three options
were on the table: absorb the family into `plugins/konjo/skills/` (single source,
auto-distributed, per-repo customization needs a designed override path); keep the
per-repo plane and build a sync mechanism (preserves tailoring, costs a second
distribution path); or hand-edit `lopi`/`miru` now (rejected by the brief itself — it
reproduces the exact bug this sprint exists to fix). Wes chose absorption. Consuming
repos will start depending on wherever this lands, which is what makes it one-way:
reversing it later means re-forking `konjo-ship` back out to N repos by hand, the thing
this decision exists to stop doing. This sprint moves `konjo-ship` itself
(`plugins/konjo/skills/konjo-ship/SKILL.md`, generalized off Rust-only commands and
off lopi-specific branding) and documents the override path (a repo-scoped
`.claude/skills/<name>/SKILL.md` wins over an identically-named global skill, per
Claude Code's own resolution rule — no new plumbing needed). The other four
(`konjo-boot`, `konjo-philosophy`, `konjo-quality`, `konjo-retrofit`) are not migrated
here; `konjo-quality`/`konjo-retrofit` are Rust-quality-framework specific and need real
generalization, not a file move — see `NEXT_SESSION_PROMPT.md`. `lopi` and `miru` still
carry their local `.claude/skills/konjo-ship/` copies, now shadowing the global one for
those two repos until each repo's own sprint removes its stale local copy; hand-editing
consuming repos is explicitly not this sprint's job.

**`Konjo-Doc-Verified` joins the record-and-check trailer family
(`Konjo-Acknowledged-Oneway`, `Konjo-Prove-Merge`) — same fingerprint scheme, not a
fourth ad hoc format.** `lib/doc_staleness.py` is the mechanism behind the
`decays:` front-matter convention (`plugins/konjo/skills/craft/SKILL.md`): a `state`
doc fails once `verified-against` falls too far behind `HEAD` (default 20 commits / 14
days), and fails hard if `verified-against` is missing at all — the unstamped case that
caused this whole sprint. `historical` docs (`CHANGELOG.md`, `LEDGER.md`, dated audits)
are exempt from staleness by declaration, `intent`/`reference` are warn-only regardless
of age, matching the four classes' actual horizons rather than one blanket rule. The
trailer reuses `oneway.make_trailer`/`oneway.find_trailer` and
`oneway.fingerprint(doc_paths)` — the same fingerprint every other Konjo trailer keys
on — rather than inventing new plumbing. Verified against real drift, not just
synthetic fixtures: run against a real clone of `konjoai/lopi`, the checker correctly
reports 0/72 docs have adopted the convention yet (an honest finding, not a bug — lopi
hasn't opted in, so everything legitimately `SKIP`s); a scratch copy of
`docs/LOOP_ENGINEERING_ROADMAP.md` stamped as it would have been at the commit that
introduced it (`f91b111`, 2026-06-22, the only commit that has ever touched that file)
fails loudly: 440 commits / 32 days behind `HEAD`, on a doc whose four claimed gaps are
all closed at that same `HEAD`. This sprint does not stamp or reclassify any of lopi's
docs — that is lopi's own sprint's job, flagged in `NEXT_SESSION_PROMPT.md`, not this
one's, per the brief's explicit scope line: "do not reclassify lopi's docs from here."
