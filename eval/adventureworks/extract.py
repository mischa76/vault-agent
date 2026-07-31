"""Parse the AdventureWorks OLTP install script into a structured schema extract (WP30 §2.1).

The extract is the CHECKED-IN instrument: `derive.py` builds every case asset from it, so the
cases are reproducible without the 330 KB upstream SQL and without network access. This module
is the one-time (re-runnable) bridge from Microsoft's DDL to that extract.

Everything here is transcription, never interpretation — the point of WP30 is that the schema,
its boundaries and its documentation come from somebody else. In particular:

* table and column descriptions are taken VERBATIM from ``sp_addextendedproperty`` and are never
  authored, extended or paraphrased (WP30 §2.3 as amended 2026-07-29);
* the five schemas are the subject areas, exactly as shipped (§2.2);
* natural keys are read from Microsoft's own ``AK_*`` unique indexes rather than chosen by us —
  which is what makes the golden mappings defensible rather than our modelling opinion.

Usage (the upstream file is not checked in; fetch it, then run this):

    curl -sSLO https://raw.githubusercontent.com/microsoft/sql-server-samples/master/\\
samples/databases/adventure-works/oltp-install-script/instawdb.sql
    python -m eval.adventureworks.extract --sql instawdb.sql \\
        --out eval/datasets/adventureworks/schema_extract.json

AdventureWorks is MIT licensed (Microsoft); see the NOTICE file beside the extract.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# The five OLTP subject areas. `dbo` holds AWBuildVersion/DatabaseLog/ErrorLog — infrastructure,
# not business content — and is excluded. That is the ONLY exclusion, and it is not a boundary
# judgement: those tables model the sample database itself, not Adventure Works Cycles.
BUSINESS_SCHEMAS = ("HumanResources", "Person", "Production", "Purchasing", "Sales")

_TABLE_RE = re.compile(
    r"CREATE TABLE \[(?P<schema>\w+)\]\.\[(?P<table>\w+)\]\((?P<body>.*?)\n\) ON ",
    re.S,
)
# The type is USUALLY bracketed (`[varchar](50)`, `[dbo].[Flag]`) but not always: `rowguid`
# is declared as bare `uniqueidentifier ROWGUIDCOL`. Accepting only the bracketed form silently
# dropped exactly the columns worth most here — a perfectly unique technical GUID beside the
# real business key is the GUID-shadow trap this instrument gets for free.
# A type argument may itself be bracketed — XML columns carry a schema collection, as in
# `[XML]([Person].[AdditionalContactInfoSchemaCollection])` — and `rest` must not require
# leading whitespace, because `[nvarchar](3850),` puts the comma flush against the type.
# Both mistakes dropped descriptive payload columns (Demographics, AdditionalContactInfo,
# Comments), which would have quietly shrunk the satellites this instrument is meant to test.
_COLUMN_RE = re.compile(
    r"^\s*\[(?P<name>\w+)\]\s+(?P<type>(?:\[[\w\]\[.]+\]|\w+)(?:\(\s*[\w,\s\[\].]+\s*\))?)"
    r"(?P<rest>.*)?$"
)
# Positional form: N'MS_Description', N'<text>', N'SCHEMA', [s], N'TABLE', [t] [, N'COLUMN', [c]]
_DESC_RE = re.compile(
    r"sp_addextendedproperty\] N'MS_Description', N'(?P<desc>(?:[^']|'')*)', "
    r"N'SCHEMA', \[(?P<schema>\w+)\], N'TABLE', \[(?P<table>\w+)\]"
    r"(?:, N'COLUMN', \[(?P<column>\w+)\])?"
)
_PK_RE = re.compile(
    r"ALTER TABLE \[(?P<schema>\w+)\]\.\[(?P<table>\w+)\] ADD\s+CONSTRAINT \[PK_\w+\] "
    r"PRIMARY KEY \w+\s*\((?P<cols>.*?)\)",
    re.S,
)
_AK_RE = re.compile(
    r"CREATE UNIQUE INDEX \[(?P<name>AK_\w+)\] ON \[(?P<schema>\w+)\]\.\[(?P<table>\w+)\]"
    r"\((?P<cols>.*?)\)",
    re.S,
)
_FK_RE = re.compile(
    r"ALTER TABLE \[(?P<schema>\w+)\]\.\[(?P<table>\w+)\] ADD\s+CONSTRAINT \[FK_\w+\] "
    r"FOREIGN KEY\s*\((?P<cols>.*?)\)\s*REFERENCES \[(?P<ref_schema>\w+)\]\."
    r"\[(?P<ref_table>\w+)\]\s*\((?P<ref_cols>.*?)\)",
    re.S,
)


@dataclass
class Column:
    name: str
    type: str
    nullable: bool
    identity: bool
    description: str | None = None


@dataclass
class Table:
    schema: str
    name: str
    description: str | None = None
    columns: list[Column] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    # Microsoft's own natural-key declarations. `rowguid` ones are technical surrogates and are
    # kept, flagged, because they are a real GUID-shadow trap: a perfectly unique column sitting
    # next to the true business key (the trap class messy_insurance had to synthesise).
    alternate_keys: list[dict[str, Any]] = field(default_factory=list)
    foreign_keys: list[dict[str, Any]] = field(default_factory=list)


def _names(raw: str) -> list[str]:
    return re.findall(r"\[(\w+)\]", raw)


def _clean(text: str) -> str:
    """Un-escape the SQL string literal. Verbatim otherwise — no rewrapping, no paraphrase."""
    return text.replace("''", "'").strip()


def _parse_columns(body: str) -> list[Column]:
    columns: list[Column] = []
    for line in body.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith(("CONSTRAINT", ")", "--")):
            continue
        match = _COLUMN_RE.match(line)
        if not match:
            continue
        rest = match.group("rest") or ""
        columns.append(
            Column(
                name=match.group("name"),
                type=match.group("type").replace("[", "").replace("]", ""),
                nullable="NOT NULL" not in rest.upper(),
                identity="IDENTITY" in rest.upper(),
            )
        )
    return columns


def parse(sql: str) -> list[Table]:
    """Parse the install script into the business-schema tables, in DDL order."""
    tables: dict[tuple[str, str], Table] = {}
    for match in _TABLE_RE.finditer(sql):
        schema, name = match.group("schema"), match.group("table")
        if schema not in BUSINESS_SCHEMAS:
            continue
        tables[(schema, name)] = Table(
            schema=schema, name=name, columns=_parse_columns(match.group("body"))
        )

    for match in _DESC_RE.finditer(sql):
        key = (match.group("schema"), match.group("table"))
        table = tables.get(key)
        if table is None:
            continue
        text = _clean(match.group("desc"))
        column = match.group("column")
        if column is None:
            table.description = text
            continue
        for col in table.columns:
            if col.name == column:
                col.description = text
                break

    for match in _PK_RE.finditer(sql):
        table = tables.get((match.group("schema"), match.group("table")))
        if table is not None:
            table.primary_key = _names(match.group("cols"))

    for match in _AK_RE.finditer(sql):
        table = tables.get((match.group("schema"), match.group("table")))
        if table is None:
            continue
        cols = _names(match.group("cols"))
        table.alternate_keys.append(
            {"name": match.group("name"), "columns": cols,
             "technical_guid": cols == ["rowguid"]}
        )

    for match in _FK_RE.finditer(sql):
        table = tables.get((match.group("schema"), match.group("table")))
        if table is None:
            continue
        table.foreign_keys.append({
            "columns": _names(match.group("cols")),
            "references_schema": match.group("ref_schema"),
            "references_table": match.group("ref_table"),
            "references_columns": _names(match.group("ref_cols")),
        })

    return list(tables.values())


def build_extract(sql: str) -> dict[str, Any]:
    """The checked-in artifact: deterministic, sorted, no timestamps."""
    tables = parse(sql)
    return {
        "source": (
            "microsoft/sql-server-samples — samples/databases/adventure-works/"
            "oltp-install-script/instawdb.sql (MIT, see NOTICE)"
        ),
        "schemas": list(BUSINESS_SCHEMAS),
        "tables": [
            asdict(t) for t in sorted(tables, key=lambda t: (t.schema, t.name))
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sql", type=Path, required=True, help="path to instawdb.sql")
    parser.add_argument("--out", type=Path, required=True, help="path to the JSON extract")
    args = parser.parse_args()

    extract = build_extract(args.sql.read_text(encoding="utf-8", errors="replace"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(extract, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    tables = extract["tables"]
    described = sum(1 for t in tables for c in t["columns"] if c["description"])
    total = sum(len(t["columns"]) for t in tables)
    print(f"{len(tables)} tables, {total} columns, {described} with a verbatim description")
    for schema in BUSINESS_SCHEMAS:
        n = sum(1 for t in tables if t["schema"] == schema)
        print(f"  {schema:16} {n:>3} tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
