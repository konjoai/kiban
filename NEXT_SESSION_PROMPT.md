# Next session: Phase 8 (the compounding loop)

## What Phase 7 built (0.7.0)

The pack seam landed and the first new language pack (Rust) shipped behind a second profile.

- The review engine split into an invariant core and opt-in language packs. The former
  `lib/specialists` moved verbatim into `lib/packs/lang`: the `_base` pack holds the
  `Specialist` machinery, `select`, the new `load_registry`, and the shared lanes
  (`concurrency`, `api-surface`, `red-team`); `mlx` holds `numerics` + `memory-bandwidth`;
  `python` is a placeholder (empty `SPECIALISTS`, a `TOOLS` fragment). The move was
  behavior-preserving: the six Squish cassettes still replay deterministically with no
  re-record.
- `review_diff` reads `packs` from the profile, or derives them from `stack` when absent
  (python -> lang/python, mlx -> lang/mlx, rust -> lang/rust), so `profiles/squish.yml`
  keeps working unchanged.
- The Rust pack (`lib/packs/lang/rust`): `ownership-lifetimes`, `error-handling`,
  `perf-alloc`, plus the reused shared lanes. Tools wired into the orchestrator: `clippy`,
  `fmt-check`, `cargo-deny`, `cargo-mutants` (all through konjo-newonly), and the
  kiban-native `unsafe-budget` gate (diff-only: a net rise in unsafe blocks with no safety
  comment fails).
- `SCOPE_TS` added to `diff_scope` (`.ts` / `.tsx` / `.mts`, in `CODE_SCOPES`). No TS lanes
  yet; the TS pack is Phase 12.
- Second profile `profiles/vectro.yml` (stack `[rust]`). VECTRO was NOT reachable from the
  build environment, so it is SEEDED with every unconfirmed field marked UNVERIFIED and the
  prove block PENDING, exactly as squish.yml was originally seeded.
- Rust eval corpus under `evals/fixtures/rust/` (five planted bugs, one clean control). The
  eval corpus is now profile-scoped via the `eval_corpus` field so each repo evaluates only
  its own fixtures.

## Carried activation steps

1. **Rust cassettes** — ACTIVATED in Phase 7 against a live model; the replay is
   deterministic across three runs and committed. No carried step. (If the lanes are ever
   reworded, re-record with `konjo-eval record --profile profiles/vectro.yml` and re-verify
   `konjo-eval run --replay --profile profiles/vectro.yml`.)
2. **VECTRO reconciliation** — when VECTRO unparks, clone it read-only and reconcile
   `profiles/vectro.yml`: confirm the stack, the format/lint and contract tools, and the
   LOAD-BEARING prove fields (metric, unit, bench_cmd, perf_globs). Clear every UNVERIFIED.
3. **Squish prove gate** — still PENDING on the M3 bench hardware (carried from Phase 5):
   capture >= 30 paired runs, measure jitter, set and confirm `min_effect_pct`, capture the
   golden baseline.

## Phase 8 tasks (the compounding loop)

The highest-leverage missing piece (evolution plan section 5b). When the agent errs, do not
just correct it in chat; write a durable rule so it never recurs.

1. A learnings stream on the substrate (`lib/learnings.py` or a Ledger stream): one-line
   mistake, the rule that prevents it, the repo scope, and a pointer to where the rule now
   lives. Append-only, redact-scanned, same as the Ledger.
2. A `correct` skill: write the learning, propose the smallest durable fix (a CLAUDE.md
   rule, a prose-lint word, a new specialist check, or a gate), and apply on confirm.
3. Extend `recall` to search learnings, not just decisions.
4. Kill-test: a correction writes a learning; a learning names an enforcement target; a
   learning with no target is refused.

Guardrail: a learning must name where its rule lives, or it is a note, and notes do not go
in the log.

## Tag and release discipline (in force)

`release.yml` cuts the release and tag server-side on a VERSION change on main. Every
VERSION bump is a one-way door: classify and confirm it. The build environment cannot push
tag refs.

## Still out, permanently

The Machine Room hub, cross-model review as a default, web/design/iOS/browser tooling,
psychographic/profile-tuning behavior, completeness-toward-10 defaults, the plugin
marketplace, and "boil the ocean" completeness.
