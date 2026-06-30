#!/usr/bin/env bash
# Phase 9 kill-test: the checkpoint/resume contract must hold with NO `claude` and NO
# network. A synthetic 5-unit run is killed after unit 3, resumed, and must skip units 1-3,
# complete 4-5, and match a clean --fresh run. Plus a corruption case: a garbage line in the
# progress file must not break resume (the tolerant-read property of jsonl_store.iter_read).

set -u

KIBAN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
FAKE_HOME="$(mktemp -d)"
STATE="$(mktemp -d)"
trap 'rm -rf "$WORK" "$FAKE_HOME" "$STATE"' EXIT

fail() { echo "FAIL: $1"; exit 1; }
pass() { echo "ok: $1"; }

# A synthetic long-run script that adopts the konjo_longrun helper. STOP_AFTER simulates a
# crash after marking that many NEW units this invocation.
cat > "$WORK/run.py" <<'PY'
import argparse, os, sys
sys.path.insert(0, os.environ["KIBAN_ROOT"])
from lib.packs.longrun import konjo_longrun as kl

p = argparse.ArgumentParser()
kl.add_resume_args(p, default_fresh=False)   # resume is the default
p.add_argument("--progress", required=True)
args = p.parse_args()

ckpt = kl.Checkpoint(args.progress, fresh=kl.is_fresh(args))
stop_after = int(os.environ.get("STOP_AFTER", "0"))
ran = []
for i in range(5):
    key = f"u{i}"
    if ckpt.done(key):
        continue
    ckpt.mark(key, f"r{i}")
    ran.append(key)
    if stop_after and len(ran) >= stop_after:
        sys.stderr.write("RAN " + ",".join(ran) + "\n")
        sys.exit(1)   # simulate a crash mid-run
sys.stderr.write("RAN " + ",".join(ran) + "\n")
print("COMPLETE " + ",".join(sorted(ckpt.completed())))
PY

CLAUDE_BIN="$(command -v claude || true)"
CLEAN_PATH="$PATH"
if [ -n "$CLAUDE_BIN" ]; then
  CLAUDE_DIR="$(dirname "$CLAUDE_BIN")"
  CLEAN_PATH="$(echo "$PATH" | tr ':' '\n' | grep -vx "$CLAUDE_DIR" | paste -sd: -)"
fi

run_py() {
  # shellcheck disable=SC2086
  env -u ANTHROPIC_BASE_URL -u ANTHROPIC_API_KEY \
    HOME="$FAKE_HOME" KONJO_STATE_DIR="$STATE" KIBAN_ROOT="$KIBAN_ROOT" PATH="$CLEAN_PATH" \
    python "$WORK/run.py" "$@"
}

PROG="$WORK/progress.jsonl"

# ---- 1. interrupted run: killed after unit 3 ---------------------------------
ERR="$(STOP_AFTER=3 run_py --progress "$PROG" 2>&1 1>/dev/null)"; RC=$?
[ "$RC" -ne 0 ] || fail "the interrupted run should exit nonzero"
echo "$ERR" | grep -q "RAN u0,u1,u2" || { echo "$ERR"; fail "first run should have run units 0-2"; }
pass "the run is interrupted after three units"

# ---- 2. resume: skips 1-3, completes 4-5 -------------------------------------
OUT="$(run_py --progress "$PROG" 2>"$WORK/err2")"; RC=$?
[ "$RC" -eq 0 ] || { cat "$WORK/err2"; fail "resume should exit 0"; }
grep -q "RAN u3,u4" "$WORK/err2" || { cat "$WORK/err2"; fail "resume should run only units 3-4 (1-3 skipped)"; }
echo "$OUT" | grep -q "COMPLETE u0,u1,u2,u3,u4" || { echo "$OUT"; fail "resume should complete all five units"; }
pass "resume skips finished units and completes the rest"

# ---- 3. resumed result set equals a clean --fresh run ------------------------
FRESH="$(run_py --fresh --progress "$WORK/fresh.jsonl" 2>/dev/null)"
[ "$FRESH" = "$OUT" ] || { echo "resumed=[$OUT] fresh=[$FRESH]"; fail "resumed run must equal a fresh run"; }
pass "the resumed result set equals a clean fresh run"

# ---- 4. a corrupt progress line does not break resume ------------------------
PROG2="$WORK/corrupt.jsonl"
STOP_AFTER=3 run_py --progress "$PROG2" >/dev/null 2>&1
printf '{ this is not valid json\n' >> "$PROG2"   # a partial/garbage write
OUT="$(run_py --progress "$PROG2" 2>/dev/null)"; RC=$?
[ "$RC" -eq 0 ] || fail "resume over a corrupt line should still exit 0"
echo "$OUT" | grep -q "COMPLETE u0,u1,u2,u3,u4" || { echo "$OUT"; fail "resume must survive a corrupt progress line"; }
pass "a corrupt progress line does not break resume"

echo "ALL longrun kill-test checks passed"
