---
name: longrun
description: Make a long-running script (a benchmark, ablation, training loop, or eval matrix) resumable. Adopt the checkpoint/resume contract so an interrupted run continues with minimal loss. Use when writing or editing any script under benchmarks/ or a bench_*/train_* path.
---

# longrun

Any run long enough to be interrupted must resume from a checkpoint, not start over. This is
the operational floor for benchmarks, ablations, training loops, and eval matrices, not
gold-plating. The `gate_longrun` CI gate enforces it on changes to long-run scripts; this
skill is how you satisfy it.

## Self-update preamble (run first)

```bash
bash "$HOME/.konjo/kiban/plugins/konjo/hooks/preamble_update.sh"
```

## The contract

1. Accept `--resume` (resume from the latest checkpoint) and `--fresh` (ignore checkpoints
   and start clean). Exactly one is the script's default; the other is explicit.
2. Write a checkpoint after each unit of work (one config, one seed, one matrix cell), not
   only at the end.
3. On resume, read the progress file, compute the completed units, and skip them.
4. Be idempotent at the unit level: re-running a unit overwrites, not duplicates, its result.

## Adopt the helper (about five lines)

```python
import argparse
from lib.packs.longrun import konjo_longrun

p = argparse.ArgumentParser()
konjo_longrun.add_resume_args(p, default_fresh=False)   # resume by default
args = p.parse_args()

ckpt = konjo_longrun.Checkpoint(progress_path, fresh=konjo_longrun.is_fresh(args))
for unit in units:
    key = unit_key(unit)            # a stable fingerprint of the unit's parameters
    if ckpt.done(key):
        continue
    ckpt.mark(key, run_unit(unit))
```

The progress file is one JSONL on the `jsonl_store` substrate: atomic appends, redact-scanned,
and tolerant on read (one corrupt line never bricks the resume). Pass an absolute
`progress_path` to control where it lands.

## What the gate checks

`gate_longrun` is a static check on the diff: it confirms a changed long-run script wires a
resume affordance (`--resume` or the `konjo_longrun` helper) and a checkpoint write
(`Checkpoint(...)` / `.mark(...)`). It never runs the script. A static check confirms the
resume path exists, not that it is correct; the resume kill-test is what proves correctness.

## When to use

- Writing or editing a script under `benchmarks/**`, `**/bench_*.py`, or `scripts/train_*.py`
  (or a repo's declared `longrun_globs`).
- Any run that costs more than a few minutes and could be interrupted.
