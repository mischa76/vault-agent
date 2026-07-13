"""Tests for the declared source-schema loader (source-schema-input spec, Phase 1).

Deterministic, no API key: the loader is pure file I/O + pydantic validation.
"""
import json
from pathlib import Path

import pytest

from vault_agent.source_schema import load_source_schemas
from vault_agent.state import SourceTable

_YAML = """\
source_schemas:
  - table: customer
    columns: [national_customer_id, bank_customer_reference, customer_name]
  - table: account
    columns: [account_number, balance, status]
"""

_EXPECTED = [
    SourceTable(
        table="customer",
        columns=["national_customer_id", "bank_customer_reference", "customer_name"],
    ),
    SourceTable(table="account", columns=["account_number", "balance", "status"]),
]


def test_loads_yaml_with_top_level_key(tmp_path: Path) -> None:
    path = tmp_path / "schema.yml"
    path.write_text(_YAML, encoding="utf-8")
    assert load_source_schemas(path) == _EXPECTED


def test_loads_json(tmp_path: Path) -> None:
    # yaml.safe_load parses JSON too; here a real .json file with the same content.
    path = tmp_path / "schema.json"
    path.write_text(
        json.dumps(
            {
                "source_schemas": [
                    {
                        "table": "customer",
                        "columns": [
                            "national_customer_id",
                            "bank_customer_reference",
                            "customer_name",
                        ],
                    },
                    {"table": "account", "columns": ["account_number", "balance", "status"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert load_source_schemas(path) == _EXPECTED


def test_loads_bare_list(tmp_path: Path) -> None:
    path = tmp_path / "schema.yml"
    path.write_text(
        "- table: customer\n"
        "  columns: [national_customer_id, bank_customer_reference, customer_name]\n"
        "- table: account\n"
        "  columns: [account_number, balance, status]\n",
        encoding="utf-8",
    )
    assert load_source_schemas(path) == _EXPECTED


def test_empty_document_yields_empty_list(tmp_path: Path) -> None:
    path = tmp_path / "empty.yml"
    path.write_text("", encoding="utf-8")
    assert load_source_schemas(path) == []


def test_null_source_schemas_key_yields_empty_list(tmp_path: Path) -> None:
    path = tmp_path / "null.yml"
    path.write_text("source_schemas:\n", encoding="utf-8")
    assert load_source_schemas(path) == []


def test_missing_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_source_schemas(tmp_path / "nope.yml")


def test_mapping_without_key_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "wrong.yml"
    path.write_text("tables:\n  - table: customer\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no 'source_schemas' key"):
        load_source_schemas(path)


def test_malformed_entry_raises_clear_value_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.yml"
    # 'table' must be a string; an entry missing it is a user error worth surfacing.
    path.write_text(
        "source_schemas:\n  - columns: [account_number]\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match=str(path)):
        load_source_schemas(path)


def test_non_mapping_entry_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "scalar.yml"
    path.write_text("source_schemas:\n  - just_a_string\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a mapping"):
        load_source_schemas(path)


def test_loads_optional_schema_and_database_keys(tmp_path: Path) -> None:
    # WP7 §7.2: `schema:` (aliased to schema_name) and `database:` locate the table
    # physically so grounded runs can bind staging through real dbt source() refs.
    path = tmp_path / "schema.yml"
    path.write_text(
        """\
source_schemas:
  - table: raw_customer
    columns: [national_customer_id]
    schema: core
    database: bank
  - table: raw_account
    columns: [account_number]
""",
        encoding="utf-8",
    )
    loaded = load_source_schemas(path)
    assert loaded[0].schema_name == "core"
    assert loaded[0].database == "bank"
    # Both remain optional; absent keys stay None (bare-name binding, as before).
    assert loaded[1].schema_name is None
    assert loaded[1].database is None


def test_invalid_schema_key_type_is_attributable(tmp_path: Path) -> None:
    path = tmp_path / "schema.yml"
    path.write_text(
        "source_schemas:\n  - table: customer\n    schema: [not, a, string]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"entry #1 is invalid"):
        load_source_schemas(path)


def test_bare_column_names_stay_inert(tmp_path: Path) -> None:
    # WP9 §3.1: bare string columns coerce to SourceColumn(name=...) with empty type/comment
    # and column_names returns the exact original strings (byte-for-byte inert).
    path = tmp_path / "schema.yml"
    path.write_text(_YAML, encoding="utf-8")
    loaded = load_source_schemas(path)
    assert loaded[0].column_names == [
        "national_customer_id",
        "bank_customer_reference",
        "customer_name",
    ]
    assert loaded[0].column_refs[0].type == ""
    assert loaded[0].column_refs[0].comment is None


def test_enriched_columns_carry_type_and_comment(tmp_path: Path) -> None:
    # WP9 §3.1: the {name, type, comment} form loads; column_names still yields plain names.
    path = tmp_path / "enriched.yml"
    path.write_text(
        """\
source_schemas:
  - table: VICTOR_PARTNER
    schema: legacy_victor
    columns:
      - name: PARTN_NR
        type: varchar(10)
        comment: "operational partner id"
      - name: KD_NR
        type: varchar(6)
        comment: "legacy branch code, NOT a customer number"
      - PARTN_TYP
""",
        encoding="utf-8",
    )
    loaded = load_source_schemas(path)
    assert loaded[0].schema_name == "legacy_victor"
    assert loaded[0].column_names == ["PARTN_NR", "KD_NR", "PARTN_TYP"]
    refs = loaded[0].column_refs
    assert refs[0].type == "varchar(10)" and refs[0].comment == "operational partner id"
    assert "branch code" in (refs[1].comment or "")
    # A bare string mixed in still coerces to an empty-metadata column.
    assert refs[2].type == "" and refs[2].comment is None


def test_shipped_enriched_schema_loads() -> None:
    # The spike's reference enriched schema (WP9 §3.1 reference input) round-trips.
    path = (
        Path(__file__).resolve().parent.parent
        / "eval/datasets/messy_insurance/source_schema_enriched.yml"
    )
    loaded = load_source_schemas(path)
    victor = next(t for t in loaded if t.table == "VICTOR_PARTNER")
    kd_nr = next(c for c in victor.column_refs if c.name == "KD_NR")
    assert "branch" in (kd_nr.comment or "").lower()
