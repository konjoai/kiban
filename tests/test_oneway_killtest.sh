#!/usr/bin/env bash
# Phase 3 kill-test: the one-way-door classifier, the typed confirm, and the CI gate
# that checks an acknowledgement record without ever prompting.
#
#   a. classify a public-API break / data delete as one-way, a comment as two-way
#   b. the confirm refuses a vague reply and logs on a valid typed token
#   c. in CI mode, an unacknowledged one-way change fails konjo-gates; with the
#      acknowledgement trailer it passes

set -u

KIBAN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ONEWAY="$KIBAN_ROOT/bin/konjo-oneway"
GATES="$KIBAN_ROOT/bin/konjo-gates"
PROFILE="$KIBAN_ROOT/profiles/squish.yml"

WORK="$(mktemp -d)"
FAKE_HOME="$(mktemp -d)"
STATE="$(mktemp -d)"
trap 'rm -rf "$WORK" "$FAKE_HOME" "$STATE"' EXIT

fail() { echo "FAIL: $1"; exit 1; }
pass() { echo "ok: $1"; }

# ---- a. classification -------------------------------------------------------
printf -- '-def public_api(x):\n+def public_api(x, y):\n' > "$WORK/api.diff"
OUT="$(python "$ONEWAY" classify --files pkg/api.py --diff "$WORK/api.diff")"
echo "$OUT" | grep -q '"door": "one-way"' || fail "public-API break should be one-way: $OUT"
pass "public-API break classifies one-way"

printf -- '+# typo fix\n' > "$WORK/c.diff"
OUT="$(python "$ONEWAY" classify --files notes.py --diff "$WORK/c.diff")"
echo "$OUT" | grep -q '"door": "two-way"' || fail "comment change should be two-way: $OUT"
pass "comment change classifies two-way"

# ---- b. confirm refuses a vague reply, logs on a valid one -------------------
# Vague reply ("yes") must abort with nonzero.
printf -- '-0.3.0\n+0.4.0\n' > "$WORK/v.diff"
if printf 'yes\n' | env KONJO_STATE_DIR="$STATE" HOME="$FAKE_HOME" \
     python "$ONEWAY" confirm --files VERSION --diff "$WORK/v.diff" --author test >/dev/null 2>&1; then
  fail "confirm should refuse a vague reply"
fi
pass "confirm refuses a vague reply"

# Exact token + justification confirms and logs to the Ledger.
OUT="$(printf 'CONFIRM\ncutting the release\n' | env KONJO_STATE_DIR="$STATE" HOME="$FAKE_HOME" \
     python "$ONEWAY" confirm --files VERSION --diff "$WORK/v.diff" --author test 2>&1)"
echo "$OUT" | grep -q "acknowledged" || fail "valid confirm should acknowledge: $OUT"
grep -q "ONEWAY-ACK" "$STATE/ledger/decisions.jsonl" || fail "confirm should log to the Ledger"
pass "confirm logs acknowledgement to the Ledger on a valid typed token"

# ---- c. CI gate: unacknowledged fails, acknowledged passes -------------------
REPO="$WORK/repo"
mkdir -p "$REPO"
git -C "$REPO" init -q
git -C "$REPO" config user.email t@t
git -C "$REPO" config user.name t
git -C "$REPO" checkout -q -b main
echo "0.3.0" > "$REPO/VERSION"
git -C "$REPO" add .
git -C "$REPO" commit -qm base
git -C "$REPO" checkout -q -b feature
echo "0.4.0" > "$REPO/VERSION"
git -C "$REPO" commit -aqm "bump version"

run_gate() {
  ( cd "$REPO" && env HOME="$FAKE_HOME" KONJO_SKIP_UPDATE=1 \
      python "$GATES" --profile "$PROFILE" --base main --no-self-test 2>&1 )
}

OUT="$(run_gate)"; RC=$?
echo "$OUT" | grep -Eq "FAIL.*one_way_door|one_way_door.*FAIL" || { echo "$OUT"; fail "unacked one-way should FAIL"; }
[ "$RC" -ne 0 ] || { echo "$OUT"; fail "unacked one-way should block"; }
pass "unacknowledged one-way change fails CI"

# Add the acknowledgement trailer (fingerprint over the changed file set).
FP="$(cd "$REPO" && python -c "import sys; sys.path.insert(0,'$KIBAN_ROOT'); from lib import oneway; print(oneway.fingerprint(['VERSION']))")"
git -C "$REPO" commit -q --allow-empty -m "ack release

Konjo-Acknowledged-Oneway: $FP"
OUT="$(run_gate)"; RC=$?
echo "$OUT" | grep -Eq "PASS.*one_way_door|one_way_door.*PASS" || { echo "$OUT"; fail "acked one-way should PASS"; }
pass "acknowledged one-way change passes CI"

echo "ALL one-way-door kill-test checks passed"
