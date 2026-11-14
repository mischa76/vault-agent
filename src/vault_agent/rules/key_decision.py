"""The key of a hub, decided from evidence before the modeler runs (WP125, ADR-0021).

Until 2026-11-14 the key was the modeler's choice: the key agent ranked candidates, the prompt
said to prefer the higher-scored one, and on the 5.5 models the modeler keyed `hub_product` on
`ProductID` against `REQ-001` and a score of 0.95 for `ProductNumber` — in its first attempt,
because every referencing relation carries only the id (C63). The key is no longer a preference
weighed by a model. It is decided here, per declared table, from two pieces of evidence — what
the requirements say (the candidates) and what the source guarantees (the declared keys) — and
only where they disagree is a human asked, with the declared natural key as the default.

Pure and recomputed wherever it is read (the checkpoint, the modeler, the validator): the only
stored input of its own is ``VaultAgentState.key_answers``.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from vault_agent.rules.dv2_rules import _type_base, hub_key_columns, normalize_identifier
from vault_agent.state import (
    BusinessKeyCandidate,
    KeyAnswer,
    KeyDecision,
    SourceColumn,
    SourceTable,
    VaultAgentState,
)

# The type decides, never the name (ADR-0019 §2 said it for the row GUID; ADR-0021 for the key).
GUID_TYPES = frozenset({"uniqueidentifier", "uuid"})
# Where the catalogue does not say whether a column is generated (WP127), an exact numeric key
# is taken as the source system's own: an identity, a sequence, a serial — an integer, or the
# `numeric` / `number` an Oracle or Db2 identity sits on.
INTEGER_TYPES = frozenset({
    "int", "integer", "bigint", "smallint", "tinyint", "serial", "bigserial", "smallserial",
    "decimal", "numeric", "number",
})
CHARACTER_TYPES = frozenset({
    "char", "nchar", "varchar", "nvarchar", "text", "ntext", "string", "character", "bpchar",
})

ColumnKind = Literal["technical", "natural", "unknown"]
KeyAnswerErrorCode = Literal["unknown_table", "unknown_column", "no_column", "reason_required"]


def fold(name: str) -> str:
    """Case- and separator-insensitive: ``product number`` and ``ProductNumber`` are one name."""
    return normalize_identifier(name).replace("_", "")


def _column(table: SourceTable, name: str) -> SourceColumn | None:
    wanted = fold(name)
    return next((c for c in table.column_refs if fold(c.name) == wanted), None)


def _references_technical(
    table: SourceTable, column: str, tables: Sequence[SourceTable],
    _seen: frozenset[tuple[str, str]] = frozenset(),
) -> bool:
    """Is the column a single-column foreign key onto a technical column of another declared
    table? A subtype's primary key is its supertype's. Cycle-safe."""
    here = (fold(table.table), fold(column))
    if here in _seen:
        return False
    by_name = {fold(t.table): t for t in tables}
    for fk in table.foreign_keys:
        if not fk.is_single_column or fold(fk.columns[0]) != here[1]:
            continue
        target = by_name.get(fold(fk.references_table))
        if target is not None and target is not table and column_kind(
            target, fk.references_columns[0], tables, _seen | {here}
        ) == "technical":
            return True
    return False


def column_kind(
    table: SourceTable, column: str, tables: Sequence[SourceTable],
    _seen: frozenset[tuple[str, str]] = frozenset(),
) -> ColumnKind:
    """Is this column a key the source system made up, one the business uses, or neither?

    Technical: a GUID; a column the catalogue says is generated (WP127); a single-column
    foreign key onto a technical column of another table; an exact numeric. Natural: a
    character column that is none of these. Anything else — no declared type, a date, a
    `hierarchyid` — is evidence for neither."""
    ref = _column(table, column)
    if ref is None:
        return "unknown"
    base = _type_base(ref.type)
    # WP127: a column the catalogue says is generated is technical whatever its type. The
    # converse is NOT read: `generated: false` says only that THIS database does not generate
    # the value — a landing zone, a replica or a data copy reports it for every column of a
    # source whose keys are identities (measured on the AdventureWorks copy, 2026-11-14).
    if base in GUID_TYPES or ref.generated is True:
        return "technical"
    if _references_technical(table, column, tables, _seen):
        return "technical"
    if base in INTEGER_TYPES:
        return "technical"
    if base in CHARACTER_TYPES:
        return "natural"
    return "unknown"


def _unique_columns(table: SourceTable) -> list[SourceColumn]:
    """The declared single-column unique keys that are not nullable — a single-column primary
    key first, then the unique keys in declaration order."""
    declared = ([table.primary_key] if len(table.primary_key) == 1 else []) + [
        key for key in table.unique_keys if len(key) == 1
    ]
    seen: set[str] = set()
    columns: list[SourceColumn] = []
    for (name,) in declared:
        ref = _column(table, name)
        if ref is None or ref.nullable is True or fold(name) in seen:
            continue
        seen.add(fold(name))
        columns.append(ref)
    return columns


def natural_keys(table: SourceTable, tables: Sequence[SourceTable]) -> list[str]:
    """The declared single-column unique keys a hub may be keyed on without anyone naming
    them: natural (a character column that is not technical) and not nullable."""
    return [
        ref.name for ref in _unique_columns(table)
        if column_kind(table, ref.name, tables) == "natural"
    ]


def admissible_keys(table: SourceTable, tables: Sequence[SourceTable]) -> list[str]:
    """The declared single-column unique keys the requirements may name as the key: not
    technical. Wider than :func:`natural_keys` by the columns whose type says nothing — a
    computed column the catalogue stores as ``AS``, a ``hierarchyid``, an untyped file: there
    the requirements' first choice is the evidence that the business uses it."""
    return [
        ref.name for ref in _unique_columns(table)
        if column_kind(table, ref.name, tables) != "technical"
    ]


def is_subtype(table: SourceTable) -> bool:
    """A table whose single-column primary key is a declared foreign key onto another table:
    its rows are identified through the supertype's. Whether such a table has a hub of its own
    at all is the resolver's question (WP29, WP38) and WP50's gate, so no key is decided."""
    if len(table.primary_key) != 1:
        return False
    pk = fold(table.primary_key[0])
    return any(
        fk.is_single_column and fold(fk.columns[0]) == pk
        and fold(fk.references_table) != fold(table.table)
        for fk in table.foreign_keys
    )


def _composite_unique(table: SourceTable) -> list[str]:
    return ["+".join(key) for key in table.unique_keys if len(key) > 1]


def _candidates(
    table: SourceTable, tables: Sequence[SourceTable], business_keys: Sequence[BusinessKeyCandidate]
) -> list[tuple[str, float]]:
    """The requirements' candidates on this table as (declared column, score), best first: the
    field is a column of the table, and the entity is the table's name or no other declared
    table has a column of that name."""
    columns = {fold(c): c for c in table.column_names}
    elsewhere = {
        fold(c) for other in tables if other is not table for c in other.column_names
    }
    found: dict[str, float] = {}
    for candidate in business_keys:
        field = fold(candidate.field)
        if field not in columns:
            continue
        if fold(candidate.entity) != fold(table.table) and field in elsewhere:
            continue
        name = columns[field]
        found[name] = max(found.get(name, float("-inf")), candidate.score)
    return sorted(found.items(), key=lambda item: -item[1])


def _answer(state: VaultAgentState, table: SourceTable) -> KeyAnswer | None:
    wanted = fold(table.table)
    return next((a for name, a in state.key_answers.items() if fold(name) == wanted), None)


def _existing_hub_key(state: VaultAgentState, table: SourceTable) -> list[str] | None:
    """The key of the existing vault's hub built from this table — the hub OF the table (its
    ``source_entity``), not one the table merely feeds."""
    if state.existing_model is None:
        return None
    wanted = fold(table.table)
    for hub in state.existing_model.hubs:
        if fold(hub.source_entity or "") == wanted:
            columns = hub_key_columns(hub)
            return [(_column(table, c) or SourceColumn(name=c)).name for c in columns]
    return None


def decide_keys(state: VaultAgentState) -> list[KeyDecision]:
    """One decision per declared table of this increment that has evidence to decide on."""
    tables = state.source_schemas
    decisions: list[KeyDecision] = []
    for table in tables:
        pk = list(table.primary_key)
        answer = _answer(state, table)
        existing = _existing_hub_key(state, table)
        pk_kind: ColumnKind = (
            column_kind(table, pk[0], tables) if len(pk) == 1 else "unknown"
        )
        naturals = natural_keys(table, tables)
        admissible = {fold(k) for k in admissible_keys(table, tables)}
        natural_folded = {fold(k) for k in naturals}
        ranked = _candidates(table, tables, state.business_keys)
        first, first_score = ranked[0] if ranked else (None, None)
        common: dict[str, Any] = {
            "table": table.table,
            "primary_key": pk,
            "primary_key_technical": pk_kind == "technical",
            "natural_keys": naturals,
            "first_choice": first,
            "first_choice_score": first_score,
        }
        named = (
            f"the requirements' first choice is {first} ({first_score:.2f})"
            if first is not None and first_score is not None
            else "the requirements name no column of this table as its identifier"
        )
        declared = (
            f"{table.table} declares {', '.join(naturals)} unique"
            if naturals else f"{table.table} declares no natural key"
        )
        if existing is not None:
            decisions.append(KeyDecision(
                **common, columns=existing, basis="existing",
                evidence=[f"a hub of the existing vault is built from {table.table}; "
                          f"an existing hub is never re-keyed"],
            ))
        elif answer is not None:
            decisions.append(KeyDecision(
                **common, columns=list(answer.columns),
                basis="catalogue_default" if answer.by_default else "human",
                reason=answer.reason,
                evidence=[named, declared] + (
                    ["answered in bulk: the declared natural key was taken"]
                    if answer.by_default else ["named by a human at the resolution checkpoint"]
                ),
            ))
        elif not pk or is_subtype(table):
            continue  # no declared key; or a subtype, identified through its supertype
        elif first is not None and fold(first) in admissible:
            decisions.append(KeyDecision(
                **common, columns=[first], basis="agreed",
                evidence=[named, f"{first} is a declared unique key of {table.table}"],
            ))
        elif len(pk) == 1 and fold(pk[0]) in natural_folded:
            decisions.append(KeyDecision(
                **common, columns=[naturals[0]], basis="natural_primary_key",
                evidence=[named, f"{pk[0]} is {table.table}'s primary key and a natural key"],
            ))
        elif naturals and pk_kind == "technical":
            in_naturals = [name for name, _ in ranked if fold(name) in natural_folded]
            default = in_naturals[0] if in_naturals else naturals[0]
            composite = _composite_unique(table)
            decisions.append(KeyDecision(
                **common, columns=[default], basis="contested", pending=True,
                evidence=[
                    named, declared,
                    f"{pk[0]} is {table.table}'s primary key, a technical key",
                ] + ([f"also declared unique: {', '.join(composite)}"] if composite else []),
            ))
    return decisions


def pending_key_decisions(state: VaultAgentState) -> list[KeyDecision]:
    """The contested keys nobody has answered — what the resolution checkpoint pauses for.
    Pure, and safe above ``interrupt()``."""
    return [d for d in decide_keys(state) if d.pending]


def given_keys(state: VaultAgentState) -> list[KeyDecision]:
    """The decisions the modeler is given and the gate enforces: taken, and about a hub this
    run may build (an existing hub's key is the merger's concern)."""
    return [d for d in decide_keys(state) if not d.pending and d.basis != "existing"]


@dataclass(frozen=True)
class KeyAnswerError:
    """Why an answer was refused — a typed code for the caller, a sentence for the human."""

    code: KeyAnswerErrorCode
    message: str


def check_key_answer(
    state: VaultAgentState, table_name: str, columns: Sequence[str], reason: str | None
) -> KeyAnswerError | None:
    """Is ``Table=Column[+Column]`` an answer that can be applied? Checked before anything
    resumes (WP73's rule). A reason is required for the technical primary key where a natural
    key is declared, and for columns the catalogue does not declare unique."""
    tables = state.source_schemas
    table = next((t for t in tables if fold(t.table) == fold(table_name)), None)
    if table is None:
        return KeyAnswerError(
            "unknown_table",
            f"{table_name}: no table of that name is declared in this run's source schema",
        )
    if not columns:
        return KeyAnswerError("no_column", f"{table_name}: the answer names no column")
    missing = [c for c in columns if _column(table, c) is None]
    if missing:
        return KeyAnswerError(
            "unknown_column",
            f"{table.table}: {', '.join(missing)} is not a declared column of the table",
        )
    if reason and reason.strip():
        return None
    chosen = [fold(c) for c in columns]
    naturals = natural_keys(table, tables)
    if len(chosen) == 1 and chosen[0] in {fold(k) for k in naturals}:
        return None
    declared = [[fold(c) for c in key] for key in [table.primary_key, *table.unique_keys] if key]
    if chosen not in declared:
        return KeyAnswerError(
            "reason_required",
            f"{table.table}: {'+'.join(columns)} is not a declared unique key — say why it "
            f"identifies a row (--key-reason \"{table.table}=…\")",
        )
    if naturals:
        return KeyAnswerError(
            "reason_required",
            f"{table.table}: {'+'.join(columns)} is not a natural key although the table "
            f"declares {', '.join(naturals)} unique — say why "
            f"(--key-reason \"{table.table}=…\")",
        )
    return None


def canonical_answer(
    state: VaultAgentState, table_name: str, columns: Sequence[str]
) -> tuple[str, list[str]]:
    """The answer in the catalogue's own spelling (after :func:`check_key_answer` passed)."""
    table = next(t for t in state.source_schemas if fold(t.table) == fold(table_name))
    return table.table, [(_column(table, c) or SourceColumn(name=c)).name for c in columns]


_BASIS_PHRASE: dict[str, str] = {
    "agreed": "the requirements name it and the catalogue declares it unique",
    "natural_primary_key": "the primary key is itself a natural key",
    "catalogue_default": "the declared natural key, taken as the default of a contested case",
    "human": "named by a human at the resolution checkpoint",
    "existing": "the existing hub's key",
    "contested": "contested, not yet answered",
}


def basis_phrase(decision: KeyDecision) -> str:
    """One clause saying why the key is what it is; presentation only."""
    return _BASIS_PHRASE[decision.basis]


def key_remedy(hub_name: str, actual: Sequence[str], decision: KeyDecision) -> str:
    """What the re-model loop is told when a hub's key is not the decided one."""
    decided = ", ".join(decision.columns)
    return (
        f"Key {hub_name} on {decided} — {basis_phrase(decision)}; it is given, not a "
        f"suggestion. Take {decided} out of the attributes of {hub_name}'s satellites (it is "
        f"the key now). Leave every satellite and link read from a relation that references "
        f"{decision.table} by {', '.join(actual)} exactly as it is: staging joins {decided} in "
        f"through the declared foreign key."
    )
