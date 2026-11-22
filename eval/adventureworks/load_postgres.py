"""Load Microsoft's AdventureWorks CSVs into PostgreSQL under the DDL instrument's catalogue —
the data half of backlog C23 (WP110, 2026-10-31); the schema half is `postgres_ddl.py`.

What it does, in order: fetch the 68 CSVs from the install script's repository into a cache
directory (never re-fetched when present), create the schemas, tables, keys and unique indexes
exactly as `render_ddl` renders them, add `load_datetime` and `record_source` to every table,
COPY each file — decoded and split as the script's own `BULK INSERT` options say (`bulk_insert`
in the extract, transcribed by `extract.py`) — and apply the 90 foreign keys last, so load order
needs no topology and a violated key fails loudly.

Three tolerances the files need, each measured on the file that needs it (spec §1): a `&|`
row's line end (`\\n` or `\\r\\n`) is dropped; a line-feed-terminated record with fewer fields
than the table's columns continues on the next line (ProductReview's comments carry embedded
line feeds); a field that is one NUL byte is the hierarchy root `/` (Document's root node,
exported as a NUL; PostgreSQL `text` cannot hold one). An empty field is NULL, BULK INSERT's
`char` rule. One conversion by type: a `varbinary` `0x…` becomes PostgreSQL's `\\x…`.

    uv run python -m eval.adventureworks.load_postgres \\
        --url postgresql://vault:vault@localhost:5432/aw_loader [--csv-dir DIR] [--replace]

An instrument for the demo and the chain builds, not a product: no retries, no partial loads
— a failing table stops the run with the value PostgreSQL refused.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from eval.adventureworks.postgres_ddl import pg_type, render_ddl, render_foreign_keys

CSV_BASE = (
    "https://raw.githubusercontent.com/microsoft/sql-server-samples/master/"
    "samples/databases/adventure-works/oltp-install-script/"
)
DEFAULT_EXTRACT = Path("eval/datasets/adventureworks/schema_extract.json")
DEFAULT_CACHE = Path.home() / ".cache" / "vault-agent" / "adventureworks"
RECORD_SOURCE = "adventureworks"
HIERARCHY_ROOT = "/"

Fetch = Callable[[str], bytes]


def csv_url(table: str) -> str:
    return f"{CSV_BASE}{table}.csv"


def decode(raw: bytes) -> str:
    """UTF-8 by the script's code page (65001); a BOM, when present, says otherwise."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    return raw.decode("utf-8")


def _field(value: str) -> str | None:
    if value == "":
        return None
    if value == "\x00":
        return HIERARCHY_ROOT
    return value


def read_records(
    text: str, *, field_terminator: str, row_terminator: str, width: int
) -> list[list[str | None]]:
    """The file's records as lists of ``width`` fields, split as the options say (spec §2.2)."""
    rows: list[list[str | None]] = []
    if row_terminator.startswith("&|"):
        chunks = text.split("&|")
        for chunk in chunks[:-1] if text.endswith(("&|", "&|\n", "&|\r\n")) else chunks:
            record = chunk.lstrip("\r\n")  # the line end after the previous terminator
            if record == "":
                continue
            fields = record.split(field_terminator)
            if fields[-1].endswith("\r"):
                fields[-1] = fields[-1][:-1]
            rows.append([_field(f) for f in fields])
    else:
        pending: list[str] = []
        for line in text.split(row_terminator):
            pending.append(line)
            joined = row_terminator.join(pending)
            fields = joined.split(field_terminator)
            if len(fields) < width:
                continue  # an embedded line feed; the record continues on the next line
            pending = []
            if fields[-1].endswith("\r"):
                fields[-1] = fields[-1][:-1]
            if len(fields) == 1 and fields[0] == "":
                continue  # the empty tail after the last terminator
            rows.append([_field(f) for f in fields])
        if pending and any(p.strip() for p in pending):
            raise ValueError(f"incomplete last record: {row_terminator.join(pending)[:80]!r}")
    for row in rows:
        if len(row) != width:
            raise ValueError(f"record has {len(row)} fields, the table {width}: {row[:3]!r}…")
    return rows


def convert(value: str | None, postgres_type: str) -> str | None:
    """The one conversion the DDL's types need: `varbinary` hex to PostgreSQL's spelling."""
    if value is None:
        return None
    if postgres_type == "bytea" and value[:2].lower() == "0x":
        return "\\x" + value[2:]
    return value


def _qualified(table: dict[str, Any]) -> str:
    return f'"{table["schema"]}"."{table["name"]}"'


def copy_sql(table: dict[str, Any]) -> str:
    """``COPY`` into the DDL's columns, lowercase and quoted — the spelling the generated
    projects' unquoted references fold to on PostgreSQL."""
    columns = ", ".join(f'"{c["name"].lower()}"' for c in table["columns"])
    return f"COPY {_qualified(table)} ({columns}) FROM STDIN WITH (FORMAT csv, NULL '')"


def csv_payload(rows: list[list[str | None]]) -> io.StringIO:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    out.seek(0)
    return out


def audit_columns_sql(table: dict[str, Any]) -> str:
    return (
        f'ALTER TABLE {_qualified(table)} ADD COLUMN "load_datetime" timestamp NOT NULL '
        f'DEFAULT now(), ADD COLUMN "record_source" text NOT NULL DEFAULT {RECORD_SOURCE!r};'
    )


def _statements(ddl: str) -> list[str]:
    return [s.strip() for s in ddl.split(";\n") if s.strip()]


def _fetch_http(url: str) -> bytes:
    import httpx

    response = httpx.get(url, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    return response.content


def load(
    connection: Any,
    extract: dict[str, Any],
    csv_dir: Path,
    *,
    fetch: Fetch | None = None,
    tables: set[str] | None = None,
    log: Callable[[str], None] = lambda _: None,
) -> dict[str, int]:
    """Create the catalogue, copy every table, apply the keys; ``{schema.table: rows}``."""
    fetch = fetch or _fetch_http
    chosen = [t for t in extract["tables"] if tables is None or t["name"] in tables]
    subset = {**extract, "tables": chosen}
    aliases = extract.get("user_defined_types", {})
    csv_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with connection.cursor() as cur:
        for statement in _statements(render_ddl(subset, foreign_keys=False, fold_columns=True)):
            cur.execute(statement)
        for table in chosen:
            cur.execute(audit_columns_sql(table))
        connection.commit()
        for table in chosen:
            path = csv_dir / f"{table['name']}.csv"
            if not path.is_file():
                log(f"fetching {path.name}")
                path.write_bytes(fetch(csv_url(table["name"])))
            options = table.get("bulk_insert") or {}
            rows = read_records(
                decode(path.read_bytes()),
                field_terminator=options.get("field_terminator", "\t"),
                row_terminator=options.get("row_terminator", "\n"),
                width=len(table["columns"]),
            )
            types = [pg_type(c["type"], aliases) for c in table["columns"]]
            converted = [[convert(v, t) for v, t in zip(row, types, strict=True)] for row in rows]
            if converted:
                cur.copy_expert(copy_sql(table), csv_payload(converted))
            counts[f"{table['schema']}.{table['name']}"] = len(converted)
            log(f"{table['schema']}.{table['name']}: {len(converted)} rows")
            connection.commit()
        for statement in _statements(render_foreign_keys(subset, fold_columns=True)):
            cur.execute(statement)
        connection.commit()
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="postgresql://user:pw@host:port/database")
    parser.add_argument("--extract", type=Path, default=DEFAULT_EXTRACT)
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CACHE,
                        help="where the CSVs are, or are fetched to")
    parser.add_argument("--tables", default="", help="comma-separated table names (default: all)")
    parser.add_argument("--replace", action="store_true",
                        help="drop the five business schemas first (never the default)")
    args = parser.parse_args()
    extract = json.loads(args.extract.read_text(encoding="utf-8"))
    tables = {t for t in args.tables.split(",") if t} or None

    import psycopg2

    connection = psycopg2.connect(args.url)
    try:
        if args.replace:
            with connection.cursor() as cur:
                for schema in sorted({t["schema"] for t in extract["tables"]}):
                    cur.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            connection.commit()
        counts = load(
            connection, extract, args.csv_dir, tables=tables, log=lambda m: print(m, flush=True)
        )
    finally:
        connection.close()
    print(f"loaded {len(counts)} table(s), {sum(counts.values())} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
