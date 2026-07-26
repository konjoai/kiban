# KT-K1.3 — Does G-CAN-FAIL have anything to bind to?

**Verdict: PASS.** Both surveyed repos' quality-gate sets are enumerable, named, and
already documented well enough to fill a `gates:` block. G-CAN-FAIL ships as a real CI
gate (Phase 3), not downgraded to a convention-only checklist item.

## Command

Manual survey (no automated command; this KT is a discovery question, not a
detector test):

```
# lopi (5760da0)
cat .github/workflows/konjo-gate.yml

# squish (already reconciled in profiles/squish.yml, Phase 2 of an earlier sprint)
grep -n "G1\|G2\|G3\|G4" /path/to/squish/.github/workflows/konjo-gate.yml
```

## Raw finding

**lopi** (`.github/workflows/konjo-gate.yml`, `5760da0`): six named, numbered gates,
each already carrying either a `HARD GATE` or `ADVISORY BY DESIGN`/`KNOWN DEBT` marker
(lopi's own soft-gate convention lint, `.konjo/scripts/soft_gate_lint.py`, already
enforces that every `continue-on-error: true` step carries one of those two labels):

| Gate | Job | Enforcement |
|---|---|---|
| G0 | Doc Staleness | hard |
| G1 | Static Analysis (fmt, clippy, audit, deny, dead code, soft-gate lint) | hard (pedantic clippy + reachability check advisory by design) |
| G2 | Tests + Coverage | hard (coverage floor); 80%/95% target soft, known debt |
| G3 | Mutation Testing | hard (≤10% survival), PR-only |
| G4 | Complexity + Size + DRY | hard (docs gate soft, known debt) |
| G5 | Adversarial Review (Wall 3) | hard on BLOCKER verdict |

**squish** (`profiles/squish.yml`, reconciled against the real repo in an earlier
sprint): `konjo-gate.yml`'s G1-G4 are already named in the profile itself —
`coverage-80`, `complexity-radon`, `file-size-500`, `dry`, `docs-interrogate-80`
(`contract_gates`), plus `mutmut` (`mutation`).

## What this means for G-CAN-FAIL

The gate set in both repos is not merely enumerable in principle — it is *already
enumerated*, by each repo's own CI YAML and (for squish) its kiban profile. Neither repo
currently names a `rejects_test` per gate (that concept does not exist in either repo's
CI yet), but naming the gates themselves — the prerequisite this KT actually asks
about — required no discovery step, just reading the existing workflow file.

**Proceed as designed**: `profiles/_schema.yml`'s `gates:` block (Phase 3) and
`gate_can_fail` ship as a real, blocking-capable CI gate, not a convention-plus-checklist
fallback.

## Carried to K2 / lopi follow-up (out of scope here per K1's own non-goals)

Populating lopi's or squish's actual `gates:` list with real `rejects_test` commands
(e.g. `cargo test --test verifier_rejects_planted_violation` for lopi's G0-G5) is
consuming-repo work, not K1's. K1 built and kill-tested the mechanism against synthetic
profiles (`tests/test_can_fail_killtest.sh`); wiring it into lopi's or squish's real
`.konjo/profile.yml` is explicitly out of scope ("Do not let this sprint drift into
lopi" / "A second override channel" is not the concern here, but the same
non-goal-boundary applies to editing consuming repos generally).
