#!/usr/bin/env bash
# K1 Phase 2 kill-test: the G-POLARITY gate end to end, and KT-K1.2 (the waiver
# trailer's binding).
#   - lopi's three real birth-defect sites (verbatim, per KT-K1.1) FAIL konjo-gates.
#   - a Konjo-Polarity-Waived trailer bound to the exact changed-file fingerprint PASSes.
#   - changing the changed-file SET (a different fingerprint) makes the old waiver stop
#     applying -- the same one-way/prove trailer semantics, not a new override channel.

set -u

KIBAN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATES="$KIBAN_ROOT/bin/konjo-gates"

WORK="$(mktemp -d)"
FAKE_HOME="$(mktemp -d)"
trap 'rm -rf "$WORK" "$FAKE_HOME"' EXIT

fail() { echo "FAIL: $1"; exit 1; }
pass() { echo "ok: $1"; }

# A repo that has adopted G-POLARITY as blocking (advisory: false) -- the state a repo
# reaches after the adoption ramp (KT-K1.1's own default is advisory: true for a repo
# that has not yet flipped the switch; this kill-test exercises the blocking path).
PROFILE="$WORK/profile.yml"
cat > "$PROFILE" <<'YML'
repo: polarity-killtest
stack: [rust]
format_lint: []
contract_gates: []
mutation: "none-with-reason: kill-test fixture, no crate to mutate"
specialists: []
polarity:
  enabled: true
  advisory: false
verify_cmd: "true"
overrides: {}
YML

REPO="$WORK/repo"
mkdir -p "$REPO/src"
git -C "$REPO" init -q
git -C "$REPO" config user.email t@t
git -C "$REPO" config user.name t
git -C "$REPO" checkout -q -b main
cat > "$REPO/src/lib.rs" <<'RS'
pub fn noop() {}
RS
git -C "$REPO" add .
git -C "$REPO" commit -qm base
git -C "$REPO" checkout -q -b feature

# ---- plant lopi's three real birth-defect sites, verbatim (KT-K1.1's fixture set) ----
cat > "$REPO/src/verifier_runner.rs" <<'RS'
impl AgentRunner {
    pub(super) async fn run_verifier_pass(&mut self, attempt: u8, test_errors: &[String]) -> bool {
        let Some(client) = self.api_client.clone() else {
            return true;
        };
        let plan = self.last_plan.clone().unwrap_or_default();
        true
    }
}
RS

cat > "$REPO/src/eval_runner.rs" <<'RS'
impl AgentRunner {
    pub(super) async fn evaluate_acceptance_gate(&mut self, score: &Score, attempt: u8) -> bool {
        if self.api_client.is_none() && acceptance_needs_judge(&acceptance) {
            self.log(
                "eval: judge tier has no API client configured — skipping the judge check".to_string(),
            );
            return true;
        }
        true
    }
}
RS

cat > "$REPO/src/scorer.rs" <<'RS'
impl Scorer {
    pub async fn score(&self) -> Result<Score> {
        let mut score = Score::new(0.0, 0, 0);
        if skip_build_check {
            score.test_pass_rate = 1.0;
        } else if cargo_toml.exists() {
            score.test_pass_rate = if out.status.success() { 1.0 } else { 0.0 };
        } else if self.repo_path.join("package.json").exists() {
            score.test_pass_rate = if out.status.success() { 1.0 } else { 0.0 };
        } else {
            // No detectable test runner — treat as passing with a warning.
            score.test_pass_rate = 1.0;
            score.errors.push("no test runner detected".into());
        }
        Ok(score)
    }
}
RS

git -C "$REPO" add .
git -C "$REPO" commit -qm "plant lopi's three real birth-defect sites (KT-K1.1)"

run_gate() {
  ( cd "$REPO" && env HOME="$FAKE_HOME" KONJO_SKIP_UPDATE=1 \
      python "$GATES" --profile "$PROFILE" --base main --no-self-test 2>&1 )
}

OUT="$(run_gate)"; RC=$?
echo "$OUT" | grep -Eq "FAIL.*polarity|polarity.*FAIL" || { echo "$OUT"; fail "lopi's three planted sites should FAIL polarity"; }
[ "$RC" -ne 0 ] || { echo "$OUT"; fail "an unwaived polarity finding should block"; }
echo "$OUT" | grep -q "verifier_runner.rs" || { echo "$OUT"; fail "should name the offending file"; }
pass "lopi's three real birth-defect sites FAIL G-POLARITY"

# ---- the reference-correct shapes must not themselves be flagged -------------------
cat > "$REPO/src/finalize.rs" <<'RS'
pub(super) fn zero_diff_is_success(deliverable: Deliverable, until_satisfied: bool) -> bool {
    until_satisfied || deliverable.allows_zero_diff_success()
}
RS
git -C "$REPO" add .
git -C "$REPO" commit -qm "add zero_diff_is_success (reference-correct, must not fail)"
OUT="$(run_gate)"
echo "$OUT" | grep -q "finalize.rs" && fail "zero_diff_is_success must not itself be named as a finding"
pass "zero_diff_is_success (a domain condition) is not flagged"

# ---- KT-K1.2: the waiver trailer is fingerprint-bound -------------------------------
CHANGED="$(git -C "$REPO" diff --name-only main...feature)"
FP="$(cd "$REPO" && python -c "
import sys
sys.path.insert(0, '$KIBAN_ROOT')
from lib import oneway
print(oneway.fingerprint(sys.stdin.read().splitlines()))
" <<< "$CHANGED")"
git -C "$REPO" commit -q --allow-empty -m "waive the planted findings for review

Konjo-Polarity-Waived: $FP — planted for KT-K1.1/KT-K1.2, not a real defect"
OUT="$(run_gate)"; RC=$?
echo "$OUT" | grep -Eq "PASS.*polarity|polarity.*PASS" || { echo "$OUT"; fail "waived findings should PASS"; }
[ "$RC" -eq 0 ] || { echo "$OUT"; fail "a fully waived polarity gate should not block"; }
pass "a waiver bound to the exact changed-file fingerprint PASSes"

# ---- the waiver does not survive a diff change (a different changed-file set) ------
echo "// unrelated touch" >> "$REPO/src/lib.rs"
git -C "$REPO" commit -qam "touch an unrelated file, changing the fingerprint"
OUT="$(run_gate)"; RC=$?
echo "$OUT" | grep -Eq "FAIL.*polarity|polarity.*FAIL" || { echo "$OUT"; fail "a changed file set should invalidate the old waiver's fingerprint"; }
[ "$RC" -ne 0 ] || { echo "$OUT"; fail "the stale waiver must not silence the still-unwaived findings"; }
pass "the waiver does not silence a different change (KT-K1.2)"

echo "ALL polarity kill-test checks passed"
