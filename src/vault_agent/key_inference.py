"""Keys inferred from data (WP99, C27 stage 3, ADR-0018). **This module reads rows.**

The producer of `SourceTable.inferred_keys`: for every table the declared schema file names,
reflect it, and find (1) the columns unique and non-null over every row, and (2) the inclusion
dependencies — a referencing column every non-null value of which occurs in a key column of
another (or the same) table. An inference, never a declaration: it lands beside the catalogue's
keys under its own key, the proposer reads it with ``provenance="inferred"``, and nobody accepts
it by default (ADR-0018 §4).

Candidates before data (rule 4 of the spec): a pair is checked only when it is a candidate of the
chosen tier — ``name`` (the default: the same compact name, the referencing name ending in the
key's, or the key table's name plus ``ID``) or ``type`` (every pair of the same type family:
complete, expensive, noisy). WP34's rejected ``key_name_only`` tier is not read back in: a name
coincidence is a candidate, and only the anti-join makes it an inference. Where several key
columns contain every value, the one with the fewest distinct values is the inference and the
others are recorded as ``wider`` — an employee is a person before it is a business entity.

Like the profiler, an explicitly invoked, read-only, scoped command (ADR-0008 #4); the pipeline
itself still holds no connection."""
from __future__ import annotations

import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from vault_agent.profiler import _kind
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.source_schema_reader import hidden_url
from vault_agent.state import (
    CandidateTier,
    InferredForeignKey,
    InferredKeys,
    InferredUniqueKey,
    SourceTable,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection, Engine

CANDIDATE_TIERS: tuple[str, ...] = ("name", "type")
Warn = Callable[[str], None]


def _stderr(message: str) -> None:
    print(f"infer-keys: {message}", file=sys.stderr)


def compact(name: str) -> str:
    """Letters and digits only, uppercased — the spelling the name rules compare."""
    return re.sub(r"[^0-9A-Za-z]", "", name).upper()


def is_name_candidate(column: str, key_table: str, key_column: str) -> bool:
    """The ``name`` tier: the same compact name; the referencing name ends in the key's name and
    is longer (``ShipToAddressID`` → ``AddressID``); or it is the key table's name plus ``ID``
    (``SalesPersonID`` → ``SalesPerson``'s key, whatever that key is called)."""
    c, k, t = compact(column), compact(key_column), compact(key_table)
    return c == k or (len(c) > len(k) and c.endswith(k)) or c == t + "ID"


@dataclass(frozen=True)
class _Key:
    """One key column the inclusion check may reference: declared or inferred unique."""

    schema: str
    table: str
    column: sa.Column[Any]
    distinct: int


@dataclass
class _Reflected:
    declared: SourceTable
    table: sa.Table
    row_count: int
    counts: dict[str, tuple[int, int]]  # column -> (non-null, distinct)


def _declared_unique(table: SourceTable) -> set[str]:
    """The declared single-column keys, normalised: primary or unique."""
    keys = set()
    if len(table.primary_key) == 1:
        keys.add(normalize_identifier(table.primary_key[0]))
    for key in table.unique_keys:
        if len(key) == 1:
            keys.add(normalize_identifier(key[0]))
    return keys


def _reflect(
    connection: Connection, engine: Engine, declared: SourceTable, warn: Warn
) -> _Reflected | None:
    schema = declared.schema_name
    try:
        table = sa.Table(declared.table, sa.MetaData(), schema=schema, autoload_with=engine)
    except sa.exc.NoSuchTableError:
        warn(f"{schema}.{declared.table}: not in the database, left without inferences")
        return None
    columns = list(table.columns)
    expressions: list[Any] = [sa.func.count()]
    for column in columns:
        expressions += [sa.func.count(column), sa.func.count(sa.distinct(column))]
    try:
        [row] = connection.execute(sa.select(*expressions).select_from(table)).all()
    except sa.exc.DBAPIError:
        connection.rollback()
        warn(f"{schema}.{declared.table}: the database refused its counts, left without inferences")
        return None
    counts = {
        str(column.name): (int(row[1 + 2 * i]), int(row[2 + 2 * i]))
        for i, column in enumerate(columns)
    }
    return _Reflected(declared, table, int(row[0]), counts)


def _inclusion_holds(
    connection: Connection, referencing: sa.Column[Any], key: sa.Column[Any], warn: Warn,
    label: str,
) -> bool:
    """``count(*) FROM R WHERE R.c IS NOT NULL AND NOT EXISTS (SELECT 1 FROM T WHERE T.k = R.c)``
    is zero — the anti-join of the spec's rule 4."""
    statement = (
        sa.select(sa.func.count())
        .select_from(referencing.table)
        .where(referencing.isnot(None), ~sa.exists().where(key == referencing))
    )
    try:
        violations = connection.execute(statement).scalar_one()
    except sa.exc.DBAPIError as exc:
        connection.rollback()
        warn(f"{label}: the database refused the inclusion check ({type(exc.orig).__name__})")
        return False
    return int(violations) == 0


def infer_keys(
    engine: Engine,
    tables: Sequence[SourceTable],
    *,
    candidates: str = "name",
    warn: Warn = _stderr,
) -> list[SourceTable]:
    """The declared tables with ``inferred_keys`` attached — an ``InferredKeys`` on every table
    the database holds (empty when nothing was inferred), ``None`` kept where it does not."""
    if candidates not in CANDIDATE_TIERS:
        raise ValueError(f"candidates must be one of {', '.join(CANDIDATE_TIERS)}: {candidates!r}")
    ordered = sorted(tables, key=lambda t: (t.schema_name or "", t.table))
    with engine.connect() as connection:
        reflected: dict[str, _Reflected] = {}
        for declared in ordered:
            found = _reflect(connection, engine, declared, warn)
            if found is not None:
                reflected[_handle(declared)] = found
        # Rule 3: unique columns, over more than one row, never a declared key.
        unique: dict[str, list[InferredUniqueKey]] = {}
        keys: list[_Key] = []
        for handle, r in reflected.items():
            declared_keys = _declared_unique(r.declared)
            unique[handle] = []
            for column in r.table.columns:
                non_null, distinct = r.counts[str(column.name)]
                key = _Key(r.declared.schema_name or "", r.declared.table, column, distinct)
                is_declared = normalize_identifier(str(column.name)) in declared_keys
                if r.row_count > 0 and non_null == r.row_count and distinct == r.row_count:
                    if is_declared:
                        keys.append(key)
                    elif r.row_count > 1:
                        unique[handle].append(
                            InferredUniqueKey(columns=[str(column.name)], rows=r.row_count)
                        )
                        keys.append(key)
                elif is_declared and non_null > 0:
                    keys.append(key)
        keys.sort(key=lambda k: (k.schema, k.table, str(k.column.name)))
        # Rule 4: inclusion dependencies, the tightest domain wins, the wider ones recorded.
        foreign: dict[str, list[InferredForeignKey]] = {}
        for handle, r in reflected.items():
            foreign[handle] = []
            declared_pairs = {
                (normalize_identifier(fk.columns[0]), normalize_identifier(fk.references_table),
                 normalize_identifier(fk.references_columns[0]))
                for fk in r.declared.foreign_keys if fk.is_single_column
            }
            for column in r.table.columns:
                name = str(column.name)
                non_null, distinct = r.counts[name]
                if non_null == 0 or _kind(column.type) == "other":
                    continue
                holding: list[_Key] = []
                for key in keys:
                    if key.column is column or _kind(key.column.type) != _kind(column.type):
                        continue
                    tier: CandidateTier = "name" if is_name_candidate(
                        name, key.table, str(key.column.name)
                    ) else "type"
                    if tier == "type" and candidates != "type":
                        continue
                    if (normalize_identifier(name), normalize_identifier(key.table),
                            normalize_identifier(str(key.column.name))) in declared_pairs:
                        continue
                    if _inclusion_holds(
                        connection, column, key.column, warn,
                        f"{r.declared.schema_name}.{r.declared.table}.{name} ⊆ "
                        f"{key.table}.{key.column.name}",
                    ):
                        holding.append(key)
                if not holding:
                    continue
                tightest = min(k.distinct for k in holding)
                group = sorted(
                    (k for k in holding if k.distinct == tightest),
                    key=lambda k: _tie_preference(name, k),
                )
                key, tied = group[0], group[1:]
                wider = sorted(
                    (k for k in holding if k.distinct > tightest),
                    key=lambda k: (k.distinct, k.table, str(k.column.name)),
                )
                foreign[handle].append(InferredForeignKey(
                    columns=[name], references_table=key.table,
                    references_columns=[str(key.column.name)], references_schema=key.schema,
                    rows=non_null, distinct=distinct, referenced_distinct=key.distinct,
                    candidate="name" if is_name_candidate(
                        name, key.table, str(key.column.name)
                    ) else "type",
                    tied=[f"{k.table}.{k.column.name}" for k in tied],
                    wider=[f"{k.table}.{k.column.name}" for k in wider],
                ))
    return [
        t.model_copy(update={"inferred_keys": InferredKeys(
            unique=unique[_handle(t)], foreign=foreign[_handle(t)],
        )}) if _handle(t) in reflected else t
        for t in tables
    ]


def _tie_preference(column: str, key: _Key) -> tuple[int, int, str, str]:
    """Equal domains cannot be told apart by data; the stated preference breaks the tie: a key
    column named after its own table first (`Product.ProductID` before
    `ProductProductPhoto.ProductID`), then the table the referencing column names, then the
    name. The alternatives travel as ``tied`` either way."""
    key_name = compact(str(key.column.name))
    table_name = compact(key.table)
    return (
        0 if key_name == table_name + "ID" else 1,
        0 if compact(column) == table_name + "ID" else 1,
        key.table,
        str(key.column.name),
    )


def _handle(table: SourceTable) -> str:
    return f"{table.schema_name or ''}.{table.table}"


def provenance(url: str, schema_header: str, *, candidates: str) -> str:
    """The written file's header: the schema file's own first line kept, the inference named."""
    first = schema_header.splitlines()[0] if schema_header else ""
    return (
        (first + "\n" if first else "")
        + f"inferred keys by vault-agent infer-keys from {hidden_url(url)} — candidates: "
        f"{candidates}; unique columns over all rows, inclusion dependencies by anti-join; an "
        "inference, not a declaration (ADR-0018). Edit freely, the loader validates."
    )
