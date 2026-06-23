# Changelog

All notable changes to kiban are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-23

Phase 0: the foundation substrate plus the squish pilot, with specified Phase 1+ stubs.

### Added

- Shared substrate:
  - `lib/jsonl_store.py`: atomic append-only JSONL store, injection-rejected,
    redact-scanned, tolerant read.
  - `lib/redact.py`: three-tier secret scanner (HIGH blocks, MEDIUM confirms, LOW
    surfaces), no MEDIUM-to-HIGH promotion.
  - `lib/prose_lint.py`: editorial lint (em dashes and the AI-tell wordlist).
- Konjo Ledger:
  - `ledger/engine.py`: event-sourced decide/supersede/redact with computed "active".
  - `ledger/schema.md`: the event schema and org/repo scoping.
  - `bin/konjo-decision`: the Ledger CLI.
- CLIs:
  - `bin/konjo-prose`: prose lint over files and globs, blocking and `--warn` modes.
  - `bin/konjo-newonly`: net-new-findings-only wrapper for strict gates on existing code.
- Distribution:
  - `install.sh`: clone-or-update to `~/.konjo/kiban`, create `~/.konjo/state`.
  - `lib/self_update.sh`: throttled, failure-safe, pin-aware fast-forward self-update.
  - `plugins/konjo/hooks/preamble_update.sh`: the skill-preamble update hook.
- Session plane skills: `konjo` (umbrella), `decide`, `recall`.
- Profiles: `_schema.yml`, `squish.yml` (seeded, unverifiable fields marked UNVERIFIED),
  `_template.yml`.
- Org defaults (`defaults.yml`) and consuming-repo templates (`templates/`).
- Eval corpus: `evals/README.md`, the `dtype_promotion` and `_clean_control` fixtures.
- Docs: `README.md`, `docs/DISTRIBUTION.md`, `docs/design/`.
- Tests for the substrate, Ledger, prose lint, and self-update.

### Stubbed (Phase 1+, contract specified, no logic)

- `bin/konjo-eval`, `bin/konjo-oneway`.
- `lib/diff_scope.py`, `lib/specialist_stats.py`.
- `evals/runner.py`.
- `packages/konjo-gates-py`, `-rs`, `-js`.

[0.1.0]: https://github.com/konjoai/kiban/releases/tag/v0.1.0
