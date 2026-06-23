# Next session: Phase 1

## What Phase 0 built (0.1.0)

The foundation substrate and the squish pilot, all working and tested:

- `lib/jsonl_store.py`, `lib/redact.py`, `lib/prose_lint.py`.
- `ledger/engine.py` + `bin/konjo-decision`, with `ledger/schema.md`.
- `bin/konjo-prose`, `bin/konjo-newonly`.
- `install.sh`, `lib/self_update.sh`, the skill-preamble hook, the `konjo`/`decide`/
  `recall` skills.
- Profiles (`_schema.yml`, `squish.yml`, `_template.yml`), `defaults.yml`, templates.
- The eval fixtures (`dtype_promotion`, `_clean_control`).
- Docs (`README.md`, `docs/DISTRIBUTION.md`).

The kill-test passes: a fresh shell runs `install.sh`, then `konjo-prose` and
`konjo-decision` work from any directory with no further setup.

## Immediate Phase 1 tasks

Each has a stub with its contract already written; fill the logic.

1. **Eval harness** (`evals/runner.py`, `bin/konjo-eval`). Read each fixture, apply the
   gate to `diff.patch`, compare to `expect.json`, record detection_rate /
   false_positives / missed_bugs. Add the 30-run paired Wilcoxon (p < 0.05) prove
   baseline comparison.
2. **Parallel specialist engine** + `lib/specialist_stats.py`. Run the review lanes
   (numerics, memory-bandwidth, concurrency, api-surface), fold the review log into
   per-specialist hit rates, tag GATE_CANDIDATE / NEVER_GATE with a sample-size floor.
3. **One-way-door confirm flow** (`bin/konjo-oneway`). Classify hard-to-reverse changes
   and add the interactive confirm. This was a Phase 0 non-goal; build it here.
4. **Secrets interactive confirms**. Wire the MEDIUM-tier confirm flow on top of
   `lib/redact.py` (HIGH already blocks).
5. **Per-stack CI packages**. Make `konjo-gates-py` load a profile, select gates via
   `lib/diff_scope.py`, run them, and fail on regression. Then `konjo-gates-rs`
   (clippy + cargo-mutants) and `konjo-gates-js` (eslint + tsc + stryker).
6. **`lib/diff_scope.py`**. Map a changed-file list to the SCOPE_* booleans so the
   runner picks the minimal gate set per change.

## Not yet, still out

The Machine Room hub, cross-model review, web/design/iOS/browser tooling, and profiles
for the other eight repos (lopi, kohaku, kyro, kairu, toki, miru, vectro, squash,
@konjoai/ui). Roll those out repo by repo behind version pins, never all at once.
