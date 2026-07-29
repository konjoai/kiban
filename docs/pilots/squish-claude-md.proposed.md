---
decays: intent
verified-against: 4dd6f62
verified-date: 2026-07-29
---

# Proposed `squish/CLAUDE.md`, converted to the Phase 13 section contract

**Not applied.** This session's access to `konjoai/squish` is read-only (added for
reconciliation research, not push). Applying this is a `konjoai/squish` PR, not a
`kiban` one -- the same shape `docs/pilots/lopi-claude-md.proposed.md` used for lopi,
and the same reason `profiles/squish.yml`'s `claude_contract` entry stays advisory
this sprint rather than flipping to blocking (see `LEDGER.md`'s
`Claude-Contract-Ramp-1`).

Converted against `squish/CLAUDE.md` at `4dd6f62` (main) and
`templates/repo-CLAUDE.md`'s section contract (`## Org rules`, `## Stack`,
`## Commands`, `## Invariants`, `## Repo map`, `## Repo-specific rules`, in that
order).

## What changed and why

- **Title/description/version line**: kept, folded under "Repo-specific rules."
- **Stack**, **Commands**: kept verbatim.
- **Module Map** (renamed **Repo map**): kept verbatim.
- **Critical Constraints → Invariants**: every bullet now names its enforcement or
  says `ADVISORY`. Checked against squish's real `.konjo/hooks/pre-commit` (Wall 1)
  and `.github/workflows/model_pipeline.yml` (read this sprint, not assumed):
  - "No `unwrap()`/`expect()` in Python" and "No silent failures" -- **enforced by
    the same check**: pre-commit's "2c. silent error swallowing scan" greps staged
    Python files for `except:` / `except Exception:` and fails the commit. Python has
    no `unwrap()`/`expect()` to scan for directly; the bare/broad-except shape is this
    codebase's equivalent defect, and one check catches both bullets.
  - "Quantization accuracy gates are hard stops" -- **enforced**:
    `model_pipeline.yml`'s "Compress and validate -- accuracy gate" job runs on every
    candidate compression.
  - "MLX imports must be gated behind platform check" -- **ADVISORY**. No pre-commit
    or CI step checks this; searched `.konjo/hooks/pre-commit` and the workflow
    directory for a platform-import guard and found none.
  - "`squish.squash` is now an optional import" -- **ADVISORY**. No check found.
  - "Pre-scan HF models before loading weights" -- **ADVISORY**. No check found (this
    is a runtime-ordering property, not something a static pre-commit/CI step can
    easily assert).
  - "Prompt injection: system prompt content must never be controllable by request
    payload" and "Never log raw user prompt content at INFO level or above" --
    **ADVISORY**. The only place either concern appears in the repo is
    `.konjo/scripts/konjo_review.py` (Wall 3, adversarial review) -- and squish's own
    CLAUDE.md already states Wall 3 is "local only -- disabled in CI." A check that
    does not run in CI is not a check a PR can rely on; naming it ADVISORY here is
    honest, not a downgrade.
  - "Version bumps touch `pyproject.toml` + `squish/__init__.py`" -- **ADVISORY**, a
    workflow property, not a diff-checkable rule (same treatment lopi's proposal gave
    "`cargo build` must stay green").

  Net: **2 of 9 constraints have real mechanical enforcement today** (the silent-
  failure scan covers two of the original bullets under one check). This is a lower
  enforced fraction than lopi's 1-of-6-but-differently-counted finding, though the two
  aren't directly comparable (different bullet counts, different codebases) -- the
  shape is the same: a "Critical Constraints" list mixing checked and merely-hoped-for
  rules with no visible distinction before this conversion.
- **Planning Docs**: kept verbatim under "Repo-specific rules."
- **Konjo Quality Framework, Skills**: kept verbatim under "Repo-specific rules" --
  this section already documents Wall 1/2/3 in useful detail; converting it into
  `contract_gates`-style bullets would duplicate `profiles/squish.yml` without adding
  information, so it stays as prose here instead of being deleted (unlike lopi's
  "Additional Hard Rules," which duplicated numbers already declared in
  `.konjo/profile.yml` and was cut for that reason -- squish's section doesn't
  duplicate a profile field).
- **Org rules**: added per the template -- entirely absent before.

## Proposed file

```markdown
# squish

Local LLM inference server -- MLX-accelerated on Apple Silicon, with speculative decoding, quantization (INT4/INT3/SQINT2), agent tool execution, Ollama/OpenAI-compatible API, and the macOS SquishBar.

**v9.34.2**

## Org rules

@~/.konjo/kiban/plugins/konjo/skills/konjo/SKILL.md

The org ethos applies here: ship over optimize, kill-test first, statistical rigor,
honest negative results, evidence first, token-efficient context.

Editorial rules: no em dashes, no AI-tell vocabulary. The prose lint enforces it; run
`konjo-prose` on docs before pushing.

Log durable decisions with `konjo-decision decide` at `repo:squish` scope. Search with
`konjo-decision search` before reopening a settled call.

When you catch a mistake worth not repeating, invoke `correct`: it records a learning
with `konjo-learn` and proposes the smallest durable fix. A learning must name where
its rule lives (a CLAUDE.md line, a prose-lint word, a lane, or a gate), or it is
refused.

Build the Konjo way: the `craft` skill carries the four behaviors (think before coding,
simplicity first, surgical changes, goal-driven execution) plus the verify-loop and the
pre-implementation trust-boundary contract. `verify_cmd` is declared in
`.konjo/profile.yml`.

## Stack
Python 3.10+ · MLX + mlx-lm (Apple Silicon) · FastAPI · transformers · HuggingFace Hub · Swift (macOS SquishBar)

## Commands
```bash
python -m pytest tests/ -x                   # full test suite
python -m pytest tests/ -x -k "test_name"    # run a single test
python -m squish serve                        # start inference server
squish pull hf:<repo>                         # download + pre-scan HF model
squish trace                                  # observability report
squish compat                                 # backend compatibility check
```

## Invariants
- No `unwrap()`/`expect()` in Python and no silent failures -- `repo:pre-commit "silent error swallowing scan"` (blocks the commit on bare/`Exception`-wide `except`)
- Quantization accuracy gates are hard stops: INT4 AWQ g=32 ≥ 70.6% arc_easy (Qwen2.5-1.5B); INT2 naive is **NEVER SHIP** -- `repo:model_pipeline.yml` "Compress and validate -- accuracy gate"
- MLX imports must be gated behind platform check -- never imported on Linux paths -- ADVISORY
- `squish.squash` is an **optional** import -- never hard-depend on `squash-ai` -- ADVISORY
- Pre-scan HF models **before** loading weights -- `HFFileSummary` scan runs at `squish pull hf:` time -- ADVISORY
- Prompt injection: system prompt content must never be controllable by request payload -- ADVISORY (only checked by Wall 3, which is disabled in CI)
- Never log raw user prompt content at INFO level or above -- log a hash or truncated prefix -- ADVISORY (same reason)
- Version bumps touch `pyproject.toml` + `squish/__init__.py` -- ADVISORY

## Repo map
| Module | Role |
|--------|------|
| `squish/server.py` | FastAPI app entry point, startup profiler, backend routing |
| `squish/cli.py` | `squish` CLI -- serve, pull, trace, compat, agent |
| `squish/catalog.py` | Model registry: URI parsing (`ollama:` / `hf:`) + HF batch upload |
| `squish/serving/` | Backend router, Ollama/LocalAI compat, blazing TTFT, tool calling |
| `squish/hardware/` | Platform detector, production profiler, Apple Silicon routing |
| `squish/api/` | OpenAI-compatible v1 router |
| `squish/agent/` | Agent loop, tool name map, tool execution |
| `squish/quant/` | AWQ/INT3/INT4/SQINT2 quantization pipeline |
| `squish/kv/` | KV cache management |
| `squish/context/` | Context window management |
| `squish/platform/` | Cross-platform router and detector |
| `apps/macos/SquishBar/` | Swift macOS menu bar app (model picker, progress, hotkey) |

## Repo-specific rules

### Planning Docs
- `MODULES.md` -- per-wave module reference (Waves 1–99+)
- `CHANGELOG.md` -- all notable changes

### Konjo Quality Framework

Three walls against AI slop.

**Wall 1 -- Pre-commit** (`bash .konjo/scripts/install-hooks.sh`):
ruff lint, ruff format, bare-except scan, DRY check, TODO scan. Blocks the commit.

**Wall 2 -- CI gate** (`.github/workflows/konjo-gate.yml`):
Coverage ≥ 80% · mutation survival ≤ 10% · complexity ≤ 15 · file ≤ 500L · zero DRY
violations. Blocks the merge. The 500L gate is blocking for **new** files; legacy
oversized files are grandfathered in `.konjo/oversized-allowlist.txt` (split them to
remove, don't grow the list).

**Wall 3 -- Adversarial review** (local only -- disabled in CI):
`git diff HEAD~1 | python3 .konjo/scripts/konjo_review.py`

See the `konjo-quality` skill (`.claude/skills/konjo-quality/`) for the full
specification.

### Skills
See `.claude/skills/` -- auto-loaded when relevant.
Run `/konjo` to boot a full session (Brief + Discovery + Plan).
```

## What this session did NOT do

Same boundary lopi's Phase 0 drew: this is a section-contract conversion, not a gate
improvement. None of the seven ADVISORY findings above get a new detector built this
sprint -- wiring one (an MLX-import-location linter, a prompt-payload-taint check, a
log-level content scanner) is new detector-building work, out of Phase 14's scope.
