"""Requirements drafted from the source catalogue (WP117, ADR-0019) — a document a human corrects.

A customer with a catalogue and no documents cannot start a run: the modeler's rule is *model only
what the requirements support*. ADR-0019 decided against a source-driven mode and for a command:
this module writes a requirements document from the declared schema — deterministic, no prompt —
marked as a draft nobody has reviewed, and a human corrects it before the normal run takes it as
any document. The rules are the C1 experiment's instrument
(`eval.adventureworks.draft_requirements`, 2026-10-30), promoted here and read back by the eval,
so the six drafted documents regenerate from this code.

**The rules.** A table is a *relationship* when two or more foreign keys cover its primary key, a
*subtype* when exactly one does, else an *entity* identified by its first declared unique key that
is not a row GUID (the type decides, never the name), else by its primary key. Columns are named in
words, never by physical name; one requirement per described column, the undescribed columns of a
table in one, one per foreign key; the table's and the columns' comments verbatim. Technical
columns — named by the caller, or of a GUID type — are stated once per entity, never as attributes.
No sentence the catalogue did not say.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ValidationError

from vault_agent.state import ForeignKeyRef, SourceColumn, SourceTable

DRAFT_MARKER = "vault-agent: drafted-from-catalogue"
# A unique key on a column of one of these types is a row GUID, never an identifier (ADR-0019 §2).
GUID_TYPES = ("uniqueidentifier", "uuid")
DATETIME_TYPES = ("datetime", "timestamp", "date", "smalldatetime")

Kind = Literal["relationship", "subtype", "entity"]


class DraftHeader(BaseModel):
    """The typed mark at the top of a drafted document: where it came from, when, and whether a
    human has reviewed it. `run` reads it (the parser flags an unreviewed draft); the human
    sets ``status: reviewed`` when the correction is done."""

    source: str
    date: str
    status: Literal["unreviewed", "reviewed"] = "unreviewed"

    def render(self) -> str:
        return (
            f"<!-- {DRAFT_MARKER}\nsource: {self.source}\ndate: {self.date}\n"
            f"status: {self.status} -->\n"
        )


_HEADER_RE = re.compile(r"\A\s*<!--\s*" + re.escape(DRAFT_MARKER) + r"[ \t]*\n(.*?)-->", re.S)


def read_draft_header(text: str) -> DraftHeader | None:
    """The header of a drafted document, or None for any other document (an analyst's, a
    comment that is not ours, a malformed header — never a guess)."""
    match = _HEADER_RE.match(text)
    if match is None:
        return None
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    try:
        return DraftHeader.model_validate(fields)
    except ValidationError:
        return None


def words(name: str) -> str:
    """``SalesOrderHeader`` → *sales order header*; ``BusinessEntityID`` → *business entity id*."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name)
    return spaced.replace("_", " ").lower()


def _columns(table: SourceTable) -> list[SourceColumn]:
    return [c if isinstance(c, SourceColumn) else SourceColumn(name=c) for c in table.columns]


def _type_of(table: SourceTable, column: str) -> str:
    for c in _columns(table):
        if c.name == column:
            return (c.type or "").lower()
    return ""


def _is_guid(table: SourceTable, column: str) -> bool:
    return _type_of(table, column).startswith(GUID_TYPES)


def classify(table: SourceTable) -> tuple[Kind, list[ForeignKeyRef]]:
    """``(kind, the foreign keys covering the primary key)``."""
    pk = set(table.primary_key)
    covering = [fk for fk in table.foreign_keys if set(fk.columns) & pk]
    covered: set[str] = set().union(*(set(fk.columns) for fk in covering)) if covering else set()
    if pk and pk <= covered:
        return ("subtype" if len(covering) == 1 else "relationship"), covering
    return "entity", covering


def natural_key(table: SourceTable) -> list[str] | None:
    """The first declared unique key that is not a row GUID — the type decides (ADR-0019 §2:
    a catalogue read by `source-schema` carries ``rowguid``'s unique index, which the eval's
    derivation dropped). The instrument's rule as measured: the first such key, of any arity."""
    for key in table.unique_keys:
        if key and not all(_is_guid(table, c) for c in key):
            return list(key)
    return None


class _Draft:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.n = 0

    def req(self, text: str) -> None:
        self.n += 1
        self.lines.append(f"- **REQ-{self.n:03d}** {text}")

    def text(self, line: str = "") -> None:
        self.lines.append(line)


def _key_phrase(columns: Sequence[str]) -> str:
    if len(columns) == 1:
        return f"its **{words(columns[0])}**"
    return "the combination of " + ", ".join(f"**{words(c)}**" for c in columns)


def _technical_sentence(table: SourceTable, technical: list[str]) -> str | None:
    """Once per entity: what the technical columns are — a last-changed timestamp, a row
    identifier that is not a business key, anything else by name."""
    if not technical:
        return None
    pieces: list[str] = []
    if any(_type_of(table, c).startswith(DATETIME_TYPES) for c in technical):
        pieces.append("a last-changed timestamp")
    if any(_is_guid(table, c) for c in technical):
        pieces.append("a technical row identifier, which is not a business key")
    other = [
        c for c in technical
        if not _type_of(table, c).startswith(DATETIME_TYPES) and not _is_guid(table, c)
    ]
    if other:
        pieces.append("the technical column(s) " + ", ".join(f"**{words(c)}**" for c in other))
    return "Each {name} carries " + " and ".join(pieces) + "."


def draft_document(
    tables: Sequence[SourceTable],
    area: str,
    *,
    source: str,
    date: str,
    status: Literal["unreviewed", "reviewed"] = "unreviewed",
    technical: Sequence[str] = (),
) -> str:
    """The drafted document for ``tables`` (in their order), headed by the typed mark."""
    d = _Draft()
    d.text(DraftHeader(source=source, date=date, status=status).render())
    d.text(f"# Requirements drafted from the source catalogue: {words(area)}")
    d.text()
    d.text(f"**Area:** {area}  ")
    d.text("**Prepared by:** nobody — drafted from the catalogue  ")
    d.text(f"**Status:** Draft, {status}")
    d.text()
    d.text("## 1. Purpose")
    d.text()
    d.text(
        f"The business needs to analyse what the {words(area)} area of the operational system "
        "records. This document lists what that area records, as the system's own catalogue "
        "describes it: its tables, what identifies each, what each records, and how they refer "
        "to one another. It states nothing the catalogue does not."
    )
    d.text()
    d.text("## 2. Business entities in scope")
    d.text()
    d.text("| Concept | What the catalogue says it is |")
    d.text("|---|---|")
    for table in tables:
        kind, _ = classify(table)
        label = {
            "relationship": " (a relationship)", "subtype": " (a kind of another concept)",
        }.get(kind, "")
        what = table.comment or "(no description in the catalogue)"
        d.text(f"| {words(table.table).capitalize()}{label} | {what} |")
    d.text()
    for index, table in enumerate(tables, start=3):
        kind, covering = classify(table)
        name = words(table.table)
        d.text(f"## {index}. {name.capitalize()}")
        d.text()
        if table.comment:
            d.text(table.comment)
            d.text()
        columns = _columns(table)
        tech = [c.name for c in columns if c.name in technical or _is_guid(table, c.name)]
        described = [c for c in columns if c.name not in tech]
        key_columns = set(table.primary_key)
        fk_columns = {c for fk in table.foreign_keys for c in fk.columns}
        if kind == "relationship":
            parties = ", ".join(f"**{words(fk.references_table)}**" for fk in covering)
            d.req(f"The business must record which {parties} are related, as a **{name}**.")
            d.req(f"Each {name} is identified by {_key_phrase(table.primary_key)}.")
        elif kind == "subtype":
            parent = words(covering[0].references_table)
            same = (
                f"the same **{words(table.primary_key[0])}**" if len(table.primary_key) == 1
                else "the same " + _key_phrase(table.primary_key)
            )
            d.req(f"The business must record every **{name}**. Every {name} is a **{parent}** and "
                  f"is identified by {same}.")
        else:
            d.req(f"The business must record every **{name}**.")
            key = natural_key(table) or table.primary_key
            if key:
                d.req(f"Each {name} is identified by {_key_phrase(key)}.")
        identifying = set(key_columns)
        if kind == "entity":
            identifying |= set(natural_key(table) or [])
        attributes = [
            c for c in described if c.name not in identifying and c.name not in fk_columns
        ]
        for column in attributes:
            if column.comment:
                d.req(f"The business must record the **{words(column.name)}** of each {name}: "
                      f"{column.comment}")
        undescribed = [words(c.name) for c in attributes if not c.comment]
        if undescribed:
            listed = ", ".join(f"**{u}**" for u in undescribed)
            d.req(f"The business must also record, for each {name}: {listed}.")
        for fk in table.foreign_keys:
            if kind != "entity" and fk in covering:
                continue
            via = ", ".join(words(c) for c in fk.columns)
            d.req(f"Each {name} refers to one **{words(fk.references_table)}** (by its {via}).")
        sentence = _technical_sentence(table, tech)
        if sentence:
            d.req(sentence.format(name=name))
        d.text()
    return "\n".join(d.lines).rstrip() + "\n"
