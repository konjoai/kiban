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
- **Phase 3+**: the one-way-door confirm flow, the MEDIUM-secret interactive confirm, the
  30-run paired Wilcoxon prove baseline, and `konjo-gates-rs`/`-js`. Stubbed with their
  contracts in place. See `NEXT_SESSION_PROMPT.md`.

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
