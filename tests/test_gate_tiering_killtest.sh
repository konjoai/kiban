#!/usr/bin/env bash
# Adoption-Ramp-1 kill-test: gate_blocking_promotion. "A gate that cannot demonstrate
# it can fail must not be allowed to block." A profile declaring `tier: blocking` on a
# gates: entry with no rejects_test FAILs; one with a rejects_test that does not pass
# FAILs; one with a passing rejects_test PASSes; no gate declaring tier: blocking SKIPs.
#
# Mirrors tests/test_can_fail_killtest.sh's shape -- gate_blocking_promotion is the
# tier-specific narrowing of the same "can_fail" claim, checked independently.

set -u

KIBAN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATES="$KIBAN_ROOT/bin/konjo-gates"

WORK="$(mktemp -d)"
FAKE_HOME="$(mktemp -d)"
trap 'rm -rf "$WORK" "$FAKE_HOME"' EXIT

fail() { echo "FAIL: $1"; exit 1; }
pass() { echo "ok: $1"; }

REPO="$WORK/repo"
mkdir -p "$REPO"
git -C "$REPO" init -q
git -C "$REPO" config user.email t@t
git -C "$REPO" config user.name t
git -C "$REPO" checkout -q -b main
echo "x" > "$REPO/f.txt"
git -C "$REPO" add .
git -C "$REPO" commit -qm base
git -C "$REPO" checkout -q -b feature
echo "y" >> "$REPO/f.txt"
git -C "$REPO" commit -aqm "unrelated change"

run_gate() {  # $1 = profile path
  ( cd "$REPO" && env HOME="$FAKE_HOME" KONJO_SKIP_UPDATE=1 \
      python "$GATES" --profile "$1" --base main --no-self-test 2>&1 )
}

# ---- a. no gate declares tier: blocking (advisory-tier gate present, with its own
#         passing rejects_test so can_fail itself stays green) -> blocking_promotion SKIPs
PROFILE_NONE="$WORK/none.yml"
cat > "$PROFILE_NONE" <<'YML'
repo: gate-tiering-killtest
stack: [rust]
format_lint: []
contract_gates: []
mutation: "none-with-reason: kill-test fixture"
specialists: []
verify_cmd: "true"
gates:
  - name: konjo_verifier
    rejects_test: "python3 -c 'assert True'"
    tier: advisory
overrides: {}
YML
OUT="$(run_gate "$PROFILE_NONE")"
echo "$OUT" | grep -Eq "SKIP.*blocking_promotion|blocking_promotion.*SKIP" || { echo "$OUT"; fail "no tier: blocking gate should SKIP, not silently pass as clean"; }
pass "no gate declares tier: blocking -> blocking_promotion SKIPs"

# ---- b. tier: blocking with NO rejects_test -> FAIL, names the offending gate --------
PROFILE_MISSING="$WORK/missing.yml"
cat > "$PROFILE_MISSING" <<'YML'
repo: gate-tiering-killtest
stack: [rust]
format_lint: []
contract_gates: []
mutation: "none-with-reason: kill-test fixture"
specialists: []
verify_cmd: "true"
gates:
  - name: konjo_verifier
    tier: blocking
overrides: {}
YML
OUT="$(run_gate "$PROFILE_MISSING")"; RC=$?
echo "$OUT" | grep -Eq "FAIL.*blocking_promotion|blocking_promotion.*FAIL" || { echo "$OUT"; fail "tier: blocking with no rejects_test should FAIL"; }
[ "$RC" -ne 0 ] || fail "tier: blocking with no rejects_test should block"
echo "$OUT" | grep -q "konjo_verifier" || fail "should name the offending gate"
pass "tier: blocking with no rejects_test FAILs"

# ---- c. tier: blocking with a rejects_test that exists but fails -> FAIL -------------
PROFILE_FAILING="$WORK/failing.yml"
cat > "$PROFILE_FAILING" <<YML
repo: gate-tiering-killtest
stack: [rust]
format_lint: []
contract_gates: []
mutation: "none-with-reason: kill-test fixture"
specialists: []
verify_cmd: "true"
gates:
  - name: konjo_verifier
    rejects_test: "python3 -c 'assert False'"
    tier: blocking
overrides: {}
YML
OUT="$(run_gate "$PROFILE_FAILING")"; RC=$?
echo "$OUT" | grep -Eq "FAIL.*blocking_promotion|blocking_promotion.*FAIL" || { echo "$OUT"; fail "tier: blocking with a failing rejects_test should FAIL"; }
[ "$RC" -ne 0 ] || fail "tier: blocking with a failing rejects_test should block"
pass "tier: blocking with a failing rejects_test FAILs"

# ---- d. tier: blocking with a rejects_test that exists and passes -> PASS -------------
PROFILE_PASSING="$WORK/passing.yml"
cat > "$PROFILE_PASSING" <<YML
repo: gate-tiering-killtest
stack: [rust]
format_lint: []
contract_gates: []
mutation: "none-with-reason: kill-test fixture"
specialists: []
verify_cmd: "true"
gates:
  - name: konjo_verifier
    rejects_test: "python3 -c 'assert True'"
    tier: blocking
overrides: {}
YML
OUT="$(run_gate "$PROFILE_PASSING")"; RC=$?
echo "$OUT" | grep -Eq "PASS.*blocking_promotion|blocking_promotion.*PASS" || { echo "$OUT"; fail "tier: blocking with a passing rejects_test should PASS"; }
[ "$RC" -eq 0 ] || fail "a passing rejects_test on a tier: blocking gate should not block"
pass "tier: blocking with a passing rejects_test PASSes"

echo "ALL gate-tiering kill-test checks passed"
