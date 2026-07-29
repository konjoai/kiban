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
        "04_unbounded_channel",
        "05_missing_timeout",
        "06_untyped_error_boundary",
        "07_missing_test_failure_path",
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
    # Phase 14, Phase 2 closed missing_timeout/unbounded_queue/untyped_error_boundary/
    # missing_test_failure_path; only raw_index_external_input is still genuinely
    # unclassified (needs dataflow tracking, see genfixtures.MECHANICALLY_CLASSIFIED).
    assert unclassified == ["raw_index_external_input"]
    # A checked class with zero findings is NOT unclassified -- None vs [] matters.
    assert "secret_in_source" not in unclassified
    assert "missing_timeout" not in unclassified


def test_run_gen_corpus_totals() -> None:
    report = genfixtures.run_gen_corpus(_CORPUS)
    assert report["n_fixtures"] == 7
    assert report["totals"]["secret_in_source"] == 1
    assert report["totals"]["untrusted_input_reaching_exec"] >= 1
    assert report["totals"]["unbounded_queue"] == 1
    assert report["totals"]["missing_timeout"] >= 1
    assert report["totals"]["untyped_error_boundary"] == 2
    assert report["totals"]["missing_test_failure_path"] == 1
    assert report["unclassified_classes"] == ["raw_index_external_input"]


def test_new_fixtures_fire_their_target_class() -> None:
    """Each Phase 14 fixture actually exercises the mechanical classifier it's named
    for -- a fixture that silently classifies to zero would be worse than no fixture."""
    for name, target in [
        ("04_unbounded_channel", "unbounded_queue"),
        ("05_missing_timeout", "missing_timeout"),
        ("06_untyped_error_boundary", "untyped_error_boundary"),
        ("07_missing_test_failure_path", "missing_test_failure_path"),
    ]:
        fixture_dir = _CORPUS / name
        diff_text = (fixture_dir / "candidate.diff").read_text()
        changed = sorted({
            line.split()[-1].removeprefix("b/")
            for line in diff_text.splitlines()
            if line.startswith("+++ ")
        })
        result = genfixtures.classify_diff(diff_text, changed)
        assert result.count(target), name


def test_run_gen_corpus_empty_dir_is_report_only_zero(tmp_path: Path) -> None:
    report = genfixtures.run_gen_corpus(tmp_path)
    assert report["n_fixtures"] == 0
    # KT-14.2: zero fixtures means zero classification happened -- every class stays
    # None (unmeasured), never a laundered 0 ("checked, clean").
    assert all(n is None for n in report["totals"].values())


def test_run_gen_corpus_totals_none_stays_none_for_unclassified_class() -> None:
    """The KT-14.2 regression case: an unclassified class must stay None in `totals`,
    not silently read as 0 ("checked, clean") once fixtures are aggregated."""
    report = genfixtures.run_gen_corpus(_CORPUS)
    assert report["totals"]["raw_index_external_input"] is None
    assert "raw_index_external_input" in report["unclassified_classes"]
    # Every mechanically classified class is a real int (0 is a legitimate "checked,
    # clean" result for a class with no findings this corpus -- only unmeasured stays
    # None).
    for cls in genfixtures.MECHANICALLY_CLASSIFIED:
        assert isinstance(report["totals"][cls], int)
