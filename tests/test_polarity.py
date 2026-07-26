"""KT-K1.1 (BLOCKING): can G-POLARITY tell right from wrong?

The fixture set below is lifted verbatim from real lopi source at `5760da0` (see
`.konjo/killtests/K1/KT-K1.1.md` for the recorded run and the file:line citations). It
was assembled BEFORE `lib/polarity.py` was written and is not edited to accommodate
whatever the detector turned out to catch -- the anti-goal named in the K1 sprint brief.

Must FAIL (lopi's three real birth defects):
  1. verifier_runner.rs:21-23 -- no API client configured -> `return true`
  2. eval_runner.rs:45-50 -- no API client for the judge tier -> `return true`
  3. scorer.rs:44-107 -- no detectable test runner -> `test_pass_rate = 1.0`

Must PASS (the reference-correct shapes a gate that cannot tell them apart is worse
than no gate at all):
  4. verifier_runner.rs:92-129 -- `handle_verifier_error` / `verifier_error_proceeds`,
     fail-closed with an explicit `verifier_fail_open` operator opt-in
  5. finalize.rs:64-66 -- `zero_diff_is_success`, a domain condition, not an absence check
"""

from __future__ import annotations

from lib import polarity

# ---- 1. verifier_runner.rs:21-23 (must FAIL) ---------------------------------------
FIXTURE_1_LET_ELSE = """\
        let Some(client) = self.api_client.clone() else {
            return true;
        };
"""

# ---- 2. eval_runner.rs:45-50 (must FAIL) --------------------------------------------
FIXTURE_2_IS_NONE = """\
        if self.api_client.is_none() && acceptance_needs_judge(&acceptance) {
            self.log(
                "eval: judge tier has no API client configured — skipping the judge check and proceeding on the scorer's pass".to_string(),
            );
            return true;
        }
"""

# ---- 3. scorer.rs:44-107, the whole dispatch chain (must FAIL) ----------------------
FIXTURE_3_UNRECOGNISED_STACK = """\
        let cargo_toml = self.repo_path.join("Cargo.toml");
        if skip_build_check {
            score.test_pass_rate = 1.0;
            tracing::info!(?changed, "no source changes to verify — skipping test/lint");
        } else if cargo_toml.exists() {
            let mut cmd = Command::new("cargo");
            if which("sccache").is_ok() {
                cmd.env("RUSTC_WRAPPER", "sccache");
            }
            let out = cmd
                .arg("test")
                .arg("--quiet")
                .current_dir(&self.repo_path)
                .output()
                .await?;
            score.test_pass_rate = if out.status.success() { 1.0 } else { 0.0 };
            if !out.status.success() {
                score.errors.push(format!(
                    "cargo test failed:\\n{}",
                    String::from_utf8_lossy(&out.stderr)
                ));
            }
        } else if self.repo_path.join("package.json").exists() {
            let out = Command::new("npm")
                .arg("test")
                .current_dir(&self.repo_path)
                .output()
                .await?;
            score.test_pass_rate = if out.status.success() { 1.0 } else { 0.0 };
            if !out.status.success() {
                score.errors.push(format!(
                    "npm test failed:\\n{}",
                    String::from_utf8_lossy(&out.stderr)
                ));
            }
        } else {
            // No detectable test runner — treat as passing with a warning.
            score.test_pass_rate = 1.0;
            score.errors.push("no test runner detected".into());
        }
"""

# ---- 4. verifier_runner.rs:92-129 (must PASS) ---------------------------------------
FIXTURE_4_HANDLE_VERIFIER_ERROR = """\
    async fn handle_verifier_error(
        &mut self,
        attempt: u8,
        model: &str,
        err: &anyhow::Error,
    ) -> bool {
        let proceed = verifier_error_proceeds(self.task.verifier_fail_open);
        let verdict = lopi_core::VerifierVerdict {
            passed: false,
            gaps: vec![format!("verifier could not evaluate the output: {err}")],
            fix_hints: vec![
                "the verifier errored; re-run so the output can be graded before finalize".into(),
            ],
            confidence: 0.0,
        };
        persist_and_emit(self, attempt, &verdict, model).await;
        if proceed {
            warn!("verifier error (fail-open opt-in, proceeding): {err}");
            return true;
        }
        warn!("verifier error (fail-closed, blocking finalize): {err}");
        self.log(
            "verifier errored — fail-closed: blocking finalize and retrying (set verifier_fail_open to override)".to_string(),
        );
        false
    }
}

#[must_use]
pub fn verifier_error_proceeds(fail_open: bool) -> bool {
    fail_open
}
"""

# The Err match arm that dispatches to handle_verifier_error (also must PASS: it returns
# a call, not a bare permissive literal).
FIXTURE_4B_ERR_MATCH_ARM = """\
        let verdict = match VerifierAgent::new(client)
            .verify(&self.task.goal, &plan, &diff, &test_output, &rubric, &model, effort.as_deref())
            .await
        {
            Ok(v) => v,
            Err(e) => return self.handle_verifier_error(attempt, &model, &e).await,
        };
"""

# ---- 5. finalize.rs:64-66 (must PASS) ------------------------------------------------
FIXTURE_5_ZERO_DIFF_IS_SUCCESS = """\
pub(super) fn zero_diff_is_success(deliverable: Deliverable, until_satisfied: bool) -> bool {
    until_satisfied || deliverable.allows_zero_diff_success()
}
"""


def test_fixture_1_let_else_fails() -> None:
    findings = polarity.lint_text(FIXTURE_1_LET_ELSE, "verifier_runner.rs")
    assert findings, "unconfigured-client let-else returning true must be a finding"
    assert findings[0].rule == "absence-let-else"
    assert findings[0].returned == "return true"


def test_fixture_2_is_none_fails() -> None:
    findings = polarity.lint_text(FIXTURE_2_IS_NONE, "eval_runner.rs")
    assert findings, "no-API-client-for-judge returning true must be a finding"
    assert findings[0].rule == "absence-if-condition"


def test_fixture_3_unrecognised_stack_fails() -> None:
    findings = polarity.lint_text(FIXTURE_3_UNRECOGNISED_STACK, "scorer.rs")
    assert findings, "unrecognised-stack default branch setting 1.0 must be a finding"
    assert len(findings) == 1, f"expected exactly one finding, got {findings}"
    assert findings[0].rule == "absence-default-branch"
    # The legitimate `if skip_build_check { test_pass_rate = 1.0 }` branch (a domain
    # fact, docs-only change) must NOT itself be flagged -- only the chain's terminal,
    # unconditioned `else` (the "none of the known stacks matched" case).
    assert "skip_build_check" not in findings[0].condition


def test_fixture_4_handle_verifier_error_passes() -> None:
    findings = polarity.lint_text(FIXTURE_4_HANDLE_VERIFIER_ERROR, "verifier_runner.rs")
    assert not findings, (
        "handle_verifier_error/verifier_error_proceeds is the reference fail-closed "
        f"implementation with an explicit opt-in; must not be flagged, got {findings}"
    )


def test_fixture_4b_err_match_arm_passes() -> None:
    findings = polarity.lint_text(FIXTURE_4B_ERR_MATCH_ARM, "verifier_runner.rs")
    assert not findings, f"an Err arm dispatching to a real handler is not permissive, got {findings}"


def test_fixture_5_zero_diff_is_success_passes() -> None:
    findings = polarity.lint_text(FIXTURE_5_ZERO_DIFF_IS_SUCCESS, "finalize.rs")
    assert not findings, (
        f"zero_diff_is_success is a domain condition (until_satisfied), not an absence "
        f"check; must not be flagged, got {findings}"
    )


def test_kt_k1_1_separates_fail_from_pass_with_no_manual_annotation() -> None:
    """The KT-K1.1 pass condition, stated once as a single assertion over the whole set:
    the detector separates 1-3 from 4-5 using only its condition-shape/permissive-value
    rules -- no fixture-specific special-casing anywhere in `lib/polarity.py` or the
    language packs."""
    must_fail = [
        FIXTURE_1_LET_ELSE,
        FIXTURE_2_IS_NONE,
        FIXTURE_3_UNRECOGNISED_STACK,
    ]
    must_pass = [
        FIXTURE_4_HANDLE_VERIFIER_ERROR,
        FIXTURE_4B_ERR_MATCH_ARM,
        FIXTURE_5_ZERO_DIFF_IS_SUCCESS,
    ]
    for text in must_fail:
        assert polarity.lint_text(text, "f.rs"), f"expected a finding, got none:\n{text}"
    for text in must_pass:
        findings = polarity.lint_text(text, "f.rs")
        assert not findings, f"expected no finding, got {findings}:\n{text}"


# ---- explicit-override recognition (Phase 2's third PASS outcome) -------------------


def test_is_explicit_override_recognizes_fail_open_field() -> None:
    finding = polarity.Finding(
        path="f.rs", line=1, rule="absence-if-condition",
        condition="if cfg.is_none() {", returned="return self.verifier_fail_open",
    )
    assert polarity.is_explicit_override(finding)


def test_is_explicit_override_rejects_bare_literal() -> None:
    finding = polarity.Finding(
        path="f.rs", line=1, rule="absence-let-else",
        condition="let Some(x) = y else {", returned="return true",
    )
    assert not polarity.is_explicit_override(finding)


# ---- Python pack: synthetic shapes (no real fixture required by KT-K1.1, but the
# vocabulary is specified in the sprint brief and must actually work) ------------------


def test_python_except_swallowed_to_true() -> None:
    text = """\
def check(x):
    try:
        return validate(x)
    except ValueError:
        return True
"""
    findings = polarity.lint_text(text, "m.py")
    assert findings and findings[0].rule == "absence-except"


def test_python_is_none_returns_true() -> None:
    text = """\
def check(cfg):
    if cfg is None:
        return True
    return cfg.run()
"""
    findings = polarity.lint_text(text, "m.py")
    assert findings and findings[0].rule == "absence-is-none"


def test_python_domain_negation_not_flagged() -> None:
    text = """\
def check(until_satisfied):
    if not until_satisfied:
        return False
    return True
"""
    assert not polarity.lint_text(text, "m.py")


def test_python_dict_get_permissive_default() -> None:
    text = 'verdict = flags.get("passed", True)\n'
    findings = polarity.lint_text(text, "m.py")
    assert findings and findings[0].rule == "absence-get-default"


# ---- TypeScript pack: synthetic shapes ----------------------------------------------


def test_ts_if_not_returns_true() -> None:
    text = """\
function check(client) {
    if (!client) {
        return true;
    }
    return client.verify();
}
"""
    findings = polarity.lint_text(text, "m.ts")
    assert findings and findings[0].rule == "absence-if-not"


def test_ts_catch_returns_true() -> None:
    text = """\
function run() {
    try {
        return verify();
    } catch (e) {
        return true;
    }
}
"""
    findings = polarity.lint_text(text, "m.ts")
    assert findings and findings[0].rule == "absence-catch"


def test_ts_nullish_coalesce_to_permissive() -> None:
    text = "const passed = verdict ?? true;\n"
    findings = polarity.lint_text(text, "m.ts")
    assert findings and findings[0].rule == "absence-nullish-coalesce"


def test_unrecognised_extension_yields_no_findings() -> None:
    assert polarity.lint_text("let x = y else { return true; };", "notes.md") == []
