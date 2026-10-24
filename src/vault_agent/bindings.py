"""WP82 — bindings at sign-off: the relation a stage reads and the column aliases it needs, as a
human ratifies them in the CLI (``resume --bind``), the workbench and the interactive prompt.

One grammar, one check, one payload for every path (WP12's capability-parity rule):

* ``STAGE=RELATION`` binds the stage to a declared relation;
* ``STAGE=RELATION(STAGE_COLUMN=column, …)`` adds aliases — the relation carries a key the stage
  names otherwise (``BUSINESSENTITYID=SalesPersonID``), rendered as derived columns (WP41).

The check runs before anything resumes: a stage this run has, a declared relation, alias targets
the relation declares, and — WP73's rule — every column the stage hashes or derives present in
the relation after the aliases. An error names the stage, the relation and the columns.
"""
from __future__ import annotations

import re
from typing import Any

from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import FlagKind, SourceTable, StageBinding, VaultAgentState

_SPEC = re.compile(
    r"^\s*(?P<stage>[^=()\s]+)\s*=\s*(?P<relation>[^=()\s]+)\s*(?:\((?P<aliases>.*)\))?\s*$"
)
_ALIAS = re.compile(r"^\s*(?P<stage_column>[^=\s,]+)\s*=\s*(?P<column>[^=\s,]+)\s*$")


def parse_bind(spec: str) -> tuple[str, StageBinding]:
    """Parse ``STAGE=RELATION`` or ``STAGE=RELATION(STAGE_COLUMN=column, …)``."""
    match = _SPEC.match(spec)
    if match is None:
        raise ValueError(
            f"invalid --bind {spec!r}; expected 'STAGE=RELATION' or "
            f"'STAGE=RELATION(STAGE_COLUMN=column, …)'"
        )
    columns: dict[str, str] = {}
    aliases = match.group("aliases")
    if aliases is not None:
        for part in aliases.split(","):
            alias = _ALIAS.match(part)
            if alias is None:
                raise ValueError(
                    f"invalid --bind {spec!r}; an alias is 'STAGE_COLUMN=column' "
                    f"(got {part.strip()!r})"
                )
            columns[alias.group("stage_column")] = alias.group("column")
    return match.group("stage"), StageBinding(relation=match.group("relation"), columns=columns)


def format_bind(stage: str, binding: StageBinding) -> str:
    """The inverse of :func:`parse_bind` — what a run's CLI equivalent records."""
    if not binding.columns:
        return f"{stage}={binding.relation}"
    aliases = ", ".join(f"{k}={v}" for k, v in binding.columns.items())
    return f"{stage}={binding.relation}({aliases})"


def coerce_bindings(raw: Any) -> dict[str, StageBinding]:
    """The decision payload's ``bindings`` as typed bindings; anything malformed is left out."""
    out: dict[str, StageBinding] = {}
    if not isinstance(raw, dict):
        return out
    for stage, value in raw.items():
        if isinstance(value, StageBinding):
            out[str(stage)] = value
        elif (
            isinstance(value, dict) and isinstance(value.get("relation"), str) and value["relation"]
        ):
            columns = value.get("columns") or {}
            if isinstance(columns, dict) and all(
                isinstance(k, str) and isinstance(v, str) for k, v in columns.items()
            ):
                out[str(stage)] = StageBinding(relation=value["relation"], columns=dict(columns))
        elif isinstance(value, str) and value:
            out[str(stage)] = StageBinding(relation=value)
    return out


def stage_key_needs(meta: dict[str, Any]) -> list[str]:
    """The relation columns a stage's KEYS read, from its stored metadata: every hash key's
    source column(s) and every derived column's source (the validator's WP73 reading of the same
    metadata). Hashdiff attributes are not keys. Order kept, duplicates dropped."""
    needs: list[str] = []

    def add(column: Any) -> None:
        text = str(column)
        if text not in needs:
            needs.append(text)

    derived = meta.get("derived_columns") or {}
    for value in (meta.get("hashed_columns") or {}).values():
        if isinstance(value, dict):
            continue  # a hashdiff
        for column in (value if isinstance(value, list) else [value]):
            if str(column) in derived:
                continue  # read through the derived column; its own source is added below
            add(column)
    for value in derived.values():
        add(value.get("source_column") if isinstance(value, dict) else value)
    return needs


def declared_relations(state: VaultAgentState) -> dict[str, SourceTable]:
    """Every relation a stage may bind to, the increment's tables before the carried ones."""
    out: dict[str, SourceTable] = {}
    for table in [*state.source_schemas, *state.carried_schemas]:
        out.setdefault(normalize_identifier(table.table), table)
    return out


def check_stage_bindings(
    state: VaultAgentState, bindings: dict[str, StageBinding]
) -> list[str]:
    """Why a binding cannot be applied — ``[]`` when every one can. One message per defect."""
    staging = state.artifacts.automatedv_yaml.get("staging") or {}
    relations = declared_relations(state)
    errors: list[str] = []
    for stage, binding in bindings.items():
        meta = staging.get(stage)
        if not isinstance(meta, dict):
            errors.append(f"{stage}: no staging model of that name in this run")
            continue
        table = relations.get(normalize_identifier(binding.relation))
        if table is None:
            errors.append(f"{stage}: {binding.relation!r} is not a declared relation of this run")
            continue
        columns = {normalize_identifier(c) for c in table.column_names}
        bad_targets = [
            column for column in binding.columns.values()
            if normalize_identifier(column) not in columns
        ]
        if bad_targets:
            errors.append(
                f"{stage}: {binding.relation} declares no column "
                f"{', '.join(repr(c) for c in bad_targets)} for the alias"
            )
            continue
        available = columns | {normalize_identifier(c) for c in binding.columns}
        missing = [
            column for column in stage_key_needs(meta)
            if normalize_identifier(column) not in available
        ]
        if missing:
            errors.append(
                f"{stage}: {binding.relation} declares none of {', '.join(missing)} that the "
                f"stage hashes or derives — name the relation's column for each as an alias "
                f"(STAGE_COLUMN=column)"
            )
    return errors


def pending_stage_bindings(state: VaultAgentState) -> list[dict[str, Any]]:
    """What a human needs to bind a stage no rule could: every inferred stage with the relation it
    reads now, why it is inferred (``rejected`` with the relation WP73 refused, else the WP47
    reason), the key columns the relation must carry, and the review role of its item."""
    staging = state.artifacts.automatedv_yaml.get("staging") or {}
    refused = {f.asset: f.reason for f in state.flags if f.kind == FlagKind.BINDING_REJECTED}
    inferred = {f.asset: f.reason for f in state.flags if f.kind == FlagKind.SOURCE_BINDING}
    out: list[dict[str, Any]] = []
    for stage in sorted(staging):
        meta = staging[stage]
        if not isinstance(meta, dict) or meta.get("source_binding") != "inferred":
            continue
        source = meta.get("source_model")
        reads = next(iter(source.values())) if isinstance(source, dict) else source
        if stage in refused:
            reason, tried = "rejected", refused[stage]
        else:
            reason, tried = str(inferred.get(stage) or "none"), None
        out.append({
            "stage": stage,
            "reads": str(reads or ""),
            "reason": reason,
            "tried": tried,
            "expected_columns": stage_key_needs(meta),
            "role": "decision" if reason in ("rejected", "ambiguous") else "disclosure",
        })
    return out
