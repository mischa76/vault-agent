"""Tests for the golden-dataset loader (WP6 layer 1). Deterministic, no API key."""
from pathlib import Path

import pytest

from eval.datasets import (
    DATASETS_ROOT,
    EvalCase,
    load_all_cases,
    load_eval_case,
)

_MINIMAL = """\
name: toy
input_document: requirements.md
golden:
  hubs:
    - {name: hub_customer, business_key: national customer ID}
  links: []
  satellites: []
"""


def _write_case(tmp_path: Path, yaml_text: str = _MINIMAL) -> Path:
    (tmp_path / "requirements.md").write_text("# reqs", encoding="utf-8")
    path = tmp_path / "dataset.yml"
    path.write_text(yaml_text, encoding="utf-8")
    return path


def test_loads_minimal_case_with_defaults(tmp_path: Path) -> None:
    case = load_eval_case(_write_case(tmp_path))
    assert case.name == "toy"
    assert case.input_document == (tmp_path / "requirements.md").resolve()
    assert case.source_schema is None
    assert case.golden.hubs[0].business_key == "national customer ID"
    assert case.expectations.validation_passed is True
    assert case.expectations.max_validation_warnings is None
    assert case.expectations.min_scores == {}


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_eval_case(tmp_path / "dataset.yml")


def test_malformed_yaml_names_file(tmp_path: Path) -> None:
    path = tmp_path / "dataset.yml"
    path.write_text("name: [unclosed", encoding="utf-8")
    with pytest.raises(ValueError, match=str(path).replace("\\", "\\\\")):
        load_eval_case(path)


def test_non_mapping_document_names_file_and_type(tmp_path: Path) -> None:
    path = tmp_path / "dataset.yml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="got list"):
        load_eval_case(path)


def test_invalid_case_is_attributable(tmp_path: Path) -> None:
    path = _write_case(tmp_path, "name: toy\ngolden: {}\n")  # input_document missing
    with pytest.raises(ValueError, match="invalid eval case"):
        load_eval_case(path)


def test_dangling_input_document_raises(tmp_path: Path) -> None:
    path = tmp_path / "dataset.yml"
    path.write_text(_MINIMAL.replace("requirements.md", "nope.md"), encoding="utf-8")
    with pytest.raises(ValueError, match="input_document"):
        load_eval_case(path)


def test_dangling_source_schema_raises(tmp_path: Path) -> None:
    path = _write_case(tmp_path, _MINIMAL + "source_schema: nope.yml\n")
    with pytest.raises(ValueError, match="source_schema"):
        load_eval_case(path)


def test_mapping_match_defaults_to_concept(tmp_path: Path) -> None:
    case = load_eval_case(_write_case(tmp_path))
    assert case.mapping_match == "concept"


def test_column_mode_allows_pair_based_gates(tmp_path: Path) -> None:
    yaml_text = _MINIMAL + (
        "mapping_match: column\n"
        "expectations:\n"
        "  min_scores: {mapping_coverage: 0.8, false_friend_hits: 1.0, pipeline_health: 1.0}\n"
    )
    case = load_eval_case(_write_case(tmp_path, yaml_text))
    assert case.mapping_match == "column"
    assert case.expectations.min_scores["mapping_coverage"] == 0.8


def test_column_mode_rejects_concept_coupled_gate(tmp_path: Path) -> None:
    yaml_text = _MINIMAL + (
        "mapping_match: column\n"
        "expectations:\n"
        "  min_scores: {mapping_accuracy: 0.8}\n"  # concept-coupled: reported-only at scale
    )
    with pytest.raises(ValueError, match="mapping_accuracy"):
        load_eval_case(_write_case(tmp_path, yaml_text))


def test_rejects_gating_construct_f1_with_an_empty_golden(tmp_path: Path) -> None:
    """A vacuous scorer reports 1.0, so gating it would pass on absence of evidence."""
    empty_golden = "name: toy\ninput_document: requirements.md\ngolden: {}\n"
    yaml_text = empty_golden + "expectations:\n  min_scores: {construct_f1: 0.5}\n"
    with pytest.raises(ValueError, match="construct_f1"):
        load_eval_case(_write_case(tmp_path, yaml_text))


def test_rejects_gating_driving_key_accuracy_without_a_golden_driving_key(
    tmp_path: Path,
) -> None:
    yaml_text = _MINIMAL + "expectations:\n  min_scores: {driving_key_accuracy: 1.0}\n"
    with pytest.raises(ValueError, match="driving_key_accuracy"):
        load_eval_case(_write_case(tmp_path, yaml_text))


def test_gating_construct_f1_is_fine_when_the_golden_declares_constructs(
    tmp_path: Path,
) -> None:
    yaml_text = _MINIMAL + "expectations:\n  min_scores: {construct_f1: 0.5}\n"
    case = load_eval_case(_write_case(tmp_path, yaml_text))
    assert case.expectations.min_scores == {"construct_f1": 0.5}


def test_load_all_cases_rejects_duplicate_names(tmp_path: Path) -> None:
    for directory in ("a", "b"):
        case_dir = tmp_path / directory
        case_dir.mkdir()
        _write_case(case_dir)
    with pytest.raises(ValueError, match="duplicate case name 'toy'"):
        load_all_cases(tmp_path)


def test_load_all_cases_skips_dirs_without_dataset(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    case_dir = tmp_path / "real"
    case_dir.mkdir()
    _write_case(case_dir)
    cases = load_all_cases(tmp_path)
    assert [case.name for case in cases] == ["toy"]


# --- the shipped cases -------------------------------------------------------------


def test_shipped_cases_load_with_unique_names() -> None:
    cases = load_all_cases()
    # Sorted by directory name; the WP13 scale cases join the original three.
    assert [case.name for case in cases] == [
        # WP30: the independent instrument — a schema, boundaries and documentation this
        # project did not author. `_full` and `_incremental` are the two arms of the
        # domain-partitioning experiment; the five others are its subject areas.
        "adventureworks_full",
        "adventureworks_humanresources",
        "adventureworks_incremental",
        "adventureworks_person",
        "adventureworks_production",
        "adventureworks_purchasing",
        "adventureworks_sales",
        "bank",
        # WP23: the one case that runs the pipeline in extension mode.
        "bank_extension",
        # WP29.1: shipped since 2026-08-01. Its fixtures existed from the Phase 2 spike, but
        # without a dataset.yml the harness could not load it, so `--dataset
        # brownfield_resolution` did not start and its gates could not run. Wiring it IS the
        # work package; this line appearing is the intended effect, not drift.
        "brownfield_resolution",
        "health_insurance",
        "messy_insurance",
        "scale_100",
        "scale_30",
        "scale_300",
    ]
    for case in cases:
        # Committed cases resolve their document to a file; a WP13 generate case has no
        # committed input_document (it is synthesised on demand by materialize_case), and a
        # WP30 chain case has none of its own (every step supplies its own inputs).
        if case.generate is None and case.chain is None:
            assert case.input_document is not None and case.input_document.is_file()
        else:
            assert case.input_document is None


def _shipped(name: str) -> EvalCase:
    return load_eval_case(DATASETS_ROOT / name / "dataset.yml")


def test_bank_case_matches_the_durchstich_model() -> None:
    case = _shipped("bank")
    assert {hub.name for hub in case.golden.hubs} == {"hub_customer", "hub_account"}
    (link,) = case.golden.links
    assert link.driving_key == ["hub_account"]
    assert {sat.sat_type for sat in case.golden.satellites} == {"standard", "effectivity"}
    assert case.source_schema is not None and case.source_schema.is_file()
    assert case.expectations.min_scores == {"construct_f1": 0.5, "mapping_accuracy": 0.95}


def test_health_insurance_case_shape() -> None:
    case = _shipped("health_insurance")
    assert len(case.golden.hubs) == 4
    assert len(case.golden.links) == 3
    assert len(case.golden.satellites) == 7
    assert case.source_schema is None
    by_name = {link.name: link for link in case.golden.links}
    assert by_name["link_insured_person_policy"].driving_key == ["hub_policy"]
    types = {sat.name: sat.sat_type for sat in case.golden.satellites}
    assert types["sat_insured_person_address"] == "multi_active"
    assert types["sat_insured_person_policy_effectivity"] == "effectivity"


def test_messy_insurance_case_is_loose() -> None:
    case = _shipped("messy_insurance")
    assert case.source_schema is not None and case.source_schema.is_file()
    assert case.expectations.min_scores == {}  # informational case, no gate
    assert case.expectations.max_validation_warnings == 25
    assert all(not link.driving_key for link in case.golden.links)


def test_an_extension_case_resolves_its_existing_vault() -> None:
    """WP23: the brownfield eval case carries the model it extends."""
    from eval.datasets import DATASETS_ROOT, load_eval_case

    case = load_eval_case(DATASETS_ROOT / "bank_extension" / "dataset.yml")

    assert case.existing is not None and case.existing.is_file()
    assert case.expectations.min_scores["existing_construct_preservation"] == 1.0


def test_a_greenfield_case_may_not_gate_the_preservation_scorer(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The WP18 rule applied to WP23's scorer: it is vacuous without an existing vault, so
    gating it there would pass on absence of evidence."""
    from eval.datasets import load_eval_case

    doc = tmp_path / "req.md"
    doc.write_text("# reqs", encoding="utf-8")
    case_file = tmp_path / "dataset.yml"
    case_file.write_text(
        "name: t\ninput_document: req.md\n"
        "golden:\n  hubs: [{name: hub_a, business_key: a}]\n"
        "expectations:\n  min_scores: {existing_construct_preservation: 1.0}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="pass on absence of evidence"):
        load_eval_case(case_file)
