#!/usr/bin/env bash
# Phase 8 kill-test: the compounding loop must enforce its guardrail with NO ~/.konjo, NO
# `claude` on PATH, and NO network. A correction writes a learning; a learning names an
# enforcement target; a learning with no target is REFUSED and nothing is written. The
# recall path (konjo-learn search) finds the learning afterward.
#
# State is redirected to a temp dir via KONJO_STATE_DIR so the test never touches the real
# learnings log.

set -u

KIBAN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LEARN="$KIBAN_ROOT/bin/konjo-learn"

WORK="$(mktemp -d)"
FAKE_HOME="$(mktemp -d)"
STATE="$(mktemp -d)"
trap 'rm -rf "$WORK" "$FAKE_HOME" "$STATE"' EXIT

fail() { echo "FAIL: $1"; exit 1; }
pass() { echo "ok: $1"; }

# Strip the dir containing `claude` from PATH so nothing can reach a live model.
CLAUDE_BIN="$(command -v claude || true)"
CLEAN_PATH="$PATH"
if [ -n "$CLAUDE_BIN" ]; then
  CLAUDE_DIR="$(dirname "$CLAUDE_BIN")"
  CLEAN_PATH="$(echo "$PATH" | tr ':' '\n' | grep -vx "$CLAUDE_DIR" | paste -sd: -)"
fi

run_learn() {
  # shellcheck disable=SC2086
  env -u ANTHROPIC_BASE_URL -u ANTHROPIC_API_KEY \
    HOME="$FAKE_HOME" KONJO_SKIP_UPDATE=1 KONJO_STATE_DIR="$STATE" PATH="$CLEAN_PATH" \
    python "$LEARN" "$@" 2>&1
}

if env PATH="$CLEAN_PATH" command -v claude >/dev/null 2>&1; then
  fail "precondition: claude should not be on PATH for the kill-test"
fi

# ---- 1. a learning with no enforcement target is refused ----------------------
OUT="$(run_learn add --mistake "a mistake" --rule "a rule" --enforcement "" )"; RC=$?
echo "$OUT" | grep -qi "refused" || { echo "$OUT"; fail "no-target learning should be refused"; }
[ "$RC" -eq 4 ] || { echo "$OUT"; fail "refusal should exit 4 (rc=$RC)"; }
# Nothing was written: a search finds no learnings.
OUT="$(run_learn search "mistake")"
echo "$OUT" | grep -qi "no matching learnings" || { echo "$OUT"; fail "refused learning must not be stored"; }
pass "a learning with no enforcement target is refused and not stored"

# ---- 2. a correction writes a learning that names its target ------------------
OUT="$(run_learn add \
  --mistake "Reworded a moved specialist prompt during a refactor" \
  --rule "Move lane prompts verbatim and assert byte-equality in a test" \
  --enforcement "tests/test_packs.py frozen prompt-hash assertion" \
  --scope org --author tester)"; RC=$?
echo "$OUT" | grep -qi "logged learning" || { echo "$OUT"; fail "valid learning should be logged"; }
[ "$RC" -eq 0 ] || { echo "$OUT"; fail "valid learning should exit 0 (rc=$RC)"; }
pass "a correction with an enforcement target writes a learning"

# ---- 3. the recall path finds it, with its enforcement target -----------------
OUT="$(run_learn search "prompt")"
echo "$OUT" | grep -qi "test_packs.py" || { echo "$OUT"; fail "recall should surface the learning's enforcement target"; }
echo "$OUT" | grep -q "ACTIVE" || { echo "$OUT"; fail "the learning should be active"; }
pass "recall finds the learning and shows where its rule lives"

# ---- 4. redact retires it -----------------------------------------------------
LID="$(run_learn search "prompt" | grep ACTIVE | head -1 | sed -E 's/.*\] ([0-9a-f]+) .*/\1/')"
[ -n "$LID" ] || fail "could not parse the learning id"
OUT="$(run_learn redact "$LID" --reason "superseded")"; RC=$?
[ "$RC" -eq 0 ] || { echo "$OUT"; fail "redact should exit 0"; }
OUT="$(run_learn search "prompt")"
echo "$OUT" | grep -qi "no matching learnings" || { echo "$OUT"; fail "redacted learning should drop from active search"; }
pass "redact retires the learning from the active view"

echo "ALL learnings kill-test checks passed"
