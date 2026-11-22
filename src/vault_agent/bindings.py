"""WP82 — bindings at sign-off: the relation a stage reads and the column aliases it needs, as a
human ratifies them in the CLI (``resume --bind``), the workbench and the interactive prompt.

One grammar, one check, one payload for every path (WP12's capability-parity rule):

* ``STAGE=RELATION`` binds the stage to a declared relation;
* ``STAGE=RELATION(STAGE_COLUMN=column, …)`` adds aliases — the relation carries a key the stage
  names otherwise (``BUSINESSENTITYID=SalesPersonID``), rendered as derived columns (WP41).

The check runs before anything resumes: a stage this run has, a declared relation, alias targets
the relation declares, and — WP73's rule — every column the stage hashes or derives present in
the relation after the aliases. An error names the stage, the relation and the columns.

WP134 (C70): the validator runs before the sign-off, so a stage bound here was unbound when its
gates looked. The two judgements that read a stage's relation are therefore made here too, from
the same functions the validator calls — what a translated stage reads from its relation
(:func:`binding_needs`) and whether a satellite's key covers a unique key of the relation
(:func:`satellite_grain_gap`). A binding that fails either is refused.
"""
from __future__ import annotations

import re
from typing import Any, NamedTuple

from vault_agent.existing_model import existing_construct_names
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
    metadata). Hashdiff attributes are not keys. Order kept, duplicates dropped.

    WP130 (C66): columns only. A derived column that is a generator expression (WP121's cast,
    WP123's hex of a hashdiff input) contributes the columns its typed ``expression_reads`` entry
    names, never the expression's text — the validator's gate reads this same function."""
    needs: list[str] = []

    def add(column: Any) -> None:
        text = str(column)
        if text not in needs:
            needs.append(text)

    derived = meta.get("derived_columns") or {}
    expression_reads = meta.get("expression_reads") or {}
    for value in (meta.get("hashed_columns") or {}).values():
        if isinstance(value, dict):
            continue  # a hashdiff
        for column in (value if isinstance(value, list) else [value]):
            if str(column) in derived:
                continue  # read through the derived column; its own source is added below
            add(column)
    for name, value in derived.items():
        if name in expression_reads:
            for column in expression_reads[name]:
                add(column)
            continue
        # WP79: an escaped derived column carries its source in the mapping form
        add(value.get("source_column") if isinstance(value, dict) else value)
    return needs


def translation_projects(meta: dict[str, Any]) -> list[str]:
    """The columns a stage's translation view adds to its relation's, from the stored metadata
    (WP132, C68): each join's ``projects`` — one column, or a composite key's list. ``[]`` for a
    stage that reads its relation directly."""
    out: list[str] = []
    for join in (meta.get("key_translation") or {}).get("joins") or []:
        projects = join.get("projects")
        for column in projects if isinstance(projects, list) else [projects]:
            if column and str(column) not in out:
                out.append(str(column))
    return out


def translation_reads(meta: dict[str, Any]) -> dict[str, str] | None:
    """Which column of the stage's own relation each translated key stands for (WP133, C69):
    projected column → the join's ``reads``, normalised. ``{}`` for a stage without a
    translation; ``None`` when a join does not say (metadata stored before WP133) — the caller
    cannot judge such a stage and must not guess from the join's text."""
    out: dict[str, str] = {}
    for join in (meta.get("key_translation") or {}).get("joins") or []:
        reads = join.get("reads")
        if not reads:
            return None
        projects = join.get("projects")
        for column in projects if isinstance(projects, list) else [projects]:
            out[normalize_identifier(str(column))] = normalize_identifier(str(reads))
    return out


def binding_needs(meta: dict[str, Any]) -> list[str]:
    """What a stage's RELATION must carry for its keys (WP134): :func:`stage_key_needs` less the
    columns the stage's translation view projects — they arrive through the view, WP132's reading
    — plus the column each join reads on the relation's side (the typed ``reads``, WP133; a join
    stored without it adds nothing). For a stage without a translation, ``stage_key_needs``."""
    projected = {normalize_identifier(c) for c in translation_projects(meta)}
    needs = [c for c in stage_key_needs(meta) if normalize_identifier(c) not in projected]
    for join in (meta.get("key_translation") or {}).get("joins") or []:
        reads = join.get("reads")
        if reads and str(reads) not in needs:
            needs.append(str(reads))
    return needs


class GrainGap(NamedTuple):
    """A satellite whose key does not cover a unique key of the relation its stage reads."""

    nearest: list[str]  # the relation's unique key the satellite is closest to, as declared
    grain: list[str]  # the relation columns the satellite's key covers, normalised, sorted
    missing: list[str]  # the columns of ``nearest`` the key lacks, as declared


def satellite_grain_gap(
    sat_meta: dict[str, Any], stage_meta: dict[str, Any], table: SourceTable,
    aliases: dict[str, str] | None = None,
) -> GrainGap | None:
    """WP85's judgement, in one place since WP134: does the satellite's key — its parent-hash
    columns and child-dependent key, mapped back to the relation — cover a declared unique key of
    ``table``? ``None`` when it does, and when the satellite is not judged: an effectivity
    satellite (its grain is the driving key), a relation without a declared key, a stage whose
    stored translation does not say what its keys stand for (before WP133 — never guessed).

    A key column is mapped through the stage's derived columns, then through ``aliases`` — a
    sign-off binding's ``{STAGE_COLUMN: relation column}``, which become derived columns once the
    binding is applied — then through the translation's ``reads`` (WP133: a translated key stands
    for the relation's referencing column)."""
    if "src_dfk" in sat_meta or "src_eff" in sat_meta:
        return None
    stands_for = translation_reads(stage_meta)
    if stands_for is None:
        return None
    unique_keys = [k for k in [table.primary_key, *table.unique_keys] if k]
    if not unique_keys:
        return None
    derived = stage_meta.get("derived_columns") or {}
    renamed = {
        normalize_identifier(k): normalize_identifier(v) for k, v in (aliases or {}).items()
    }

    def relation_column(column: str) -> str:
        value = derived.get(column)
        if isinstance(value, dict):
            value = value.get("source_column")
        name = normalize_identifier(str(value if value else column))
        name = renamed.get(name, name)
        return stands_for.get(name, name)

    pk_value = (stage_meta.get("hashed_columns") or {}).get(str(sat_meta.get("src_pk")))
    pk_columns: list[Any] = (
        list(pk_value) if isinstance(pk_value, list) else [pk_value] if pk_value else []
    )
    cdk = sat_meta.get("src_cdk") or []
    grain = {relation_column(str(c)) for c in [*pk_columns, *cdk]}
    if any({normalize_identifier(c) for c in key} <= grain for key in unique_keys):
        return None
    # The key the satellite is closest to: most columns already in its grain, then the fewest
    # missing — a surrogate primary key never wins over the natural unique key.
    nearest = min(
        unique_keys,
        key=lambda k: (
            -len({normalize_identifier(c) for c in k} & grain),
            len({normalize_identifier(c) for c in k} - grain),
        ),
    )
    missing = [c for c in nearest if normalize_identifier(c) not in grain]
    return GrainGap(list(nearest), sorted(grain), missing)


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
    satellites = state.artifacts.automatedv_yaml.get("satellites") or {}
    pre_existing = existing_construct_names(state.existing_model)
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
        # WP134: what the relation itself must carry — a translated stage's projected keys
        # arrive through its view, its referencing columns do not.
        missing = [
            column for column in binding_needs(meta)
            if normalize_identifier(column) not in available
        ]
        if missing:
            errors.append(
                f"{stage}: {binding.relation} declares none of {', '.join(missing)} that the "
                f"stage hashes or derives — name the relation's column for each as an alias "
                f"(STAGE_COLUMN=column)"
            )
            continue
        # WP134 (C70): the grain gate's judgement, which the validator could not make on a stage
        # that was unbound when it ran. One message per binding: the first satellite that fails.
        for sat_name, sat_meta in satellites.items():
            if (
                not isinstance(sat_meta, dict) or sat_meta.get("source_model") != stage
                or sat_name in pre_existing
            ):
                continue
            gap = satellite_grain_gap(sat_meta, meta, table, binding.columns)
            if gap is None:
                continue
            errors.append(
                f"{stage}: {binding.relation} is unique on {' + '.join(gap.nearest)}, but "
                f"{sat_name}, which reads this stage, covers only "
                f"{', '.join(gap.grain) or 'nothing'} — bound to it, {', '.join(gap.missing)} "
                f"would repeat per key and load date and the satellite would re-insert on every "
                f"load (E_SAT_GRAIN_NOT_UNIQUE). Leave the stage unbound and provide a relation "
                f"unique on the satellite's key, or run again with {sat_name} multi-active on "
                f"{', '.join(gap.missing)}"
            )
            break
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
            "expected_columns": binding_needs(meta),  # WP134: of the relation, not the view
            "role": "decision" if reason in ("rejected", "ambiguous") else "disclosure",
        })
    return out
