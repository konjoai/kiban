---
name: longrun
description: Make a long-running script (a benchmark, ablation, training loop, or eval matrix) resumable. Portable variant of kiban's longrun skill -- pure code-authoring guidance, no konjo-* CLI, no ~/.konjo. Use when writing or editing any script under benchmarks/ or a bench_*/train_* path.
---

# longrun (portable)

Any run long enough to be interrupted must resume from a checkpoint, not start
over. This is code-authoring guidance, not a runtime dependency on kiban's
CLI or `~/.konjo` -- the only thing kiban's own `longrun` skill needed to drop
to become portable was its self-update preamble line. Ported here unchanged
otherwise; if `gate_longrun` (kiban's CI gate) applies to the repo you're
working in, that gate itself still needs kiban's CLI to run -- this skill only
teaches the pattern the gate checks for.

This file and `plugins/konjo/skills/longrun/SKILL.md` are a declared pair
(`konjo-skis/CONTRACT.yml`, enforced by `bin/konjo-skis-check`). Sections
marked `skis-contract:*` below must stay in sync with their counterpart
there -- edit both, or the gate fails the build.

## The contract

<!-- skis-contract:longrun.contract -->
1. Accept `--resume` (resume from the latest checkpoint) and `--fresh` (ignore
   checkpoints and start clean). Exactly one is the script's default; the
   other is explicit.
2. Write a checkpoint after each unit of work (one config, one seed, one
   matrix cell), not only at the end.
3. On resume, read the progress file, compute the completed units, and skip
   them.
4. Be idempotent at the unit level: re-running a unit overwrites, not
   duplicates, its result.
<!-- /skis-contract:longrun.contract -->

## Adopt the helper, if the target repo has kiban installed

<!-- skis-contract:longrun.helper-code -->
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
<!-- /skis-contract:longrun.helper-code -->

If the target repo does not have `kiban` importable (a phone-authored script,
a repo that has never adopted kiban), implement the same four-point contract
by hand: any JSON-lines progress file with atomic appends and a
tolerant-on-read loader satisfies it. The contract is the point; the helper is
a convenience for repos that already have it.

## When to use

- Writing or editing a script under `benchmarks/**`, `**/bench_*.py`, or
  `scripts/train_*.py` (or a repo's declared `longrun_globs`).
- Any run that costs more than a few minutes and could be interrupted --
  including from a surface with no local kiban install, since the contract
  itself needs nothing beyond a JSON-lines file.
