#!/usr/bin/env bash
# K1 Phase 3 kill-test: G-CAN-FAIL. "A green run is not evidence a gate works. Only a
# red one is." A profile declaring a gate with no rejects_test FAILs; a rejects_test
# that does not exist FAILs; a rejects_test that actually passes PASSes.

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

# ---- a. no gates: declared at all -> SKIP (nothing to bind to yet, KT-K1.3) ----------
PROFILE_NONE="$WORK/none.yml"
cat > "$PROFILE_NONE" <<'YML'
repo: can-fail-killtest
stack: [rust]
format_lint: []
contract_gates: []
mutation: "none-with-reason: kill-test fixture"
specialists: []
verify_cmd: "true"
overrides: {}
YML
OUT="$(run_gate "$PROFILE_NONE")"
echo "$OUT" | grep -Eq "SKIP.*can_fail|can_fail.*SKIP" || { echo "$OUT"; fail "no gates: declared should SKIP, not silently pass as clean"; }
pass "no gates: declared -> SKIP (nothing to bind to)"

# ---- b. a declared gate with no rejects_test -> FAIL --------------------------------
PROFILE_MISSING="$WORK/missing.yml"
cat > "$PROFILE_MISSING" <<'YML'
repo: can-fail-killtest
stack: [rust]
format_lint: []
contract_gates: []
mutation: "none-with-reason: kill-test fixture"
specialists: []
verify_cmd: "true"
gates:
  - name: konjo_verifier
overrides: {}
YML
OUT="$(run_gate "$PROFILE_MISSING")"; RC=$?
echo "$OUT" | grep -Eq "FAIL.*can_fail|can_fail.*FAIL" || { echo "$OUT"; fail "a gate with no rejects_test should FAIL"; }
[ "$RC" -ne 0 ] || fail "a gate with no rejects_test should block"
echo "$OUT" | grep -q "konjo_verifier" || fail "should name the offending gate"
pass "a declared gate with no rejects_test FAILs"

# ---- c. a rejects_test that does not exist -> FAIL -----------------------------------
PROFILE_NOTFOUND="$WORK/notfound.yml"
cat > "$PROFILE_NOTFOUND" <<'YML'
repo: can-fail-killtest
stack: [rust]
format_lint: []
contract_gates: []
mutation: "none-with-reason: kill-test fixture"
specialists: []
verify_cmd: "true"
gates:
  - name: konjo_verifier
    rejects_test: "this-command-does-not-exist-anywhere --flag"
overrides: {}
YML
OUT="$(run_gate "$PROFILE_NOTFOUND")"; RC=$?
echo "$OUT" | grep -Eq "FAIL.*can_fail|can_fail.*FAIL" || { echo "$OUT"; fail "a nonexistent rejects_test should FAIL"; }
[ "$RC" -ne 0 ] || fail "a nonexistent rejects_test should block"
pass "a rejects_test that does not exist FAILs"

# ---- d. a real test asserting "enabled == true" is a wiring test, not a rejecting one:
#         it passes trivially without ever exercising the bad input. G-CAN-FAIL cannot
#         see the difference (documented limit) -- but it CAN tell the difference
#         between "no test ran" and "a test ran and passed", which is the ground floor.
PROFILE_TRIVIAL="$WORK/trivial.yml"
cat > "$PROFILE_TRIVIAL" <<YML
repo: can-fail-killtest
stack: [rust]
format_lint: []
contract_gates: []
mutation: "none-with-reason: kill-test fixture"
specialists: []
verify_cmd: "true"
gates:
  - name: konjo_verifier
    rejects_test: "python3 -c 'assert True'"
overrides: {}
YML
OUT="$(run_gate "$PROFILE_TRIVIAL")"; RC=$?
echo "$OUT" | grep -Eq "PASS.*can_fail|can_fail.*PASS" || { echo "$OUT"; fail "an existing, passing rejects_test should PASS"; }
[ "$RC" -eq 0 ] || fail "a passing rejects_test should not block"
pass "a rejects_test that exists and passes PASSes"

# ---- e. a rejects_test that exists but genuinely fails -> FAIL (the test caught
#         nothing, or the gate regressed; either way it is not proof the gate rejects) --
PROFILE_FAILING="$WORK/failing.yml"
cat > "$PROFILE_FAILING" <<YML
repo: can-fail-killtest
stack: [rust]
format_lint: []
contract_gates: []
mutation: "none-with-reason: kill-test fixture"
specialists: []
verify_cmd: "true"
gates:
  - name: konjo_verifier
    rejects_test: "python3 -c 'assert False'"
overrides: {}
YML
OUT="$(run_gate "$PROFILE_FAILING")"; RC=$?
echo "$OUT" | grep -Eq "FAIL.*can_fail|can_fail.*FAIL" || { echo "$OUT"; fail "a rejects_test that fails to run should FAIL"; }
[ "$RC" -ne 0 ] || fail "a failing rejects_test should block"
pass "a rejects_test that exists but does not pass FAILs"

echo "ALL can-fail kill-test checks passed"
