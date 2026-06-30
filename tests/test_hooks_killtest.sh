#!/usr/bin/env bash
# Phase 11 kill-test: the lifecycle hook templates must work with NO `claude` and NO network.
# The Stop hook runs verify_cmd and blocks a red end-of-turn (exit 2); the PostToolUse format
# hook runs format_cmd and never blocks (exit 0). Both no-op when their field is absent. The
# konjo-headless helper bakes --bare and --output-format stream-json --verbose.

set -u

KIBAN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STOP="$KIBAN_ROOT/templates/hooks/stop-verify.sh"
FMT="$KIBAN_ROOT/templates/hooks/posttooluse-format.sh"

WORK="$(mktemp -d)"
FAKE_HOME="$(mktemp -d)"
trap 'rm -rf "$WORK" "$FAKE_HOME"' EXIT

fail() { echo "FAIL: $1"; exit 1; }
pass() { echo "ok: $1"; }

# Strip the dir holding `claude` from PATH; add kiban/bin so konjo-profile-get resolves.
CLAUDE_BIN="$(command -v claude || true)"
CLEAN_PATH="$KIBAN_ROOT/bin:$PATH"
if [ -n "$CLAUDE_BIN" ]; then
  CLAUDE_DIR="$(dirname "$CLAUDE_BIN")"
  CLEAN_PATH="$(echo "$CLEAN_PATH" | tr ':' '\n' | grep -vx "$CLAUDE_DIR" | paste -sd: -)"
fi

run_hook() {  # run_hook <script> <profile>
  # shellcheck disable=SC2086
  env -u ANTHROPIC_BASE_URL -u ANTHROPIC_API_KEY \
    HOME="$FAKE_HOME" PATH="$CLEAN_PATH" KONJO_PROFILE="$2" \
    bash "$1" </dev/null
}

if env PATH="$CLEAN_PATH" command -v claude >/dev/null 2>&1; then
  fail "precondition: claude should not be on PATH for the kill-test"
fi

# ---- 1. Stop hook: a passing verify_cmd lets the turn end (exit 0) ------------
printf 'verify_cmd: %s\n' "'sh -c \"exit 0\"'" > "$WORK/pass.yml"
run_hook "$STOP" "$WORK/pass.yml" >/dev/null 2>&1; RC=$?
[ "$RC" -eq 0 ] || fail "Stop hook should exit 0 when verify_cmd passes (rc=$RC)"
pass "Stop hook runs verify_cmd and allows a green end-of-turn"

# ---- 2. Stop hook: a failing verify_cmd blocks the stop (exit 2) --------------
printf 'verify_cmd: %s\n' "'sh -c \"exit 1\"'" > "$WORK/red.yml"
run_hook "$STOP" "$WORK/red.yml" >/dev/null 2>&1; RC=$?
[ "$RC" -eq 2 ] || fail "Stop hook should exit 2 when verify_cmd fails (rc=$RC)"
pass "Stop hook blocks a red end-of-turn when verify_cmd fails"

# ---- 3. Stop hook: no verify_cmd is a safe no-op (exit 0) ---------------------
printf 'repo: x\n' > "$WORK/none.yml"
run_hook "$STOP" "$WORK/none.yml" >/dev/null 2>&1; RC=$?
[ "$RC" -eq 0 ] || fail "Stop hook should no-op (exit 0) with no verify_cmd (rc=$RC)"
pass "Stop hook no-ops safely when no verify_cmd is declared"

# ---- 4. Format hook: runs format_cmd, exits 0 --------------------------------
printf "format_cmd: 'sh -c \"touch %s/formatted\"'\n" "$WORK" > "$WORK/fmt.yml"
run_hook "$FMT" "$WORK/fmt.yml" >/dev/null 2>&1; RC=$?
[ "$RC" -eq 0 ] || fail "format hook should exit 0 (rc=$RC)"
[ -f "$WORK/formatted" ] || fail "format hook should have run format_cmd (no marker)"
pass "format hook runs format_cmd after an edit"

# ---- 5. Format hook: never blocks, even when format_cmd fails -----------------
printf 'format_cmd: %s\n' "'sh -c \"exit 7\"'" > "$WORK/fmtfail.yml"
run_hook "$FMT" "$WORK/fmtfail.yml" >/dev/null 2>&1; RC=$?
[ "$RC" -eq 0 ] || fail "format hook must never block, even on a formatter error (rc=$RC)"
pass "format hook never blocks a turn over a cosmetic step"

# ---- 6. headless helper bakes the fast, structured flags ---------------------
ARGV="$(env PATH="$CLEAN_PATH" python "$KIBAN_ROOT/bin/konjo-headless" --dry-run "hello")"
echo "$ARGV" | grep -q -- "--bare" || { echo "$ARGV"; fail "headless should pass --bare"; }
echo "$ARGV" | grep -q -- "--output-format stream-json" || { echo "$ARGV"; fail "headless should stream json"; }
echo "$ARGV" | grep -q -- "--verbose" || { echo "$ARGV"; fail "stream-json requires --verbose"; }
pass "konjo-headless bakes --bare, stream-json, and the required --verbose"

echo "ALL hooks kill-test checks passed"
