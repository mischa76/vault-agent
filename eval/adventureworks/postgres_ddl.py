"""Render the AdventureWorks schema extract as PostgreSQL DDL — the cross-check for WP96.

An instrument, not a product: the extract (`schema_extract.json`, transcribed from Microsoft's
install script by `extract.py`) becomes a catalogue a real PostgreSQL holds — schemas, tables,
columns with types and nullability, primary keys, the `AK_*` unique indexes (`rowguid` ones
included: the catalogue has them), every foreign key, every description as a `COMMENT` — so that
`vault-agent source-schema` can be measured against what `derive.py` derives from the same
extract (spec §4 P4). It is also the schema half of backlog C23 (a loader for the data is not here).

Transcription with one mapping: SQL Server types to PostgreSQL types (`_TYPES`), alias types to
their base (`user_defined_types`, WP64), and the ten computed columns (`AS` in the extract) to
`text`, because the extract records no type for them.

    python -m eval.adventureworks.postgres_ddl --out /tmp/aw.sql
    psql -h localhost -U vault -d aw_ddl -v ON_ERROR_STOP=1 -f /tmp/aw.sql
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_TYPES = {
    "int": "integer", "bigint": "bigint", "smallint": "smallint", "tinyint": "smallint",
    "bit": "boolean", "money": "numeric(19, 4)", "smallmoney": "numeric(10, 4)",
    "float": "double precision", "real": "real", "datetime": "timestamp",
    "smalldatetime": "timestamp", "date": "date", "time": "time",
    "uniqueidentifier": "uuid", "varbinary(max)": "bytea", "nvarchar(max)": "text",
    "varchar(max)": "text", "hierarchyid": "text", "geography": "text", "xml": "xml",
    "AS": "text",
}
_SIZED = re.compile(r"^(?P<base>nvarchar|varchar|nchar|char|decimal|numeric)\((?P<args>[^)]*)\)$")


def pg_type(declared: str, aliases: dict[str, dict[str, Any]]) -> str:
    """The PostgreSQL spelling of a SQL Server type as the extract records it."""
    alias = aliases.get(declared.removeprefix("dbo."))
    if alias:
        declared = alias["base_type"]
    if declared in _TYPES:
        return _TYPES[declared]
    if declared.upper().startswith("XML"):
        return "xml"
    match = _SIZED.match(declared)
    if match:
        base = {"nvarchar": "varchar", "nchar": "char", "decimal": "numeric"}.get(
            match.group("base"), match.group("base")
        )
        args = ", ".join(part.strip() for part in match.group("args").split(","))
        return f"{base}({args})"
    raise ValueError(f"no PostgreSQL type for {declared!r}")


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _lit(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def render_ddl(extract: dict[str, Any], *, schema_prefix: str = "") -> str:
    """Schemas, tables with keys and unique indexes, then every foreign key, then every
    comment — in the extract's (sorted) order, so two renderings are byte-identical."""
    aliases = extract.get("user_defined_types", {})
    tables = extract["tables"]
    schemas = sorted({t["schema"] for t in tables})
    lines: list[str] = []
    for schema in schemas:
        lines.append(f"CREATE SCHEMA {_q(schema_prefix + schema)};")
    lines.append("")
    for table in tables:
        qualified = f"{_q(schema_prefix + table['schema'])}.{_q(table['name'])}"
        body = [
            f"    {_q(col['name'])} {pg_type(col['type'], aliases)}"
            + ("" if col["nullable"] else " NOT NULL")
            for col in table["columns"]
        ]
        if table["primary_key"]:
            body.append(
                f"    PRIMARY KEY ({', '.join(_q(c) for c in table['primary_key'])})"
            )
        lines.append(f"CREATE TABLE {qualified} (")
        lines.append(",\n".join(body))
        lines.append(");")
        for ak in table["alternate_keys"]:
            lines.append(
                f"CREATE UNIQUE INDEX {_q(ak['name'])} ON {qualified} "
                f"({', '.join(_q(c) for c in ak['columns'])});"
            )
        lines.append("")
    for table in tables:
        qualified = f"{_q(schema_prefix + table['schema'])}.{_q(table['name'])}"
        for fk in table["foreign_keys"]:
            referenced = (
                f"{_q(schema_prefix + fk['references_schema'])}.{_q(fk['references_table'])}"
            )
            lines.append(
                f"ALTER TABLE {qualified} ADD FOREIGN KEY "
                f"({', '.join(_q(c) for c in fk['columns'])}) REFERENCES {referenced} "
                f"({', '.join(_q(c) for c in fk['references_columns'])});"
            )
    lines.append("")
    for table in tables:
        qualified = f"{_q(schema_prefix + table['schema'])}.{_q(table['name'])}"
        if table["description"]:
            lines.append(f"COMMENT ON TABLE {qualified} IS {_lit(table['description'])};")
        for col in table["columns"]:
            if col["description"]:
                lines.append(
                    f"COMMENT ON COLUMN {qualified}.{_q(col['name'])} IS "
                    f"{_lit(col['description'])};"
                )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extract", type=Path,
        default=Path("eval/datasets/adventureworks/schema_extract.json"),
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--schema-prefix", default="")
    args = parser.parse_args()
    extract = json.loads(args.extract.read_text(encoding="utf-8"))
    args.out.write_text(render_ddl(extract, schema_prefix=args.schema_prefix), encoding="utf-8")
    print(f"{len(extract['tables'])} tables rendered to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
