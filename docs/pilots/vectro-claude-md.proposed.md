---
decays: intent
verified-against: f9dd8a1
verified-date: 2026-07-29
---

# Proposed `vectro/CLAUDE.md`, converted to the Phase 13 section contract

**Not applied.** This session's access to `konjoai/vectro` is read-only (added for
reconciliation research, not push). Applying this is a `konjoai/vectro` PR, not a
`kiban` one -- the same shape `docs/pilots/lopi-claude-md.proposed.md` used for lopi,
and the same reason `profiles/vectro.yml`'s `claude_contract` entry stays advisory
this sprint rather than flipping to blocking (see `LEDGER.md`'s
`Claude-Contract-Ramp-1`).

Converted against `vectro/CLAUDE.md` at `f9dd8a1` (main) and
`templates/repo-CLAUDE.md`'s section contract, in order.

## What changed and why

- **Title/description/version line**: kept, folded under "Repo-specific rules."
- **Stack**, **Commands**, **Crate Map** (renamed **Repo map**), **Python Modules**:
  kept verbatim.
- **Critical Constraints → Invariants**: every bullet now names its enforcement or
  says `ADVISORY`. Checked against vectro's real
  `.github/workflows/konjo-gate.yml` and `.konjo/hooks/pre-commit` (read this sprint,
  not assumed):
  - "No `unwrap()`/`expect()` outside tests" -- **enforced**: both the pre-commit
    hook and `konjo-gate.yml`'s G1 job run `cargo clippy -D clippy::unwrap_used -D
    clippy::expect_used` (the CI job additionally runs `-D clippy::pedantic`). The
    only bullet of the fourteen with a confirmed mechanical check.
  - The remaining thirteen bullets ("No silent failures," the SIMD cosine-similarity
    property-test requirement, dtype-explicit boundaries, FP32 accumulation, NaN/Inf
    assertions, Python-baseline numerical parity, the macOS-only feature-gating rule,
    the two output-directory-naming rules, seed logging, and the four-file version-
    bump rule) -- **ADVISORY**. Searched `.konjo/hooks/pre-commit` and
    `.github/workflows/konjo-gate.yml` for `tracing::warn`, `cosine`, `proptest`, and
    related tokens and found no matching check for any of them. Several of these
    (numerical parity across three backends, benchmark provenance, seed
    reproducibility) are exactly the kind of property a `konjo-prove`-style measured
    comparison could check, not a lint -- real future gate-building work, not
    something this conversion invents a check for.

  Net: **1 of 14 constraints have real mechanical enforcement today.** This is the
  most lopsided of the three real profiles reconciled against the Phase 13 contract
  so far (lopi: 1 of 6 checked at first read, since corrected to more by Sprint S13R;
  squish: 2 of 9). Not a defect in vectro particular -- it is the same "Critical
  Constraints" framing gap Phase 13 named for lopi, found again because this is the
  first time anything checked.
- **Planning Docs, Konjo Quality Framework, Skills**: kept verbatim under
  "Repo-specific rules," same reasoning as squish's proposal (the Quality Framework
  section documents Wall 1/2/3 usefully and doesn't duplicate a `.konjo/profile.yml`
  field, so it stays as prose rather than being deleted).
- **Org rules**: added per the template -- entirely absent before.

## Proposed file

```markdown
# vectro

Ultra-high-performance embedding compression library -- INT8 · NF4 · PQ-96 · Binary · HNSW · RQ · VQZ -- with Rust kernels, optional Mojo SIMD acceleration, and PyO3 Python bindings.

**v5.24.0** (Python) / **v8.17.0** (Rust) -- 1452 Python + 230 Rust tests passing.

## Org rules

@~/.konjo/kiban/plugins/konjo/skills/konjo/SKILL.md

The org ethos applies here: ship over optimize, kill-test first, statistical rigor,
honest negative results, evidence first, token-efficient context.

Editorial rules: no em dashes, no AI-tell vocabulary. The prose lint enforces it; run
`konjo-prose` on docs before pushing.

Log durable decisions with `konjo-decision decide` at `repo:vectro` scope. Search with
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
Rust 2021 · ndarray · rayon · simsimd · half · PyO3 · anyhow · criterion · Mojo (optional) · Python 3.10+ · NumPy · pixi

## Commands
```bash
cargo build                                  # build workspace
cargo test                                   # run all crate tests
cargo clippy -- -D warnings                  # lint
cargo bench --bench encode                   # criterion benchmarks
make bench-darwin-arm64 WAVE=1               # paper benchmark (Darwin arm64)
make bench-arxiv WAVE=1                      # full benchmark + notebook render
python -m pytest tests/ -x                   # Python test suite (1020 tests)
pixi install && pixi shell                   # Mojo environment (optional)
pixi run build-mojo                          # compile Mojo kernels (optional)
```

## Invariants
- No `unwrap()`/`expect()` outside tests -- use `anyhow::Result` and `?` -- `repo:clippy` (`-D clippy::unwrap_used -D clippy::expect_used`, pre-commit and CI)
- No silent failures -- log via `tracing::warn!` whenever a fallback swallows an error -- ADVISORY
- SIMD kernels require property tests: cosine ≥ 0.9999 on adversarial 1e6-magnitude inputs -- ADVISORY
- dtype explicit at every Rust/Python array boundary -- never rely on implicit casting -- ADVISORY
- Accumulate in FP32 for all quantized matmuls -- document any exception with a measured benchmark -- ADVISORY
- NaN/Inf assertion checks at module boundaries during development -- never ship masked overflow -- ADVISORY
- Python-only mode is always the correctness baseline -- Rust/Mojo acceleration must match it numerically -- ADVISORY
- `--features vectro_lib_accelerate` is macOS-only -- never gate correctness on it -- ADVISORY
- Benchmark results go to `benchmarks/results/` with timestamp + full hardware metadata -- never overwrite -- ADVISORY
- Experiment outputs in `experiments/runs/<timestamp>_<name>/` -- always new directory, never overwrite -- ADVISORY
- Seed all stochastic ops; log the seed in every benchmark JSON output -- ADVISORY
- Version bumps touch `pyproject.toml` + `python/__init__.py` + `python/vectro.py` + `rust/vectro_lib/Cargo.toml` -- ADVISORY

## Repo map
| Crate | Role |
|-------|------|
| `vectro_lib` | Core quantization kernels: INT8 (NEON 32-wide / AVX2 / AMX), NF4, PQ-96, Binary, HNSW, RQ, VQZ |
| `vectro_cli` | `vectro` CLI binary -- quantize, search, benchmark subcommands |
| `vectro_py` | PyO3 bindings -- `quantize_int8_batch` (zero-copy f32), `quantize_int8_batch_from_f16` |
| `generators` | Vector data generators for benchmarking and property testing |

## Repo-specific rules

### Python Modules
| Module | Role |
|--------|------|
| `python/vectro.py` | Main Python API: `AutoQuantize`, `HNSW`, all quantization modes |
| `python/quantization_extra.py` | INT2/INT4 bit-packing via NumPy (fallback path) |
| `benchmarks/vectro_paper_benchmark.py` | Reproducibility harness: `--quick / --table / --json / --reps / --warmup` |
| `scripts/aggregate_paper_tables.py` | Aggregates `results/paper/*.json` into paper tables |

### Planning Docs
- `PLAN.md` -- current sprint state and version history
- `VECTRO_V3_PLAN.md` -- v3 architecture audit and research landscape (Q1 2026)
- `VECTRO_OPTIMIZATION_AUDIT_2026-07.md` -- algorithm-layer audit (RaBitQ,
  quantization-graph fusion, ANN research 2024–2026); the unpark plan for
  when VECTRO resumes past the current kernel-tuning ceiling
- `CHANGELOG.md` -- all notable changes (Keep a Changelog format)
- `BACKLOG_v2.1.md` -- feature backlog

### Konjo Quality Framework

Three walls against AI slop.

**Wall 1 -- Pre-commit** (`bash .konjo/scripts/install-hooks.sh`):
cargo check, clippy, ruff lint, ruff format, DRY check, TODO scan. Blocks the commit.

**Wall 2 -- CI gate** (`.github/workflows/konjo-gate.yml`):
Coverage ≥ 80% · mutation survival ≤ 10% · complexity ≤ 15 · file ≤ 500L · zero DRY
violations. Blocks the merge.

**Wall 3 -- Adversarial review** (local only -- disabled in CI):
`git diff HEAD~1 | python3 .konjo/scripts/konjo_review.py`

See `KONJO_QUALITY_FRAMEWORK.md` for the full specification.

### Skills
See `.claude/skills/` -- auto-loaded when relevant.
Run `/konjo` to boot a full session (Brief + Discovery + Plan).
```

## What this session did NOT do

Same boundary as squish's proposal: no new detector gets built for any of the thirteen
ADVISORY findings this sprint. Several are real future `konjo-prove`-shaped candidates
(numerical parity across backends, seed reproducibility) rather than lint-shaped ones
-- flagged, not attempted, matching Phase 14's non-goal against "improving any gate."
