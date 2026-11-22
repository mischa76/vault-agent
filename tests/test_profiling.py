"""Tests for the declared profiling-evidence loader (WP9 §3.2). Keyless, pure I/O + validation."""
from pathlib import Path

import pytest

from vault_agent.profiling import load_profiling

_YAML = """\
tables:
  - table: VICTOR_PARTNER
    row_count: 2000000
    columns:
      - name: PARTN_NR
        uniqueness_ratio: 0.9998
        null_ratio: 0.002
        distinct_count: 1992016
        example_values: ["P000012345"]
      - name: PARTN_GUID
        uniqueness_ratio: 1.0
        null_ratio: 0.0
        distinct_count: 2000000
"""


def test_loads_tables_and_columns(tmp_path: Path) -> None:
    path = tmp_path / "profiling.yml"
    path.write_text(_YAML, encoding="utf-8")
    profiling = load_profiling(path)
    assert set(profiling) == {"VICTOR_PARTNER"}
    partn = profiling["VICTOR_PARTNER"]["PARTN_NR"]
    assert partn.uniqueness_ratio == 0.9998
    assert partn.null_ratio == 0.002
    assert partn.example_values == ["P000012345"]
    # PARTN_GUID profiles as a flawless key (the statistics trap) but that is just data here.
    assert profiling["VICTOR_PARTNER"]["PARTN_GUID"].uniqueness_ratio == 1.0
    # row_count is ignored (not a per-column field), and absent example_values default to [].
    assert profiling["VICTOR_PARTNER"]["PARTN_GUID"].example_values == []


def test_empty_document_is_inert(tmp_path: Path) -> None:
    path = tmp_path / "empty.yml"
    path.write_text("", encoding="utf-8")
    assert load_profiling(path) == {}


def test_null_tables_key_is_inert(tmp_path: Path) -> None:
    path = tmp_path / "null.yml"
    path.write_text("tables:\n", encoding="utf-8")
    assert load_profiling(path) == {}


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_profiling(tmp_path / "nope.yml")


def test_mapping_without_tables_key_is_attributable(tmp_path: Path) -> None:
    path = tmp_path / "wrong.yml"
    path.write_text("source_schemas:\n  - table: x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no 'tables' key"):
        load_profiling(path)


def test_column_without_name_is_attributable(tmp_path: Path) -> None:
    path = tmp_path / "bad.yml"
    path.write_text(
        "tables:\n  - table: VICTOR_PARTNER\n    columns:\n      - uniqueness_ratio: 1.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="without a 'name' key"):
        load_profiling(path)


def test_shipped_profiling_loads() -> None:
    path = (
        Path(__file__).resolve().parent.parent
        / "eval/datasets/messy_insurance/profiling.yml"
    )
    profiling = load_profiling(path)
    # The statistics trap is reflected: PARTN_GUID flawless, PARTN_NR has the 0.2% null wart.
    victor = profiling["VICTOR_PARTNER"]
    assert victor["PARTN_GUID"].uniqueness_ratio == 1.0 and victor["PARTN_GUID"].null_ratio == 0.0
    assert victor["PARTN_NR"].null_ratio > 0.0
