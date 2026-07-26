# KT-K1.1 — Can G-POLARITY tell right from wrong? (BLOCKING)

**Verdict: PASS.** The engine separates the three real lopi birth defects from the two
reference-correct shapes with no manual annotation.

## Command

```
python3 -m pytest tests/test_polarity.py -v
```

Fixture set assembled from real lopi source at `5760da0` *before* `lib/polarity.py` was
written (`crates/lopi-agent/src/runner/verifier_runner.rs`, `.../eval_runner.rs`,
`crates/lopi-agent/src/scorer.rs`, `.../runner/finalize.rs`). Not edited afterward to
accommodate what the detector turned out to catch.

## Fixture set

**Must FAIL:**
1. `verifier_runner.rs:21-23` — `let Some(client) = self.api_client.clone() else { return
   true; };`
2. `eval_runner.rs:45-50` — `if self.api_client.is_none() && acceptance_needs_judge(...)
   { ...; return true; }`
3. `scorer.rs:44-107` — the `if skip_build_check {} else if cargo_toml.exists() {} else
   if package.json.exists() {} else { score.test_pass_rate = 1.0; ... }` dispatch's
   terminal, unconditioned `else` (the "no detectable test runner" branch)

**Must PASS:**
4. `verifier_runner.rs:92-129` — `handle_verifier_error` / `verifier_error_proceeds`,
   fail-closed with the explicit `verifier_fail_open` operator opt-in, plus the `Err(e)
   => return self.handle_verifier_error(...).await` match arm that dispatches to it
5. `finalize.rs:64-66` — `zero_diff_is_success`, `until_satisfied ||
   deliverable.allows_zero_diff_success()` — a domain condition, not an absence check

## Raw output (2026-07-26)

```
tests/test_polarity.py::test_fixture_1_let_else_fails PASSED             [  5%]
tests/test_polarity.py::test_fixture_2_is_none_fails PASSED              [ 11%]
tests/test_polarity.py::test_fixture_3_unrecognised_stack_fails PASSED   [ 17%]
tests/test_polarity.py::test_fixture_4_handle_verifier_error_passes PASSED [ 23%]
tests/test_polarity.py::test_fixture_4b_err_match_arm_passes PASSED      [ 29%]
tests/test_polarity.py::test_fixture_5_zero_diff_is_success_passes PASSED [ 35%]
tests/test_polarity.py::test_kt_k1_1_separates_fail_from_pass_with_no_manual_annotation PASSED [ 41%]
[... 10 more, Python/TypeScript synthetic vocabulary checks + explicit-override checks ...]
================================== 17 passed in 0.05s ===================================
```

## What actually separates them

Every "must FAIL" condition tests **whether evaluation was possible**: `let ... else`,
`.is_none()`, a dispatch chain's unconditioned default arm. Every "must PASS" condition
either tests a **domain fact** (`until_satisfied`, a plain `if proceed`) or routes its
permissive-looking value through a **named function call**, not a bare literal
(`return self.handle_verifier_error(...).await`, `verifier_error_proceeds(fail_open)`).
The engine's regexes key on the condition/return *shape*, never on file identity or
literal fixture text — confirmed by the synthetic Python/TypeScript tests in the same
file, which exercise the same vocabulary on code that has nothing to do with lopi.

One deliberate, load-bearing restriction, found while building fixture 3: a terminal
`else` is only treated as "the default/unrecognised case" when it is preceded by at
least one `else if` (a 3+-way dispatch). A plain 2-way `if/else`'s `else` branch is NOT
flagged by this rule. This was necessary to keep `scorer.rs`'s own legitimate
`if skip_build_check { test_pass_rate = 1.0 }` branch (a domain fact: the change is
docs-only) from being swept in alongside the real defect four branches later in the same
function — both branches set the identical permissive constant, so the condition shape,
not the value, has to be doing the separating work. Verified directly:
`test_fixture_3_unrecognised_stack_fails` asserts exactly one finding and that
`"skip_build_check"` does not appear in it.

## Rescope decision

Not needed. The detector achieves clean separation with a general, shape-based
vocabulary (five condition patterns × Rust/Python/TypeScript packs), not per-fixture
special-casing. `gate_polarity` ships as a real blocking gate (Phase 2), not downgraded
to advisory-only triage — though it still *defaults* to advisory for a repo that has not
opted in yet (the standard coverage-floor ratchet), which is a policy choice, not a
concession to detector quality.

## Limit carried forward

Where a condition is genuinely ambiguous between "could not evaluate" and "chose not
to" (a bare 2-way `if/else`, a permissive value reached only through further named
calls), the engine does not flag it. This is a deliberate false negative, recorded in
`lib/polarity.py`'s own module docstring and in `KONJO_FORWARD.md`, not a bug to be
tuned away by loosening the condition-shape vocabulary.
