"""The declared source schema read from the source system's catalogue (WP96, C27 stage 1).

The producer that `source_schema.py` is the consumer of: connect to the source database, read
what its catalogue says about the named schemas — tables, columns in ordinal order with the
vendor's type spelling and nullability, column comments, primary and unique keys, foreign keys —
and write the house ``source_schemas:`` file the loader validates. Transcription, never
interpretation (spec §2 rule 1): no key is inferred, no GUID excluded, no name normalised.

One seam (ADR-0017): :func:`read_source_schema` takes a :class:`CatalogueReader`, a protocol of
eight methods; :class:`InspectorReader` is SQLAlchemy's ``Inspector`` behind it, which is what the
command uses and what the keyless tests run on SQLite. A reader that is not a database reflection
(SAP's dictionary, C27 tier C) implements the same protocol later. Metadata only: nothing here
reads a row, and the protocol has no method that could."""
from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, Protocol

import yaml
from sqlalchemy.types import UserDefinedType

from vault_agent.state import ForeignKeyRef, SourceColumn, SourceTable

if TYPE_CHECKING:
    from sqlalchemy.engine import Dialect, Engine, Inspector
    from sqlalchemy.sql.type_api import TypeEngine

SOURCE_URL_ENV = "VAULT_AGENT_SOURCE_URL"


@dataclass(frozen=True)
class ReadColumn:
    """One column as the catalogue states it — the type already spelled, ``""`` when unknown."""

    name: str
    type: str
    nullable: bool
    comment: str | None = None


@dataclass(frozen=True)
class ReadForeignKey:
    """One declared foreign key; ``referenced_schema`` is ``None`` when the catalogue omits it."""

    columns: list[str]
    referenced_table: str
    referenced_columns: list[str]
    referenced_schema: str | None = None


class CatalogueReader(Protocol):
    """What the reader needs from a catalogue. Any method may raise ``NotImplementedError`` for
    a catalogue that cannot say — recorded as nothing, never as a failure."""

    @property
    def default_schema(self) -> str | None: ...

    def schema_names(self) -> list[str]: ...

    def table_names(self, schema: str) -> list[str]: ...

    def view_names(self, schema: str) -> list[str]: ...

    def columns(self, table: str, schema: str) -> list[ReadColumn]: ...

    def primary_key(self, table: str, schema: str) -> list[str]: ...

    def unique_keys(self, table: str, schema: str) -> list[list[str]]: ...

    def foreign_keys(self, table: str, schema: str) -> list[ReadForeignKey]: ...

    def table_comment(self, table: str, schema: str) -> str | None: ...


class InspectorReader:
    """SQLAlchemy's ``Inspector`` behind the protocol (``sqlalchemy/engine/reflection.py``,
    2.1.6 as installed: ``get_table_names``, ``get_view_names``, ``get_columns``,
    ``get_pk_constraint``, ``get_unique_constraints``, ``get_indexes``, ``get_foreign_keys``)."""

    def __init__(self, inspector: Inspector) -> None:
        self._inspector = inspector

    @property
    def default_schema(self) -> str | None:
        return self._inspector.default_schema_name

    def schema_names(self) -> list[str]:
        return list(self._inspector.get_schema_names())

    def table_names(self, schema: str) -> list[str]:
        return list(self._inspector.get_table_names(schema=schema))

    def view_names(self, schema: str) -> list[str]:
        return list(self._inspector.get_view_names(schema=schema))

    @staticmethod
    def type_name(type_: TypeEngine[Any], dialect: Dialect) -> str:
        """The vendor's spelling, lowercased, as the dialect compiles it; a type the dialect did
        not recognise (``NullType``) is ``""`` — unknown, never guessed."""
        from sqlalchemy.sql import sqltypes

        if isinstance(type_, sqltypes.NullType):
            return ""
        return str(type_.compile(dialect=dialect)).lower()

    def columns(self, table: str, schema: str) -> list[ReadColumn]:
        dialect = self._inspector.dialect
        return [
            ReadColumn(
                name=column["name"],
                type=self.type_name(column["type"], dialect),
                nullable=bool(column["nullable"]),
                comment=column.get("comment") or None,
            )
            for column in self._inspector.get_columns(table, schema=schema)
        ]

    def primary_key(self, table: str, schema: str) -> list[str]:
        return list(self._inspector.get_pk_constraint(table, schema=schema)["constrained_columns"])

    def unique_keys(self, table: str, schema: str) -> list[list[str]]:
        """Unique constraints, then unique indexes that are not a constraint's own index and
        name only columns (an expression index has ``None`` among its names)."""
        keys = [
            list(constraint["column_names"])
            for constraint in self._inspector.get_unique_constraints(table, schema=schema)
        ]
        for index in self._inspector.get_indexes(table, schema=schema):
            names = index["column_names"]
            if not index.get("unique") or index.get("duplicates_constraint") or None in names:
                continue
            keys.append([name for name in names if name is not None])
        return keys

    def foreign_keys(self, table: str, schema: str) -> list[ReadForeignKey]:
        return [
            ReadForeignKey(
                columns=list(fk["constrained_columns"]),
                referenced_table=fk["referred_table"],
                referenced_columns=list(fk["referred_columns"]),
                referenced_schema=fk.get("referred_schema"),
            )
            for fk in self._inspector.get_foreign_keys(table, schema=schema)
        ]

    def table_comment(self, table: str, schema: str) -> str | None:
        """WP97: the table's own comment (``get_table_comment``, ``reflection.py`` 1330 —
        ``ReflectedTableComment.text``); a dialect without comments raises, the caller records
        nothing."""
        return self._inspector.get_table_comment(table, schema=schema)["text"] or None


class CatalogueType(UserDefinedType[Any]):
    """A type the vendor's catalogue names and SQLAlchemy's dialect has no class for — spelled
    as the catalogue spells it, nothing more. Registered per vendor in :data:`DIALECT_TYPES` the
    way the dialect documents it (``ischema_names``; GeoAlchemy2 registers its geometry types so),
    because the dialect otherwise reflects such a column as ``NullType`` — the measurement of
    2026-10-30 found PostgreSQL's ``xml`` so, on seven AdventureWorks columns."""

    cache_ok = True

    def __init__(self, name: str) -> None:
        self.name = name

    def get_col_spec(self, **kw: Any) -> str:
        return self.name


DIALECT_TYPES: dict[str, dict[str, Callable[..., CatalogueType]]] = {
    "postgresql": {"xml": partial(CatalogueType, "xml")},
}


def register_catalogue_types(dialect: Dialect) -> None:
    """Give the dialect instance the catalogue types it lacks (the class attribute untouched)."""
    extra = DIALECT_TYPES.get(dialect.name)
    if extra:
        names = getattr(dialect, "ischema_names", None)
        if isinstance(names, dict):
            dialect.ischema_names = {**names, **extra}  # type: ignore[attr-defined]


def source_engine(url: str) -> Engine:
    """The engine for a source URL, its dialect given the catalogue types it lacks. Raises what
    ``create_engine`` raises — ``ModuleNotFoundError`` for a driver that is not installed,
    ``NoSuchModuleError`` for a dialect SQLAlchemy does not know; the dialect's
    ``OperationalError`` on a refused connection comes from the first read. Shared with the
    profiler (WP98), which is the one caller that reads rows through it."""
    from sqlalchemy import create_engine

    engine = create_engine(url)
    register_catalogue_types(engine.dialect)
    return engine


def inspector_reader(url: str) -> InspectorReader:
    """Connect by SQLAlchemy URL (see :func:`source_engine` for what it raises)."""
    from sqlalchemy import inspect

    return InspectorReader(inspect(source_engine(url)))


def hidden_url(url: str) -> str:
    """The URL with its password hidden — the only form that reaches a message or a file."""
    from sqlalchemy.engine import make_url

    return make_url(url).render_as_string(hide_password=True)


def database_of(url: str) -> str | None:
    from sqlalchemy.engine import make_url

    return make_url(url).database or None


def _nothing_on(method: Any, *args: Any) -> Any:
    try:
        return method(*args)
    except NotImplementedError:
        return None


def read_source_schema(
    reader: CatalogueReader,
    *,
    schemas: Sequence[str],
    database: str | None,
    views: bool = False,
) -> list[SourceTable]:
    """Every table (and, on ``views``, every view) of the named schemas as the catalogue states
    it — deterministic: tables by (schema, name), columns in ordinal order, unique keys and
    foreign keys sorted (spec §2 rule 2)."""
    relations: list[tuple[str, str, bool]] = []
    for schema in schemas:
        relations.extend((schema, name, True) for name in reader.table_names(schema))
        if views:
            relations.extend((schema, name, False) for name in reader.view_names(schema) or [])
    tables: list[SourceTable] = []
    for schema, name, is_table in sorted(relations, key=lambda r: (r[0], r[1])):
        columns = [
            SourceColumn(name=c.name, type=c.type, nullable=c.nullable, comment=c.comment)
            for c in reader.columns(name, schema)
        ]
        primary_key: list[str] = []
        unique_keys: list[list[str]] = []
        foreign_keys: list[ForeignKeyRef] = []
        if is_table:
            primary_key = list(_nothing_on(reader.primary_key, name, schema) or [])
            seen: set[tuple[str, ...]] = {tuple(primary_key)} if primary_key else set()
            for key in _nothing_on(reader.unique_keys, name, schema) or []:
                if key and tuple(key) not in seen:
                    seen.add(tuple(key))
                    unique_keys.append(list(key))
            unique_keys.sort()
            for fk in _nothing_on(reader.foreign_keys, name, schema) or []:
                foreign_keys.append(
                    ForeignKeyRef(
                        columns=list(fk.columns),
                        references_table=fk.referenced_table,
                        references_columns=list(fk.referenced_columns),
                        references_schema=fk.referenced_schema or reader.default_schema or schema,
                    )
                )
            foreign_keys.sort(key=lambda f: (f.columns, f.references_table))
        tables.append(
            SourceTable(
                table=name,
                schema=schema,
                database=database,
                columns=list(columns),
                foreign_keys=foreign_keys,
                primary_key=primary_key,
                unique_keys=unique_keys,
                comment=_nothing_on(reader.table_comment, name, schema) or None,
            )
        )
    return tables


def _entry(table: SourceTable) -> dict[str, Any]:
    """The house file's shape: empty lists and absent values omitted, as the derivation omits
    them (``eval/adventureworks/derive.py``)."""
    columns: list[dict[str, Any]] = []
    for column in table.column_refs:
        entry: dict[str, Any] = {"name": column.name, "type": column.type}
        if column.nullable is not None:
            entry["nullable"] = column.nullable
        if column.comment:
            entry["comment"] = column.comment
        columns.append(entry)
    declared: dict[str, Any] = {"table": table.table, "schema": table.schema_name}
    if table.database:
        declared["database"] = table.database
    if table.comment:
        declared["comment"] = table.comment
    declared["columns"] = columns
    if table.primary_key:
        declared["primary_key"] = list(table.primary_key)
    if table.unique_keys:
        declared["unique_keys"] = [list(key) for key in table.unique_keys]
    if table.foreign_keys:
        declared["foreign_keys"] = [
            {
                "columns": list(fk.columns),
                "references_table": fk.references_table,
                "references_columns": list(fk.references_columns),
                "references_schema": fk.references_schema,
            }
            for fk in table.foreign_keys
        ]
    return declared


def render_source_schema(tables: Sequence[SourceTable], *, header: str) -> str:
    """The file: a comment header (provenance, no timestamp) and ``source_schemas:``."""
    lines = "".join(f"# {line}\n" for line in header.splitlines())
    return lines + yaml.safe_dump(
        {"source_schemas": [_entry(t) for t in tables]}, sort_keys=False, allow_unicode=True,
        width=100,
    )


def provenance(url: str, schemas: Sequence[str], *, views: bool) -> str:
    what = "tables and views" if views else "tables"
    return (
        f"read by vault-agent source-schema from {hidden_url(url)} — "
        f"schemas {', '.join(schemas)}; {what}.\n"
        "A declared source schema is an input: edit freely, the loader validates."
    )


def warn_unknown_types(tables: Sequence[SourceTable]) -> None:
    for table in tables:
        for column in table.column_refs:
            if column.type == "":
                print(
                    f"source-schema: {table.schema_name}.{table.table}.{column.name}: the dialect "
                    "did not recognise the type; declared empty, not guessed",
                    file=sys.stderr,
                )
