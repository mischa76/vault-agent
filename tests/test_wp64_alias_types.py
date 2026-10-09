"""WP64 — AdventureWorks' alias types resolve to their base types in the derivation (spec §3).
Committed before the change, failing."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from eval.adventureworks.derive import build_source_schema
from eval.adventureworks.extract import build_extract

_SQL = """
CREATE TYPE [AccountNumber] FROM nvarchar(15) NULL;
CREATE TYPE [Flag] FROM bit NOT NULL;
CREATE TYPE [NameStyle] FROM bit NOT NULL;
CREATE TYPE [Name] FROM nvarchar(50) NULL;
CREATE TYPE [OrderNumber] FROM nvarchar(25) NULL;
CREATE TYPE [Phone] FROM nvarchar(25) NULL;
"""


def test_the_extractor_transcribes_the_six_alias_types() -> None:
    types = build_extract(_SQL)["user_defined_types"]
    assert types == {
        "AccountNumber": {"base_type": "nvarchar(15)", "nullable": True},
        "Flag": {"base_type": "bit", "nullable": False},
        "Name": {"base_type": "nvarchar(50)", "nullable": True},
        "NameStyle": {"base_type": "bit", "nullable": False},
        "OrderNumber": {"base_type": "nvarchar(25)", "nullable": True},
        "Phone": {"base_type": "nvarchar(25)", "nullable": True},
    }


def test_the_derivation_resolves_an_alias_and_leaves_everything_else() -> None:
    extract = {
        "schemas": ["HumanResources"],
        "user_defined_types": {"Name": {"base_type": "nvarchar(50)", "nullable": True}},
        "tables": [{
            "schema": "HumanResources", "name": "Department", "description": "", "primary_key": [],
            "alternate_keys": [], "foreign_keys": [],
            "columns": [
                {"name": "DepartmentID", "type": "smallint", "description": "Primary key.",
                 "nullable": False, "identity": True},
                {"name": "Name", "type": "Name", "description": "Name of the department.",
                 "nullable": False, "identity": False},
                {"name": "GroupName", "type": "dbo.Name", "description": "Group.",
                 "nullable": False, "identity": False},
            ],
        }],
    }
    [table] = build_source_schema(extract, "HumanResources")["source_schemas"]
    assert [c["type"] for c in table["columns"]] == ["smallint", "nvarchar(50)", "nvarchar(50)"]
    assert table["columns"][1]["comment"] == "Name of the department."


def test_the_checked_in_extract_and_schemas_carry_no_alias_types() -> None:
    extract = json.loads(Path("eval/datasets/adventureworks/schema_extract.json").read_text())
    assert sorted(extract["user_defined_types"]) == [
        "AccountNumber", "Flag", "Name", "NameStyle", "OrderNumber", "Phone"
    ]
    aliases = set(extract["user_defined_types"])
    for path in Path("eval/datasets").glob("adventureworks_*/source_schema.yml"):
        doc = yaml.safe_load(path.read_text())
        tables = doc if isinstance(doc, list) else doc.get("source_schemas", doc.get("tables", []))
        for table in tables:
            for col in table.get("columns", []):
                if isinstance(col, dict):
                    base = str(col.get("type", "")).split("(")[0].removeprefix("dbo.")
                    assert base not in aliases, (path.name, table["table"], col["name"])
