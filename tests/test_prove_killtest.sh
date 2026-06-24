#!/usr/bin/env bash
# Phase 4 kill-test: the prove gate end to end.
#   - konjo-prove renders MERGE / NOISE (sub-threshold) / NOISE (non-sig) / REGRESSION
#     from synthetic paired artifacts, and emits a MERGE trailer only on MERGE.
#   - konjo-gates: a perf change with no MERGE record FAILS; with the record PASSES,
#     reusing the Phase 3 record-and-check path. The CI gate runs no benchmark.

set -u

KIBAN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROVE="$KIBAN_ROOT/bin/konjo-prove"
GATES="$KIBAN_ROOT/bin/konjo-gates"
PROFILE="$KIBAN_ROOT/profiles/squish.yml"

WORK="$(mktemp -d)"
HOME_DIR="$(mktemp -d)"
STATE="$(mktemp -d)"
trap 'rm -rf "$WORK" "$HOME_DIR" "$STATE"' EXIT

fail() { echo "FAIL: $1"; exit 1; }
pass() { echo "ok: $1"; }

# Write a paired artifact: $1=outfile $2=delta (candidate = baseline + delta, lower better).
make_artifact() {
  python - "$1" "$2" <<'PY'
import json, sys
out, delta = sys.argv[1], float(sys.argv[2])
base = [100.0 + (i % 7) - 3 for i in range(30)]
cand = [b + delta for b in base]
json.dump({"metric": "e2e_response_s", "unit": "s", "lower_is_better": True,
           "hardware": "synthetic", "thermal_controlled": False,
           "baseline": base, "candidate": cand}, open(out, "w"))
PY
}

# Alternating +/-1 artifact (non-significant).
make_artifact_altsign() {
  python - "$1" <<'PY'
import json, sys
out = sys.argv[1]
base = [100.0 + (i % 7) - 3 for i in range(30)]
cand = [b + (1.0 if i % 2 == 0 else -1.0) for i, b in enumerate(base)]
json.dump({"metric": "e2e_response_s", "unit": "s", "lower_is_better": True,
           "hardware": "synthetic", "thermal_controlled": False,
           "baseline": base, "candidate": cand}, open(out, "w"))
PY
}

run_prove() {  # in a throwaway git repo so fingerprint + Ledger work
  local art="$1"
  local d; d="$(mktemp -d)"
  git -C "$d" init -q; git -C "$d" config user.email t@t; git -C "$d" config user.name t
  git -C "$d" checkout -q -b main; echo x > "$d/f"; git -C "$d" add .; git -C "$d" commit -qm base
  ( cd "$d" && env HOME="$HOME_DIR" KONJO_STATE_DIR="$STATE" \
      python "$PROVE" run --results "$art" --min-effect 2.0 --base main 2>&1 )
  rm -rf "$d"
}

make_artifact "$WORK/merge.json" -10        # 10s faster
OUT="$(run_prove "$WORK/merge.json")"
echo "$OUT" | grep -q "MERGE" || { echo "$OUT"; fail "10s-faster should MERGE"; }
echo "$OUT" | grep -q "Konjo-Prove-Merge:" || fail "MERGE should emit the trailer"
pass "significant + above-threshold -> MERGE (trailer emitted)"

make_artifact "$WORK/sub.json" -0.2         # 0.2s faster: significant but sub-threshold
OUT="$(run_prove "$WORK/sub.json")"
echo "$OUT" | grep -q "NOISE" || { echo "$OUT"; fail "0.2s should be NOISE"; }
echo "$OUT" | grep -q "Konjo-Prove-Merge:" && fail "sub-threshold must NOT emit a MERGE trailer"
echo "$OUT" | grep -qi "never merges" || fail "should explain significance alone never merges"
pass "significant but sub-threshold -> NOISE (no trailer) [load-bearing]"

make_artifact_altsign "$WORK/ns.json"
OUT="$(run_prove "$WORK/ns.json")"
echo "$OUT" | grep -q "NOISE" || { echo "$OUT"; fail "non-significant should be NOISE"; }
pass "non-significant -> NOISE"

make_artifact "$WORK/reg.json" 10           # 10s slower
OUT="$(run_prove "$WORK/reg.json")"
echo "$OUT" | grep -q "REGRESSION" || { echo "$OUT"; fail "10s-slower should REGRESSION"; }
echo "$OUT" | grep -q "Konjo-Prove-Merge:" && fail "regression must NOT emit a MERGE trailer"
pass "significant wrong-direction -> REGRESSION (no trailer)"

# ---- CI record-and-check: perf change unacked FAILS, acked PASSES ----
REPO="$WORK/repo"
mkdir -p "$REPO/benchmarks"
git -C "$REPO" init -q; git -C "$REPO" config user.email t@t; git -C "$REPO" config user.name t
git -C "$REPO" checkout -q -b main
echo "print('bench')" > "$REPO/benchmarks/bench.py"
git -C "$REPO" add .; git -C "$REPO" commit -qm base
git -C "$REPO" checkout -q -b feature
echo "print('faster bench')" > "$REPO/benchmarks/bench.py"
git -C "$REPO" commit -aqm "optimize the bench path"

run_gate() { ( cd "$REPO" && env HOME="$HOME_DIR" KONJO_SKIP_UPDATE=1 \
  python "$GATES" --profile "$PROFILE" --base main --no-self-test 2>&1 ); }

OUT="$(run_gate)"; RC=$?
echo "$OUT" | grep -Eq "FAIL.*prove|prove.*FAIL" || { echo "$OUT"; fail "unacked perf change should FAIL the prove gate"; }
[ "$RC" -ne 0 ] || fail "unacked perf change should block"
pass "perf change with no MERGE record fails CI"

FP="$(cd "$REPO" && python -c "import sys; sys.path.insert(0,'$KIBAN_ROOT'); from lib import oneway; print(oneway.fingerprint(['benchmarks/bench.py']))")"
git -C "$REPO" commit -q --allow-empty -m "record prove verdict

Konjo-Prove-Merge: $FP"
OUT="$(run_gate)"
echo "$OUT" | grep -Eq "PASS.*prove|prove.*PASS" || { echo "$OUT"; fail "acked perf change should PASS"; }
pass "perf change with the MERGE record passes CI"

# ---- squish prove gate is honest about its inert state (PENDING threshold) ----
# The squish profile has min_effect_pct PENDING (null), so konjo-prove must refuse a
# verdict with NOT ACTIVATED (exit 3) rather than invent an effect size or pass silently.
make_artifact "$WORK/act.json" -5
python - "$WORK/act.json" <<'PY'
import json, sys
a = json.load(open(sys.argv[1])); a["baseline"] = [x + 5 for x in a["candidate"]]
json.dump(a, open(sys.argv[1], "w"))
PY
d="$(mktemp -d)"; git -C "$d" init -q; git -C "$d" config user.email t@t; git -C "$d" config user.name t
git -C "$d" checkout -q -b main; echo x > "$d/f"; git -C "$d" add .; git -C "$d" commit -qm base
OUT="$(cd "$d" && env HOME="$HOME_DIR" KONJO_STATE_DIR="$STATE" \
  python "$PROVE" run --results "$WORK/act.json" --profile "$KIBAN_ROOT/profiles/squish.yml" --base main 2>&1)"; RC=$?
rm -rf "$d"
echo "$OUT" | grep -q "NOT ACTIVATED" || { echo "$OUT"; fail "PENDING profile should report NOT ACTIVATED"; }
[ "$RC" -eq 3 ] || { echo "$OUT"; fail "NOT ACTIVATED should exit 3 (got $RC)"; }
pass "squish prove gate reports NOT ACTIVATED while min_effect_pct is PENDING"

echo "ALL prove kill-test checks passed"
