# kiban

基盤 (kiban): literally "the foundation/platform/infrastructure everything rests on."

kiban is the single source of truth for Konjo AI's org-wide quality and memory tooling.
It is the repo every other Konjo repo inherits from. It houses two paired frameworks on
one shared substrate:

- **KCQF**: quality enforcement. Blocks defects mechanically and tests itself.
- **Konjo Ledger (kledger)**: epistemic memory. An append-only decision log with
  kill-test verdicts, prove verdicts, and learnings. The lab notebook.
- **Shared `jsonl-store`**: injection-hardened, atomic, redact-scanned append-only
  store under both.

## Naming

The repo is `kiban`. The commands, skills, and CI packages it ships keep the Konjo
brand: `konjo-decision`, `konjo-prose`, `konjo-newonly`, the `/konjo` skill,
`konjo-gates-py`. kiban is the foundation; `konjo-*` are the tools it provides.

## Install (gstack-style)

One plain git clone per machine to `~/.konjo/kiban`. No plugin marketplace.

```bash
git clone https://github.com/konjoai/kiban.git ~/.konjo/kiban
~/.konjo/kiban/install.sh
# then add the printed line to your shell rc:
export PATH="$HOME/.konjo/kiban/bin:$PATH"
```

After that, the CLIs work from any directory:

```bash
konjo-prose docs/*.md
konjo-decision decide --decision "..." --rationale "..." --confidence 8 --author you
konjo-decision search "distribution"
```

Each skill runs a throttled, failure-safe `git pull` self-update in its preamble, so the
clone stays current without a marketplace.

## Two planes

- **Session plane**: skills, hooks, and CLAUDE.md rules read from the global clone at
  `~/.konjo/kiban`.
- **CI plane**: the blocking gates ship as pinned, installable packages
  (`packages/konjo-gates-*`) that each consuming repo's CI installs and runs. CI never
  reads `~/.konjo`.

Ledger state lives in `~/.konjo/state`, outside the clone, so updates never touch it. It
syncs across machines via a separate redact-scanned private repo. See
`docs/DISTRIBUTION.md`.

## Pinning discipline

A consuming repo pins a kiban ref (`.konjo/kiban.ref` for the session plane, `KIBAN_REF`
in CI). A master change then rolls out repo by repo on a deliberate schedule by bumping
each pin, never all repos at once.

## Phase map

- **Phase 0 (0.1.0)**: the substrate (`jsonl_store`, `redact`, `prose_lint`), the Ledger
  engine and `konjo-decision`, `konjo-prose`, `konjo-newonly`, install and self-update,
  the skills and hooks, profiles, templates, and the eval fixtures.
- **Phase 1 (this release, 0.2.0)**: the meta-gate. The keystone `review_diff` interface,
  the parallel specialist engine (`lib/specialists/`), `diff_scope`, the review log,
  specialist-stats, and the eval harness that regression-tests the gate
  (`konjo-eval`, `konjo-review`, `konjo-stats`). Working and tested; the kill-test passes.
- **Phase 2 (this release, 0.3.0)**: the CI plane enforces. The `konjo-gates` orchestrator
  (`packages/konjo-gates-py`) routes changed files through `diff_scope` and runs the
  kiban-native gates (prose, secrets, the self_test replay eval, report-only specialist
  stats) plus the profile's repo-native gates, each wrapped in `konjo-newonly`. The eval
  runs deterministically offline via recorded cassettes (`konjo-eval record` /
  `run --replay`). Working and tested; the kill-test passes with no model and no network.
- **Phase 3 (this release, 0.4.0)**: the safety layer. The one-way-door classifier
  (`lib/oneway.py`, `konjo-oneway`), the typed-confirm flow (`lib/confirm.py`) that logs
  an acknowledgement and emits a commit trailer, the MEDIUM-secret confirm
  (`konjo-secrets`), and the CI `one_way_door` gate that checks the trailer without
  prompting. Plus the release-tag discipline. Working and tested; the kill-test passes.
- **Phase 4 (this release, 0.5.0)**: the prove gate. A 30-run paired Wilcoxon signed-rank
  perf test (`lib/prove.py`, `konjo-prove`) that renders MERGE / NOISE / REGRESSION, where
  significance alone never merges. It runs locally on the bench hardware and records a
  MERGE trailer; the CI `prove` gate checks the trailer and runs no benchmark. Working and
  tested; the kill-test passes.
- **Phase 5 (this release, 0.6.0)**: the squish pilot is complete. The eval corpus covers
  all four squish specialists (numerics, memory-bandwidth, concurrency, api-surface), and
  the squish prove gate is wired against the real benchmark (`lib/bench_squish.py`,
  `konjo-prove adapt`) and stays honestly NOT ACTIVATED until its threshold is confirmed.
- **Phase 7 (this release, 0.7.0)**: the pack seam plus the first new language pack. The
  review engine split into an invariant core and opt-in language packs (`lib/packs/lang`):
  `_base` (the shared machinery and lanes), `mlx` and `python` (the repackaged Squish
  content), and a new `rust` pack (`ownership-lifetimes`, `error-handling`, `perf-alloc`,
  the `unsafe-budget` gate, and the cargo tool table). A second repo profile
  (`profiles/vectro.yml`, Rust) proves the schema generalizes. The Squish cassettes moved
  verbatim and still replay deterministically with no re-record. Working and tested.
- **Phase 8+**: the compounding loop (learnings log + `correct` skill), the long-run gate,
  the craft skill, then `konjo-gates-js` and the context-budget gate. See
  `NEXT_SESSION_PROMPT.md`.

## Proving a perf change

A perf claim needs a verdict, not a vibe. On the bench hardware, produce a paired
measurement artifact with the repo's benchmark, then run
`konjo-prove run --results <artifact> --profile <profile>`. It computes the paired
Wilcoxon test and renders MERGE only when the result is significant AND the median
improvement clears the minimum effect size. A MERGE prints a commit trailer; the CI
`prove` gate checks for it on a perf-labeled change and never runs the benchmark itself.

## Irreversible changes

A one-way door (schema migration, public-API removal, data delete, key rotation, a
release) needs an explicit acknowledgement, not an automatic block. Run
`konjo-oneway confirm --files ...`: it states what is irreversible, requires a typed
confirmation and a justification, logs the call to the Ledger, and prints a commit
trailer. The CI `one_way_door` gate checks for that trailer and never prompts.

## Gates in CI

A consuming repo installs the pinned kiban distribution and runs `konjo-gates` against
its `.konjo/profile.yml` (see `templates/repo-ci.yml`). The CI plane never reads
`~/.konjo`; the gate logic and eval cassettes ship with the pinned package, so CI needs
no model and no network.

## Reviewing a diff

```bash
konjo-review --base origin/main              # review the working diff, log the run
konjo-eval --runs 3                          # regression-test the gate against the corpus
konjo-stats --branch <branch>                # per-specialist gate verdicts
```

## Ethos

Ship over optimize. Kill-test first. Statistical rigor. Honest negative results.
Evidence first, not deference. Token-efficient context.

## License

MIT. See `LICENSE`.
