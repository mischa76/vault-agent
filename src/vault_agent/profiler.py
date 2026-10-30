"""Profiling read from the source system (WP98, C27 stage 2). **This module reads rows.**

The producer of the file `profiling.py` loads: connect to the source database, and for every
table of the named schemas compute the statistics the mapper and the validator read — exact
aggregates over all rows by SQL (``count(*)``, ``count(c)``, ``count(distinct c)``), plus the
selectable checks of spec §2 rule 3: ``range`` (numeric and temporal columns only; a character
minimum is a row value), ``lengths`` (character columns), ``patterns`` (value shapes from a sample)
and ``examples`` (off by default — the one check that writes a character column's values). It is
the explicitly invoked, read-only, scoped step ADR-0008 #4 permits, and it is a command, never a
capability of the pipeline: no agent gains a connection, and the catalogue reader's protocol
(`source_schema_reader.py`) stays row-less.

Nothing is written that was not measured (rule 5): one statement per table carries every
aggregate; a database that refuses it (PostgreSQL has no equality operator for ``xml``) is asked
column by column, and a column it still refuses is omitted and named on stderr — never zeroed,
because ``uniqueness_ratio: 0.0`` reads as evidence of a non-key."""
from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
import yaml
from sqlalchemy.sql import sqltypes

from vault_agent.source_schema_reader import hidden_url
from vault_agent.state import ColumnProfile, ValuePattern

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection, Engine

CHECKS: tuple[str, ...] = ("range", "lengths", "patterns", "examples")
DEFAULT_CHECKS: tuple[str, ...] = ("range", "lengths", "patterns")
DEFAULT_SAMPLE = 10_000
DEFAULT_EXAMPLES = 3
SHAPE_LENGTH = 32
PATTERNS_KEPT = 5
RATIO_PLACES = 6

Fetch = Callable[[sa.Executable], Sequence[sa.Row[Any]]]
Warn = Callable[[str], None]


@dataclass(frozen=True)
class TableProfile:
    """One table's statistics: the house file's per-table entry."""

    schema: str
    table: str
    row_count: int
    columns: list[ColumnProfile]


def _stderr(message: str) -> None:
    print(f"profile: {message}", file=sys.stderr)


def value_shape(text: str) -> str:
    """The shape of a value: every digit ``9``, every letter ``A``, every other character kept,
    cut at :data:`SHAPE_LENGTH`."""
    return "".join(
        "9" if ch.isdigit() else "A" if ch.isalpha() else ch for ch in text[:SHAPE_LENGTH]
    )


def _kind(type_: Any) -> str:
    """``number``, ``temporal``, ``text`` or ``other`` — by SQLAlchemy's reflected type class."""
    if isinstance(type_, sqltypes.Integer | sqltypes.Numeric | sqltypes.Float):
        return "number"
    if isinstance(type_, sqltypes.Date | sqltypes.DateTime | sqltypes.Time):
        return "temporal"
    if isinstance(type_, sqltypes.String):
        return "text"
    return "other"


def _render(value: Any) -> str:
    """A statistic as text, the vendor's value spelled plainly: integers as they are, decimals
    without trailing zeros, dates and times ISO."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, float):
        return f"{value:.15g}"
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    return str(value)


def _stats(column: sa.Column[Any], checks: Collection[str]) -> list[str]:
    """The statistics measured for ``column`` beyond the counts, in statement order."""
    kind = _kind(column.type)
    names: list[str] = []
    if "range" in checks and kind in ("number", "temporal"):
        names += ["min", "max"]
    if "lengths" in checks and kind == "text":
        names += ["min_length", "max_length"]
    return names


def _expressions(column: sa.Column[Any], names: Sequence[str]) -> list[Any]:
    length = sa.func.char_length(column)
    by_name = {
        "min": sa.func.min(column), "max": sa.func.max(column),
        "min_length": sa.func.min(length), "max_length": sa.func.max(length),
    }
    return [sa.func.count(column), sa.func.count(sa.distinct(column))] + [
        by_name[name] for name in names
    ]


def _column_profile(
    column: sa.Column[Any], names: Sequence[str], values: Sequence[Any], row_count: int
) -> ColumnProfile:
    non_null, distinct = int(values[0]), int(values[1])
    measured = dict(zip(names, values[2:], strict=True))
    kw: dict[str, Any] = {}
    for name in ("min", "max"):
        if measured.get(name) is not None:
            kw[name] = _render(measured[name])
    for name in ("min_length", "max_length"):
        if measured.get(name) is not None:
            kw[name] = int(measured[name])
    return ColumnProfile(
        name=str(column.name),  # a reflected name is a `quoted_name`; the file wants str
        uniqueness_ratio=round(distinct / non_null, RATIO_PLACES) if non_null else 0.0,
        null_ratio=round(1 - non_null / row_count, RATIO_PLACES) if row_count else 0.0,
        distinct_count=distinct,
        **kw,
    )


def _sample(
    fetch: Fetch, table: sa.Table, columns: Sequence[sa.Column[Any]], *, sample: int, warn: Warn
) -> dict[str, list[Any]]:
    """The sampled values per column — the first ``sample`` rows the database returns (rule 4);
    on refusal column by column, a column still refused is left without a sample."""
    if not columns:
        return {}
    try:
        rows = fetch(sa.select(*columns).select_from(table).limit(sample))
        return {c.name: [row[i] for row in rows] for i, c in enumerate(columns)}
    except sa.exc.DBAPIError:
        pass
    sampled: dict[str, list[Any]] = {}
    for column in columns:
        try:
            rows = fetch(sa.select(column).select_from(table).limit(sample))
            sampled[column.name] = [row[0] for row in rows]
        except sa.exc.DBAPIError as exc:
            warn(f"{table.fullname}.{column.name}: no sample, the database refused it "
                 f"({type(exc.orig).__name__})")
    return sampled


def profile_relation(
    fetch: Fetch,
    table: sa.Table,
    *,
    checks: Collection[str],
    sample: int,
    examples: int,
    warn: Warn = _stderr,
) -> TableProfile:
    """One table's profile through ``fetch`` (a callable that executes a statement and returns
    its rows — the seam the keyless tests refuse statements through)."""
    columns = list(table.columns)
    plan = {c.name: _stats(c, checks) for c in columns}
    profiles: dict[str, ColumnProfile] = {}
    try:
        expressions: list[Any] = [sa.func.count()]
        for column in columns:
            expressions += _expressions(column, plan[column.name])
        [row] = fetch(sa.select(*expressions).select_from(table))
        row_count = int(row[0])
        position = 1
        for column in columns:
            width = 2 + len(plan[column.name])
            profiles[column.name] = _column_profile(
                column, plan[column.name], row[position:position + width], row_count
            )
            position += width
    except sa.exc.DBAPIError:
        [row] = fetch(sa.select(sa.func.count()).select_from(table))
        row_count = int(row[0])
        for column in columns:
            try:
                [row] = fetch(
                    sa.select(*_expressions(column, plan[column.name])).select_from(table)
                )
                profiles[column.name] = _column_profile(column, plan[column.name], row, row_count)
            except sa.exc.DBAPIError as exc:
                warn(f"{table.fullname}.{column.name}: omitted, the database refused its "
                     f"statistics ({type(exc.orig).__name__})")
    wants_patterns, wants_examples = "patterns" in checks, "examples" in checks and examples > 0
    to_sample = [
        c for c in columns if c.name in profiles and (
            (wants_patterns and _kind(c.type) == "text")
            or (wants_examples and _kind(c.type) != "other")
        )
    ]
    sampled = _sample(fetch, table, to_sample, sample=sample, warn=warn) if to_sample else {}
    for column in to_sample:
        values = [v for v in sampled.get(column.name, []) if v is not None]
        update: dict[str, Any] = {}
        if wants_patterns and _kind(column.type) == "text" and values:
            shapes = Counter(value_shape(str(v)) for v in values)
            ranked = sorted(shapes.items(), key=lambda item: (-item[1], item[0]))[:PATTERNS_KEPT]
            update["patterns"] = [
                ValuePattern(shape=shape, share=round(count / len(values), RATIO_PLACES))
                for shape, count in ranked
            ]
        if wants_examples and values:
            seen: list[str] = []
            for value in values:
                text = _render(value)
                if text not in seen:
                    seen.append(text)
                if len(seen) == examples:
                    break
            update["example_values"] = seen
        if update:
            profiles[column.name] = profiles[column.name].model_copy(update=update)
    return TableProfile(
        schema=str(table.schema or ""),
        table=str(table.name),
        row_count=row_count,
        columns=[profiles[c.name] for c in columns if c.name in profiles],
    )


def _fetcher(connection: Connection) -> Fetch:
    """Execute on one connection; a refused statement leaves no aborted transaction behind
    (PostgreSQL refuses every statement after a failed one until a rollback)."""
    def fetch(statement: sa.Executable) -> Sequence[sa.Row[Any]]:
        try:
            return connection.execute(statement).all()
        except sa.exc.DBAPIError:
            connection.rollback()
            raise
    return fetch


def select_tables(
    engine: Engine, *, schemas: Sequence[str], tables: Sequence[str] | None
) -> tuple[list[tuple[str, str]], list[str]]:
    """The (schema, table) pairs to profile, sorted, and the names of ``tables`` the catalogue
    lacks. A name is ``Schema.Table`` or bare (then any of the named schemas)."""
    inspector = sa.inspect(engine)
    available = [(s, name) for s in schemas for name in sorted(inspector.get_table_names(s))]
    if tables is None:
        return available, []
    chosen: list[tuple[str, str]] = []
    missing: list[str] = []
    for wanted in tables:
        schema, _, bare = wanted.rpartition(".")
        hits = [
            (s, t) for s, t in available if t == bare and (not schema or s == schema)
        ]
        if hits:
            chosen.extend(hit for hit in hits if hit not in chosen)
        else:
            missing.append(wanted)
    return sorted(chosen), missing


def profile_tables(
    engine: Engine,
    *,
    schemas: Sequence[str],
    tables: Sequence[str] | None,
    checks: Collection[str],
    sample: int,
    examples: int,
    warn: Warn = _stderr,
) -> list[TableProfile]:
    """Every selected table, in (schema, name) order, each reflected and profiled on one
    connection. Unknown table names are the caller's to refuse (:func:`select_tables`)."""
    selected, _ = select_tables(engine, schemas=schemas, tables=tables)
    profiles: list[TableProfile] = []
    with engine.connect() as connection:
        fetch = _fetcher(connection)
        for schema, name in selected:
            reflected = sa.Table(name, sa.MetaData(), schema=schema, autoload_with=engine)
            profiles.append(profile_relation(
                fetch, reflected, checks=checks, sample=sample, examples=examples, warn=warn
            ))
    return profiles


def _column_entry(profile: ColumnProfile) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": profile.name,
        "uniqueness_ratio": profile.uniqueness_ratio,
        "null_ratio": profile.null_ratio,
        "distinct_count": profile.distinct_count,
    }
    for name in ("min", "max", "min_length", "max_length"):
        value = getattr(profile, name)
        if value is not None:
            entry[name] = value
    if profile.patterns:
        entry["patterns"] = [{"shape": p.shape, "share": p.share} for p in profile.patterns]
    if profile.example_values:
        entry["example_values"] = list(profile.example_values)
    return entry


def render_profiling(profiles: Sequence[TableProfile], *, header: str) -> str:
    """The file `load_profiling` reads: a comment header (provenance, no timestamp) and
    ``tables:`` — ``table`` the bare name as the catalogue spells it, ``schema`` and
    ``row_count`` beside it (per-table keys the loader ignores), a statistic present only when
    it was measured."""
    lines = "".join(f"# {line}\n" for line in header.splitlines())
    document = {"tables": [
        {
            "table": p.table, "schema": p.schema, "row_count": p.row_count,
            "columns": [_column_entry(c) for c in p.columns],
        }
        for p in profiles
    ]}
    return lines + yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=100)


def provenance(
    url: str,
    schemas: Sequence[str],
    tables: Sequence[str],
    *,
    checks: Collection[str],
    sample: int,
    examples: int,
) -> str:
    scope = f"schemas {', '.join(schemas)}" + (f"; tables {', '.join(tables)}" if tables else "")
    selected = ", ".join(c for c in CHECKS if c in checks) or "none"
    return (
        f"read by vault-agent profile from {hidden_url(url)} — {scope}.\n"
        f"checks: counts always and exact over all rows, then {selected}; shapes and examples "
        f"from a sample {sample} rows, the first the database returns; examples per column: "
        f"{examples}.\n"
        "Profiling evidence is an input: edit freely, the loader validates. A statistic absent "
        "here was not measured."
    )
