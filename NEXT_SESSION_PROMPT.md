# Sprint K5 shipped. Two real-device checks are the only open items.

Sprint K5 moved the Ledger's canonical home from a laptop-only
`~/.konjo/state/ledger/decisions.jsonl` into `$KONJO_CORTEX_DIR/ledger/events/`, one
file per event. Any surface with `konjo-cortex` checked out can now write and read.
Full reasoning: `LEDGER.md`'s `Ledger-Laptop-Only-1` and `Ledger-Events-Per-File-1`,
`CHANGELOG.md` `[1.20.0]`.

**What a session in this repo cannot advance, and should not try to:**

1. **KT-9's literal M3 leg.** `.konjo/killtests/LedgerEvents/KT-9.md` is PASS: code
   audit, positive control, same-environment repeatability, and a real
   cross-machine check -- this sandbox and a GitHub Actions runner independently
   folded the same `konjo-cortex` commit (`9bb778c`) to byte-identical markdown,
   confirmed by reading the runner's own job log. The one thing no cloud session
   can do is fold on the actual M3 and diff against those same hashes. If you're
   reading this from a session that *does* have M3 access: run the fold there
   against that commit (or whatever's current), confirm the hash matches, and
   append that to KT-9's verdict. If you're a cloud session: don't attempt this,
   say so, move on.
2. **KT-11: the phone write path.** `.konjo/killtests/LedgerEvents/KT-11.md` is
   BLOCKED, not attempted -- structurally the phone write path is the same code as
   the laptop/cloud path (no invocation-surface branch in
   `konjo-decision`/`lib/cortex_sync.py`), but that's an argument, not a test. Real
   phone, real Cowork task, real push, real laptop pull-and-read -- the file names
   the exact five steps. A session with no device-control path to a real phone
   should not attempt this either; report the number of scoped-out legs (still 1)
   and stop, the same discipline the old P-0b note asked for.

**Both are the same shape of open item the old P-0b note described: a session cannot
manufacture the evidence, only report honestly that it's still open.** Don't try to
close either with a structural argument dressed up as a real result -- that's
exactly the failure mode `.konjo/killtests/TEMPLATE.md` exists to prevent.

**P-0b itself (real decisions captured as work happens, not transcribed) still
applies and is unaffected by this sprint** -- it was never about where the Ledger
lives, only about whether real usage exists. Check it the same way as before:

```bash
python3 - <<'PY'
from ledger.engine import Ledger
CLOSE = "2026-08-19T15:16:52Z"
f = Ledger()._fold()
p0b = [d for d in f if d.decided_at > CLOSE]
print(f"P-0b events since K4 close: {len(p0b)}")
for d in p0b:
    print(f"  {d.decided_at}  {d.scope:12s}  {d.decision[:60]}")
PY
```

Note this now reads from `Ledger()`'s new default (`$KONJO_CORTEX_DIR/ledger/events`,
not `~/.konjo/state`) -- set `KONJO_CORTEX_DIR` to a real local `konjo-cortex` clone
before running it, or pass an explicit path.

**Until KT-9's M3 leg and KT-11 close, or P-0b reaches the old trigger (15 events
across 2+ scopes), kiban gets bug fixes only.** No new gates, skills, or contract
sections -- same standing rule as before this sprint, restated because the sprint
that just shipped is a real exception to "dormant," not a reopening of the general
rule.
