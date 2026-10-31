"""WP110 — an AdventureWorks data loader in the repository (C23): Microsoft's CSVs, decoded and
split as the install script's BULK INSERT options say, into PostgreSQL under the DDL instrument's
catalogue, with `load_datetime` and `record_source`. Committed red before the change. Keyless: no
network, no database — the fetch and the connection are injected."""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from eval.adventureworks import extract as extract_mod
from eval.adventureworks import load_postgres as loader
from eval.adventureworks.postgres_ddl import render_ddl, render_foreign_keys
from eval.datasets import DATASETS_ROOT

EXTRACT = json.loads((DATASETS_ROOT / "adventureworks" / "schema_extract.json").read_text())


# ── the install script's options, transcribed ──────────────────────────────────────────────
_SNIPPET = """
BULK INSERT [Production].[Document] FROM '$(SqlSamplesSourceDataPath)Document.csv'
WITH (
    CHECK_CONSTRAINTS,
    CODEPAGE = '65001',
    DATAFILETYPE = 'char',
    FIELDTERMINATOR = '+|',
    ROWTERMINATOR = '&|\\n',
    KEEPIDENTITY,
    TABLOCK
);
BULK INSERT [Production].[ProductReview] FROM '$(SqlSamplesSourceDataPath)ProductReview.csv'
WITH (
    CODEPAGE = '65001',
    DATAFILETYPE = 'char',
    FIELDTERMINATOR = '\\t',
    ROWTERMINATOR = '0x0a',
    TABLOCK
);
BULK INSERT [Sales].[Store] FROM '$(SqlSamplesSourceDataPath)Store.csv'
WITH (
    CODEPAGE = '65001',
    FIELDTERMINATOR= '+|',
    ROWTERMINATOR = '\\n'
);
"""


def test_the_extract_transcribes_the_bulk_insert_options() -> None:
    options = extract_mod.parse_bulk_insert_options(_SNIPPET)
    assert options[("Production", "Document")] == {
        "field_terminator": "+|", "row_terminator": "&|\n", "codepage": "65001",
    }
    assert options[("Production", "ProductReview")] == {
        "field_terminator": "\t", "row_terminator": "\n", "codepage": "65001",  # 0x0a is LF
    }
    assert options[("Sales", "Store")]["field_terminator"] == "+|"


def test_the_checked_in_extract_carries_the_options_for_every_table() -> None:
    tables = EXTRACT["tables"]
    assert len(tables) == 68 and all(t.get("bulk_insert") for t in tables)
    plus = sorted(t["name"] for t in tables if t["bulk_insert"]["field_terminator"] == "+|")
    assert plus == ["BusinessEntity", "BusinessEntityAddress", "BusinessEntityContact", "Document",
                    "EmailAddress", "Illustration", "JobCandidate", "Password", "Person",
                    "PersonPhone", "PhoneNumberType", "ProductModel", "ProductPhoto", "Store"]
    assert all(t["bulk_insert"]["codepage"] == "65001" for t in tables)


# ── decoding and splitting ─────────────────────────────────────────────────────────────────
def test_decode_is_bom_aware_and_utf8_by_default() -> None:
    text = "1\tMüller\n"
    assert loader.decode(text.encode("utf-8")) == text
    assert loader.decode(text.encode("utf-8-sig")) == text
    assert loader.decode(text.encode("utf-16")) == text  # BOM-led UTF-16


def test_plus_pipe_records_keep_embedded_newlines_and_drop_the_crlf_after_them() -> None:
    text = "1+|first line\r\nsecond line+|x&|\r\n2+|+|y&|\r\n"
    rows = loader.read_records(text, field_terminator="+|", row_terminator="&|\n", width=3)
    assert rows == [["1", "first line\r\nsecond line", "x"], ["2", None, "y"]]


def test_tab_records_join_continuation_lines_until_the_width_is_reached() -> None:
    # ProductReview: a comment with an embedded LF under ROWTERMINATOR 0x0a
    text = "1\t709\tJohn\tgreat bike\nreally\t2013-09-18\n2\t937\tDavid\tok\t2013-11-13\r\n"
    rows = loader.read_records(text, field_terminator="\t", row_terminator="\n", width=5)
    assert rows == [["1", "709", "John", "great bike\nreally", "2013-09-18"],
                    ["2", "937", "David", "ok", "2013-11-13"]]


def test_a_nul_only_field_is_the_hierarchy_root() -> None:
    text = "\x00+|Doc&|\n"
    rows = loader.read_records(text, field_terminator="+|", row_terminator="&|\n", width=2)
    assert rows == [["/", "Doc"]]


# ── types and the COPY ────────────────────────────────────────────────────────────────────
def test_values_are_converted_by_the_postgres_type() -> None:
    assert loader.convert("0x89504E47", "bytea") == "\\x89504E47"
    assert loader.convert("1", "boolean") == "1"
    assert loader.convert("abc", "text") == "abc"
    assert loader.convert(None, "bytea") is None


def test_the_copy_names_the_ddl_columns_lowercase_and_quoted() -> None:
    table = next(t for t in EXTRACT["tables"] if t["name"] == "ProductReview")
    sql = loader.copy_sql(table)
    assert sql.startswith('COPY "Production"."ProductReview" ("productreviewid", "productid", ')
    assert sql.endswith('FROM STDIN WITH (FORMAT csv, NULL \'\')')
    payload = loader.csv_payload([["1", None, "a\nb"]])
    assert payload.getvalue() == '1,,"a\nb"\n'


def test_the_ddl_instrument_splits_into_tables_then_foreign_keys_byte_identically() -> None:
    whole = render_ddl(EXTRACT)
    assert render_ddl(EXTRACT, foreign_keys=False) + render_foreign_keys(EXTRACT) != ""
    assert "ADD FOREIGN KEY" not in render_ddl(EXTRACT, foreign_keys=False)
    keys = render_foreign_keys(EXTRACT).count("ADD FOREIGN KEY")
    assert keys == whole.count("ADD FOREIGN KEY") == 90
    folded = render_ddl(EXTRACT, fold_columns=True)
    assert '"businessentityid"' in folded and '"BusinessEntityID"' not in folded
    assert folded.count("\n") == whole.count("\n")  # the same statements, folded names only
    assert loader.audit_columns_sql(EXTRACT["tables"][0]).startswith(
        'ALTER TABLE "HumanResources"."Department" ADD COLUMN "load_datetime" timestamp '
        'NOT NULL DEFAULT now(), '
        'ADD COLUMN "record_source" text NOT NULL DEFAULT \'adventureworks\''
    )


# ── the load, end to end against fakes ─────────────────────────────────────────────────────
class _Cursor:
    def __init__(self, log: list[tuple[str, str]]) -> None:
        self.log = log

    def execute(self, sql: str, params: Any = None) -> None:
        self.log.append(("execute", sql))

    def copy_expert(self, sql: str, file: io.StringIO) -> None:
        self.log.append(("copy", sql + " <<" + file.getvalue() + ">>"))

    def fetchone(self) -> tuple[int]:
        copies = [e for e in self.log if e[0] == "copy"]
        return (copies[-1][1].count("\n") - 1 if copies else 0,)

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class _Connection:
    def __init__(self) -> None:
        self.log: list[tuple[str, str]] = []
        self.committed = 0

    def cursor(self) -> _Cursor:
        return _Cursor(self.log)

    def commit(self) -> None:
        self.committed += 1


def _mini_extract() -> dict[str, Any]:
    tables = [t for t in EXTRACT["tables"] if t["name"] in ("ProductReview", "Product")]
    return {**EXTRACT, "tables": tables}


def test_load_creates_the_catalogue_copies_every_table_and_keys_last(tmp_path: Path) -> None:
    csvs = {
        "Product.csv": b"",  # nothing to load, still created
        "ProductReview.csv": b"1\t709\tJohn\t2013-09-18\tjohn@x\t5\tgreat\nbike\t2013-09-18\n",
    }
    fetched: list[str] = []

    def fetch(url: str) -> bytes:
        fetched.append(url)
        return csvs[url.rsplit("/", 1)[1]]

    conn = _Connection()
    counts = loader.load(conn, _mini_extract(), tmp_path, fetch=fetch)
    assert fetched == [loader.csv_url("Product"), loader.csv_url("ProductReview")]
    assert (tmp_path / "ProductReview.csv").read_bytes() == csvs["ProductReview.csv"]
    kinds = [kind for kind, _ in conn.log]
    first_copy = kinds.index("copy")
    executed = [sql for kind, sql in conn.log if kind == "execute"]
    assert any(sql.startswith("CREATE SCHEMA") for sql in executed[:first_copy])
    # the warehouse's column names are folded — what the generated references resolve to
    assert any('"productreviewid" integer NOT NULL' in sql for sql in executed[:first_copy])
    assert not any('"ProductReviewID"' in sql for sql in executed)
    assert any("ADD COLUMN \"load_datetime\"" in sql for sql in executed[:first_copy])
    assert all("ADD FOREIGN KEY" not in sql for sql in executed[:first_copy])
    assert any("ADD FOREIGN KEY" in sql for sql in executed[first_copy:])
    copies = [sql for kind, sql in conn.log if kind == "copy"]
    assert len(copies) == 1 and '"great\nbike"' in copies[0]  # the empty table copies nothing
    assert counts == {"Production.Product": 0, "Production.ProductReview": 1}
    assert conn.committed >= 1


def test_a_cached_csv_is_not_fetched_again(tmp_path: Path) -> None:
    (tmp_path / "Product.csv").write_bytes(b"")
    (tmp_path / "ProductReview.csv").write_bytes(b"")
    conn = _Connection()
    def refuse(url: str) -> bytes:
        raise AssertionError(url)

    loader.load(conn, _mini_extract(), tmp_path, fetch=refuse)
    assert [k for k, _ in conn.log].count("copy") == 0
