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
