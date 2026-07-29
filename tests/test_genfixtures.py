"""evals/genfixtures.py: generation-fixture discovery and mechanical classification."""

from __future__ import annotations

from pathlib import Path

from evals import genfixtures

_CORPUS = Path(__file__).resolve().parent.parent / "evals" / "gen_fixtures"


def test_discover_seed_corpus() -> None:
    fixtures = genfixtures.discover_gen_fixtures(_CORPUS)
    ids = {f.name for f in fixtures}
    assert {
        "01_webhook_signature_baseline",
        "02_subprocess_no_env_allowlist",
        "03_hardcoded_token",
    } <= ids


def test_load_task() -> None:
    task = genfixtures.load_task(_CORPUS / "01_webhook_signature_baseline")
    assert task.id == "webhook-signature-baseline"
    assert task.context_label == "baseline"
    assert task.prompt


def test_classify_diff_clean_control_finds_nothing_mechanical() -> None:
    diff_text = (_CORPUS / "01_webhook_signature_baseline" / "candidate.diff").read_text()
    result = genfixtures.classify_diff(diff_text, ["crates/lopi-remote/src/whatsapp.rs"])
    assert result.count("secret_in_source") == 0
    assert result.count("untrusted_input_reaching_exec") == 0


def test_classify_diff_catches_subprocess_hint() -> None:
    diff_text = (_CORPUS / "02_subprocess_no_env_allowlist" / "candidate.diff").read_text()
    result = genfixtures.classify_diff(diff_text, ["crates/lopi-agent/src/eval_tier.rs"])
    assert result.count("untrusted_input_reaching_exec") == 1


def test_classify_diff_catches_hardcoded_secret() -> None:
    diff_text = (_CORPUS / "03_hardcoded_token" / "candidate.diff").read_text()
    result = genfixtures.classify_diff(diff_text, ["crates/lopi-webhook/src/gh_client.rs"])
    assert result.count("secret_in_source") == 1


def test_classify_diff_names_unclassified_classes() -> None:
    result = genfixtures.classify_diff("+ nothing interesting\n", ["x.py"])
    unclassified = result.unclassified()
    assert "missing_timeout" in unclassified
    assert "unbounded_queue" in unclassified
    # A checked class with zero findings is NOT unclassified -- None vs [] matters.
    assert "secret_in_source" not in unclassified


def test_run_gen_corpus_totals() -> None:
    report = genfixtures.run_gen_corpus(_CORPUS)
    assert report["n_fixtures"] == 3
    assert report["totals"]["secret_in_source"] == 1
    assert report["totals"]["untrusted_input_reaching_exec"] == 1
    assert "missing_timeout" in report["unclassified_classes"]


def test_run_gen_corpus_empty_dir_is_report_only_zero(tmp_path: Path) -> None:
    report = genfixtures.run_gen_corpus(tmp_path)
    assert report["n_fixtures"] == 0
    assert all(n == 0 for n in report["totals"].values())
