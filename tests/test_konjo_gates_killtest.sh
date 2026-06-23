#!/usr/bin/env bash
# Phase 2 kill-test: konjo-gates must enforce in a CI-like environment with NO ~/.konjo,
# NO `claude` on PATH, and NO network. It must pass a clean diff, fail a net-new prose
# violation, fail a HIGH secret, and run the self_test replay eval as a gate.
#
# We strip the directory holding `claude` from PATH and point HOME at an empty dir so a
# stray ~/.konjo cannot be read. The self_test gate uses the recorded cassettes via the
# replay backend, so it needs no model and no network.

set -u

KIBAN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATES="$KIBAN_ROOT/bin/konjo-gates"
PROFILE="$KIBAN_ROOT/profiles/squish.yml"

WORK="$(mktemp -d)"
FAKE_HOME="$(mktemp -d)"
trap 'rm -rf "$WORK" "$FAKE_HOME"' EXIT

fail() { echo "FAIL: $1"; exit 1; }
pass() { echo "ok: $1"; }

# Strip the dir containing `claude` from PATH so the engine cannot reach a live model.
CLAUDE_BIN="$(command -v claude || true)"
CLEAN_PATH="$PATH"
if [ -n "$CLAUDE_BIN" ]; then
  CLAUDE_DIR="$(dirname "$CLAUDE_BIN")"
  CLEAN_PATH="$(echo "$PATH" | tr ':' '\n' | grep -vx "$CLAUDE_DIR" | paste -sd: -)"
fi

run_gates() {
  # shellcheck disable=SC2086
  env -u ANTHROPIC_BASE_URL -u ANTHROPIC_API_KEY \
    HOME="$FAKE_HOME" KONJO_SKIP_UPDATE=1 PATH="$CLEAN_PATH" \
    python "$GATES" --profile "$PROFILE" --base main 2>&1
}

# Confirm the live model really is unreachable in this PATH.
if env PATH="$CLEAN_PATH" command -v claude >/dev/null 2>&1; then
  fail "precondition: claude should not be on PATH for the kill-test"
fi

make_repo() {
  local repo="$WORK/$1"
  mkdir -p "$repo"
  git -C "$repo" init -q
  git -C "$repo" config user.email t@t
  git -C "$repo" config user.name t
  git -C "$repo" checkout -q -b main
  mkdir -p "$repo/docs"
  printf 'A clean line of documentation.\n' > "$repo/docs/guide.md"
  git -C "$repo" add .
  git -C "$repo" commit -qm base
  git -C "$repo" checkout -q -b feature
  echo "$repo"
}

# ---- 1. clean diff passes ----------------------------------------------------
REPO="$(make_repo clean)"
printf 'A clean line of documentation.\nAnother plain sentence.\n' > "$REPO/docs/guide.md"
git -C "$REPO" commit -qam "add a plain sentence"
OUT="$(cd "$REPO" && run_gates)"; RC=$?
echo "$OUT" | grep -q "self_test" || fail "self_test gate did not run"
echo "$OUT" | grep -Eq "self_test.*PASS|PASS.*self_test" || fail "self_test should pass via replay"
[ "$RC" -eq 0 ] || { echo "$OUT"; fail "clean diff should pass (rc=$RC)"; }
pass "clean diff passes and self_test replay ran as a gate"

# ---- 2. net-new prose violation in article scope fails -----------------------
REPO="$(make_repo prose)"
mkdir -p "$REPO/articles"
# An em dash is a blocking editorial violation in article scope.
printf 'This post is great and robust — really.\n' > "$REPO/articles/post.md"
git -C "$REPO" add articles/post.md
git -C "$REPO" commit -qm "add article with violations"
OUT="$(cd "$REPO" && run_gates)"; RC=$?
echo "$OUT" | grep -Eq "FAIL.*prose|prose.*FAIL" || { echo "$OUT"; fail "prose gate should FAIL"; }
[ "$RC" -ne 0 ] || { echo "$OUT"; fail "net-new prose violation should block (rc=$RC)"; }
pass "net-new prose violation blocks"

# ---- 3. HIGH secret on an added line fails -----------------------------------
REPO="$(make_repo secret)"
{
  echo "config:"
  echo "-----BEGIN PRIVATE KEY-----"
  echo "MIIBVgIBADANBgkqhkiG9w0BAQEFAASCAUAwggE8AgEAAkEA"
  echo "-----END PRIVATE KEY-----"
} > "$REPO/secret.txt"
git -C "$REPO" add secret.txt
git -C "$REPO" commit -qm "oops add a key"
OUT="$(cd "$REPO" && run_gates)"; RC=$?
echo "$OUT" | grep -Eq "FAIL.*secrets|secrets.*FAIL" || { echo "$OUT"; fail "secrets gate should FAIL"; }
[ "$RC" -ne 0 ] || { echo "$OUT"; fail "HIGH secret should block (rc=$RC)"; }
pass "HIGH secret blocks"

echo "ALL konjo-gates kill-test checks passed"
