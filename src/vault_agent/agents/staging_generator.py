"""Staging-layer generator (the spec §9 follow-up: "generates a runnable project").

Deterministically renders one AutomateDV ``stage`` model per staging source the raw-vault
models reference — computing every hash key / hashdiff the hubs, links, and satellites
consume — plus the dbt project scaffolding (dbt_project.yml, packages.yml, a documented
sources.yml, README.md) that turns the output directory into a buildable dbt project.

No LLM is involved: everything here derives from the typed ``DVModel`` with the same
naming rules the raw-vault generator uses, so staging and raw vault can never disagree
about a column name. The one open decision — which raw relation feeds a staging model —
is taken from the declared source schema (ADR-0004) when a table matches, and otherwise
*inferred* as ``raw_<base>`` and flagged for human review (``FlagKind.SOURCE_BINDING``):
the generator names, it never guesses silently.

Called by the CodeGeneratorAgent after the raw-vault pass; kept in its own module so the
raw-vault renderer stays under its size budget and this layer is testable in isolation.
"""
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from vault_agent.rules.dv2_rules import (
    AUTOMATE_DV_VERSION,
    EFFECTIVITY_APPLIED_COLUMN,
    HASHDIFF_SUFFIX,
    LOAD_DATETIME_COLUMN,
    RAW_SOURCE_PREFIX,
    RECORD_SOURCE_COLUMN,
    STAGING_PREFIX,
    canonical_hub_key_column,
    normalize_identifier,
    role_bk_column,
    role_fk_column,
)
from vault_agent.state import DVModel, FlagKind, Hub, HubSource, PipelineFlag, SourceTable

# dbt project/profile name used in the generated scaffolding.
PROJECT_NAME = "vault_project"


@dataclass
class _HashDiff:
    """Marker for a hashdiff entry (rendered with ``is_hashdiff: true``)."""

    columns: list[str]


@dataclass
class StagingSpec:
    """Everything one ``stage`` model needs, collected across the constructs it feeds."""

    name: str  # staging model name, e.g. "stg_customer"
    base: str  # construct base, e.g. "customer"
    # Ordered hashed columns: (name, single source column | multi-column list | _HashDiff).
    hashed: list[tuple[str, str | list[str] | _HashDiff]] = field(default_factory=list)
    derived: dict[str, str] = field(default_factory=dict)  # e.g. APPLIED_DTS -> start date
    source_columns: list[str] = field(default_factory=list)  # expected raw columns, ordered
    source_model: str = ""  # the raw relation this staging reads
    bound: bool = False  # True when matched against a declared source table
    # dbt source block this staging reads through (WP7 §7.2). Set only on grounded runs
    # for specs whose declared table carries a physical location (schema/database); the
    # rendered model then uses automate_dv.stage's source() mapping form instead of a
    # bare relation name.
    source_name: str | None = None

    def add_hashed(self, name: str, value: str | list[str] | _HashDiff) -> None:
        if all(existing != name for existing, _ in self.hashed):
            self.hashed.append((name, value))

    def add_source_column(self, column: str) -> None:
        if column not in self.source_columns:
            self.source_columns.append(column)


@dataclass
class StagingResult:
    models: dict[str, str]  # staging model name -> rendered SQL
    metadata: dict[str, dict[str, object]]  # staging model name -> stage() metadata
    scaffolding: dict[str, str]  # relative output path -> file content
    flags: list[PipelineFlag]


def _to_column(label: str) -> str:
    return normalize_identifier(label)


# Mirrors of the raw-vault generator's naming (kept trivially simple; both sides derive
# from normalize_identifier + the rules/ constants, so they cannot drift apart).
def _base_name(construct_name: str) -> str:
    for prefix in ("hub_", "link_", "sat_"):
        if construct_name.startswith(prefix):
            return construct_name[len(prefix):]
    return construct_name


def _staging_name(construct_name: str) -> str:
    # Normalised through the one identifier helper (WP20 §2.4), the way _sat_staging_model
    # already did — two naming paths that merely happen to agree on well-formed names are a
    # latent split. Byte-identical for every valid construct name (E_BAD_NAME enforces
    # lowercase snake_case, and normalize("account").lower() == "account").
    return STAGING_PREFIX + normalize_identifier(_base_name(construct_name)).lower()


def multi_source_staging_name(hub: Hub, source: HubSource) -> str:
    """Per-source staging model for a multi-source hub (WP10): ``stg_<entity>_<source>``.

    Deterministic and traceable — the source suffix is the feeding table's normalised name,
    so a hub fed by ``crm_customer`` + ``victor_partner`` yields ``stg_customer_crm_customer``
    and ``stg_customer_victor_partner``."""
    return (
        STAGING_PREFIX
        + _base_name(hub.name)
        + "_"
        + normalize_identifier(source.source_table).lower()
    )


def collect_staging_specs(model: DVModel) -> dict[str, StagingSpec]:
    """Group the raw-vault constructs by the staging model that feeds them.

    Mirrors the raw-vault generator's guards (unknown hubs/parents are skipped there and
    therefore need no staging here); insertion order is deterministic: hubs, links, then
    the satellites' additions to their parents' staging models."""
    from vault_agent.agents.code_generator import (
        _hub_hashkey,
        _link_hashkey,
        _sat_staging_model,
    )

    specs: dict[str, StagingSpec] = {}
    hub_by_name = {hub.name: hub for hub in model.hubs}

    def spec_for(construct_name: str) -> StagingSpec:
        name = _staging_name(construct_name)
        if name not in specs:
            specs[name] = StagingSpec(name=name, base=_base_name(construct_name))
        return specs[name]

    for hub in model.hubs:
        if hub.sources:
            # WP10 multi-source: one stg_<entity>_<source> per feed, each aliasing its
            # physical key column to the canonical name and hashing X_HK from it — so the
            # same key value hashes identically across sources (the integration property).
            canonical = canonical_hub_key_column(hub)
            for source in hub.sources:
                name = multi_source_staging_name(hub, source)
                spec = specs.setdefault(name, StagingSpec(name=name, base=_base_name(hub.name)))
                spec.source_model = source.source_table
                spec.bound = True
                src_col = _to_column(source.business_key_column)
                if src_col != canonical:
                    spec.derived[canonical] = src_col  # alias the source column -> canonical
                spec.add_hashed(_hub_hashkey(hub), canonical)
                spec.add_source_column(src_col)
        else:
            spec = spec_for(hub.name)
            bk_col = _to_column(hub.business_key)
            spec.add_hashed(_hub_hashkey(hub), bk_col)
            spec.add_source_column(bk_col)

    generated_links = []
    for link in model.links:
        if any(ref.hub not in hub_by_name for ref in link.hub_refs):
            continue  # the raw-vault generator skips (and flags) this link
        if link.link_type == "transactional" and link.event_timestamp is None:
            continue  # not generated as t_link either
        generated_links.append(link)
        spec = spec_for(link.name)
        bk_cols = []
        for ref in link.hub_refs:
            # Role-qualify both the FK hash key and its source business-key column so a
            # self-referencing link gets two distinct columns (ADR-0009); unqualified refs
            # keep the bare names, so plain-string links stage byte-identically.
            hub = hub_by_name[ref.hub]
            bk_col = role_bk_column(_to_column(hub.business_key), ref.role)
            bk_cols.append(bk_col)
            spec.add_hashed(role_fk_column(_hub_hashkey(hub), ref.role), bk_col)
            spec.add_source_column(bk_col)
        spec.add_hashed(_link_hashkey(link), bk_cols)
        if link.link_type == "transactional":
            for col in link.payload:
                spec.add_source_column(_to_column(col))
            if link.event_timestamp:
                spec.add_source_column(_to_column(link.event_timestamp))

    link_names = {link.name for link in generated_links}
    links_by_name = {link.name: link for link in generated_links}
    for sat in model.satellites:
        if sat.parent not in hub_by_name and sat.parent not in link_names:
            continue  # dangling parent — skipped/flagged by the raw-vault generator
        if sat.source_table and sat.sat_type != "effectivity":
            # WP7 §7.1: the satellite's rows live in their own (usually finer-grain) raw
            # relation — a dedicated staging model, bound VERBATIM to the declared
            # source_table (never inferred, never flagged). It still computes the
            # parent's hash key from the parent's business key(s): those columns existing
            # in the finer-grain relation is what makes the rows attachable.
            name = _sat_staging_model(sat)
            spec = specs.setdefault(
                name, StagingSpec(name=name, base=_base_name(sat.name))
            )
            spec.source_model = sat.source_table
            spec.bound = True
            if sat.parent in hub_by_name:
                parent_hub = hub_by_name[sat.parent]
                bk_col = _to_column(parent_hub.business_key)
                spec.add_hashed(_hub_hashkey(parent_hub), bk_col)
                spec.add_source_column(bk_col)
            else:
                parent_link = links_by_name[sat.parent]
                bk_cols = []
                for ref in parent_link.hub_refs:
                    bk_col = role_bk_column(
                        _to_column(hub_by_name[ref.hub].business_key), ref.role
                    )
                    bk_cols.append(bk_col)
                    spec.add_source_column(bk_col)
                spec.add_hashed(_link_hashkey(parent_link), bk_cols)
            target_specs = [spec]
        else:
            sat_parent_hub = hub_by_name.get(sat.parent)
            if sat_parent_hub is not None and sat_parent_hub.sources:
                # WP10: a satellite on a multi-source hub feeds each per-source staging (one
                # satellite per source is emitted downstream, reading its own staging).
                target_specs = [
                    specs[multi_source_staging_name(sat_parent_hub, source)]
                    for source in sat_parent_hub.sources
                ]
            else:
                target_specs = [spec_for(sat.parent)]
        attr_cols = [_to_column(attr) for attr in sat.attributes]
        for spec in target_specs:
            for col in attr_cols:
                spec.add_source_column(col)
            for key in sat.child_dependent_key:
                spec.add_source_column(_to_column(key))
            if sat.sat_type == "effectivity":
                # Same guard as the raw-vault eff_sat template: needs start+end dates and a
                # link parent. The dedicated src_eff column is DERIVED from the start date so
                # AutomateDV's incremental SQL never projects one column twice (see rules/).
                if sat.parent in link_names and len(attr_cols) >= 2:
                    spec.derived.setdefault(EFFECTIVITY_APPLIED_COLUMN, attr_cols[0])
            else:
                hashdiff_name = _to_column(_base_name(sat.name)) + HASHDIFF_SUFFIX
                spec.add_hashed(hashdiff_name, _HashDiff(columns=attr_cols))

    for spec in specs.values():
        spec.add_source_column(LOAD_DATETIME_COLUMN)
        spec.add_source_column(RECORD_SOURCE_COLUMN)
    return specs


def bind_sources(
    specs: dict[str, StagingSpec],
    source_schemas: list[SourceTable],
    source_overrides: dict[str, str] | None = None,
) -> list[PipelineFlag]:
    """Bind each staging model to its raw relation; flag every *inferred* binding.

    A declared source table matches by normalised name against the construct base or its
    ``raw_<base>`` form; the table name is then used verbatim (source dialect, ADR-0004).
    Without a match the binding is inferred as ``raw_<base>`` and flagged for review.

    ``source_overrides`` (WP9 §6) maps a normalised construct base to the source table a
    ratified/proposed business↔source mapping resolved it to; an override binds the spec
    verbatim and raises no flag (the mapping *is* the human-reviewable evidence)."""
    overrides = source_overrides or {}
    flags: list[PipelineFlag] = []
    for spec in specs.values():
        if spec.bound:
            # Declared on the construct itself (Satellite.source_table, WP7 §7.1):
            # bound verbatim at collection time — no inference, no flag.
            continue
        override = overrides.get(normalize_identifier(spec.base))
        if override:
            spec.source_model = override
            spec.bound = True
            continue
        inferred = RAW_SOURCE_PREFIX + spec.base
        candidates = {normalize_identifier(spec.base), normalize_identifier(inferred)}
        for table in source_schemas:
            if normalize_identifier(table.table) in candidates:
                spec.source_model = table.table
                spec.bound = True
                break
        else:
            spec.source_model = inferred
            flags.append(
                PipelineFlag(
                    agent="code_generator",
                    message=(
                        f"staging model {spec.name!r} assumes raw source "
                        f"{spec.source_model!r} (no declared source table matched); "
                        f"provide it as a seed/table of that name or correct the binding"
                    ),
                    kind=FlagKind.SOURCE_BINDING,
                    asset=spec.name,
                )
            )
    return flags


@dataclass
class SourceBlock:
    """One dbt ``source:`` block in the generated sources.yml (grounded runs, WP7 §7.2)."""

    name: str  # dbt source name: "raw", then "raw_2", ... in first-appearance order
    database: str | None
    schema_name: str | None
    specs: list[StagingSpec] = field(default_factory=list)


def group_sources(
    specs: dict[str, StagingSpec], source_schemas: list[SourceTable]
) -> list[SourceBlock]:
    """Assign bound staging specs to dbt source blocks (grounded runs only, WP7 §7.2).

    A spec joins a block when its bound relation matches a declared table that carries a
    physical location (``schema_name`` and/or ``database``) — only then is a ``source()``
    reference *better* than the bare relation name (a dbt source without a ``schema``
    property defaults its schema to the source's name, which would silently break the
    verified bare-name/seed pattern; unknowns stay bare and documented, never guessed).
    One block per distinct (database, schema) pair, deterministic: blocks appear in
    staging-spec insertion order, named ``raw``, ``raw_2``, ... Ungrounded runs
    (``source_schemas`` empty) return no blocks — output stays byte-identical."""
    if not source_schemas:
        return []
    declared: dict[str, SourceTable] = {}
    for table in source_schemas:
        declared.setdefault(normalize_identifier(table.table), table)
    blocks: dict[tuple[str | None, str | None], SourceBlock] = {}
    for spec in specs.values():
        if not spec.bound:
            continue
        match = declared.get(normalize_identifier(spec.source_model))
        if match is None or (match.schema_name is None and match.database is None):
            continue
        key = (match.database, match.schema_name)
        block = blocks.get(key)
        if block is None:
            name = "raw" if not blocks else f"raw_{len(blocks) + 1}"
            block = SourceBlock(name=name, database=match.database,
                                schema_name=match.schema_name)
            blocks[key] = block
        block.specs.append(spec)
        spec.source_name = block.name
    return list(blocks.values())


def render_stage_model(spec: StagingSpec) -> str:
    """Render one AutomateDV ``stage`` model (the pattern verified by demo/bank_postgres)."""
    binding = "declared source schema" if spec.bound else "inferred — see review queue"
    lines = [
        f"-- Generated AutomateDV staging model for the raw-vault constructs on "
        f"'{spec.base}'.",
        "-- Computes the hash keys / hashdiffs the raw-vault models reference and passes",
        f"-- the source columns through (source binding: {binding}).",
        "{{ config(materialized='view') }}",
        "{%- set yaml_metadata -%}",
    ]
    if spec.source_name:
        # source() mapping form (AutomateDV stage: `source_name: table_name`), bound to
        # the matching block in the generated sources.yml (WP7 §7.2, grounded runs).
        lines.append("source_model:")
        lines.append(f"  {spec.source_name}: '{spec.source_model}'")
    else:
        lines.append(f"source_model: '{spec.source_model}'")
    if spec.derived:
        lines.append("derived_columns:")
        for name, source_col in spec.derived.items():
            lines.append(f"  {name}: '{source_col}'")
    lines.append("hashed_columns:")
    for name, value in spec.hashed:
        if isinstance(value, str):
            lines.append(f"  {name}: '{value}'")
        elif isinstance(value, _HashDiff):
            lines.append(f"  {name}:")
            lines.append("    is_hashdiff: true")
            lines.append("    columns:")
            lines.extend(f"      - '{col}'" for col in value.columns)
        else:
            lines.append(f"  {name}:")
            lines.extend(f"    - '{col}'" for col in value)
    derived_arg = "metadata_dict['derived_columns']" if spec.derived else "none"
    lines.extend(
        [
            "{%- endset -%}",
            "{% set metadata_dict = fromyaml(yaml_metadata) %}",
            "",
            "{{ automate_dv.stage(include_source_columns=true,",
            "                     source_model=metadata_dict['source_model'],",
            f"                     derived_columns={derived_arg},",
            "                     hashed_columns=metadata_dict['hashed_columns'],",
            "                     ranked_columns=none) }}",
        ]
    )
    return "\n".join(lines) + "\n"


def _stage_metadata(spec: StagingSpec) -> dict[str, object]:
    hashed: dict[str, object] = {}
    for name, value in spec.hashed:
        if isinstance(value, _HashDiff):
            hashed[name] = {"is_hashdiff": True, "columns": list(value.columns)}
        elif isinstance(value, list):
            hashed[name] = list(value)
        else:
            hashed[name] = value
    meta: dict[str, object] = {
        "source_model": (
            {spec.source_name: spec.source_model} if spec.source_name
            else spec.source_model
        ),
        "source_binding": "declared" if spec.bound else "inferred",
        "hashed_columns": hashed,
        "expected_source_columns": list(spec.source_columns),
    }
    if spec.derived:
        meta["derived_columns"] = dict(spec.derived)
    return meta


# Contract data_type -> dbt/Postgres-safe seed column type (WP7 §7.3). JSON Schema base
# types only; "string" is refined by a `format` semantic (date / date-time) below.
# Unmapped types (unknown/object/array/null) are OMITTED — dbt seed inference, as before;
# absence of knowledge stays visible, never papered over with a guess.
_SEED_TYPE_BY_JSON_TYPE = {
    "string": "varchar",
    "integer": "bigint",
    "number": "numeric",
    "boolean": "boolean",
}


def _seed_type(contract_field: dict[str, Any]) -> str | None:
    """Map one contract field to a seed column type, or None to omit (never guess)."""
    constraints = contract_field.get("constraints") or {}
    data_type: Any = constraints.get("data_type", "unknown")
    if isinstance(data_type, list):
        # Unions take the non-null member; anything ambiguous is omitted.
        non_null = [t for t in data_type if t != "null"]
        if len(non_null) != 1:
            return None
        data_type = non_null[0]
    if data_type == "string":
        fmt = next(
            (
                s.get("value")
                for s in contract_field.get("semantics", [])
                if isinstance(s, dict) and s.get("kind") == "format"
            ),
            None,
        )
        if fmt == "date":
            return "date"
        if fmt == "date-time":
            return "timestamp"
    return _SEED_TYPE_BY_JSON_TYPE.get(str(data_type))


def _collect_seed_column_types(
    specs: dict[str, StagingSpec], contracts: list[dict[str, Any]]
) -> dict[str, dict[str, str]]:
    """Seed column types per staging source, from the drafted data contracts (WP7 §7.3).

    A staging spec picks up the contract whose ``name`` matches its ``source_model``
    (normalised) — on grounded runs the contracts are per source table, so the names
    line up; ungrounded entity contracts match nothing and change nothing. Column names
    are normalised to the UPPER_SNAKE seed headers; ``LOAD_DATETIME`` / ``RECORD_SOURCE``
    are always typed timestamp / varchar (every raw relation carries them)."""
    by_name: dict[str, dict[str, Any]] = {}
    for contract in contracts:
        name = contract.get("name")
        if isinstance(name, str):
            by_name.setdefault(normalize_identifier(name), contract)
    column_types: dict[str, dict[str, str]] = {}
    for spec in specs.values():
        matched = by_name.get(normalize_identifier(spec.source_model))
        if matched is None:
            continue  # no contract match -> no column_types (dbt inference, as today)
        columns: dict[str, str] = {}
        raw_fields = matched.get("schema", [])
        if not isinstance(raw_fields, list):
            raw_fields = []
        for contract_field in raw_fields:
            if not isinstance(contract_field, dict):
                continue
            label = contract_field.get("name")
            if not isinstance(label, str):
                continue
            seed_type = _seed_type(contract_field)
            if seed_type is not None:
                columns[_to_column(label)] = seed_type
        columns[LOAD_DATETIME_COLUMN] = "timestamp"
        columns[RECORD_SOURCE_COLUMN] = "varchar"
        column_types[spec.source_model] = columns
    return column_types


def _render_dbt_project(seed_column_types: dict[str, dict[str, str]]) -> str:
    return f"""# Generated by vault-agent — dbt project scaffolding for the generated Data Vault.
# Define a matching connection profile named '{PROJECT_NAME}' in profiles.yml
# (see README.md); then: dbt deps && dbt build.
name: '{PROJECT_NAME}'
version: '1.0.0'
config-version: 2

profile: '{PROJECT_NAME}'

model-paths: ["models"]
seed-paths: ["seeds"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
macro-paths: ["macros"]

target-path: "target"
clean-targets:
  - "target"
  - "dbt_packages"

models:
  {PROJECT_NAME}:
    staging:
      # Thin view layer (hash keys / hashdiffs); no need to persist it.
      +materialized: view
    raw_vault:
      # The generated models already carry config(materialized='incremental');
      # this is a belt-and-braces default.
      +materialized: incremental

seeds:
  {PROJECT_NAME}:
    # Keep seed column headers UNQUOTED so UPPER_SNAKE identifiers fold consistently
    # with the (also unquoted) identifiers AutomateDV emits (verified on Postgres —
    # see demo/bank_postgres in the vault-agent repo).
    +quote_columns: false
""" + _render_seed_column_types(seed_column_types)


def _render_seed_column_types(seed_column_types: dict[str, dict[str, str]]) -> str:
    """The per-seed ``+column_types`` blocks (WP7 §7.3); empty when no contract matched,
    keeping ungrounded/contract-less output byte-identical."""
    if not seed_column_types:
        return ""
    lines = [
        "    # Column types pinned from the drafted data contracts (never inferred);",
        "    # columns with an undetermined contract type are omitted and left to dbt's",
        "    # seed inference, so a gap stays visible instead of being guessed at.",
    ]
    for seed_name, columns in seed_column_types.items():
        lines.append(f"    {seed_name}:")
        lines.append("      +column_types:")
        for column, seed_type in columns.items():
            lines.append(f"        {column}: {seed_type}")
    return "\n".join(lines) + "\n"


def _render_packages() -> str:
    return f"""# Generated by vault-agent. AutomateDV (Datavault-UK) — the OSS dbt package whose
# hub/link/sat/eff_sat/stage macros the generated models call. Pinned to the version
# the generator's output is verified against; bump deliberately.
packages:
  - package: Datavault-UK/automate_dv
    version: {AUTOMATE_DV_VERSION}
"""


def _merge_source_tables(
    specs: Iterable[StagingSpec],
) -> list[tuple[str, list[str], bool]]:
    """Collapse staging specs that read the SAME raw relation into one source entry.

    Several staging models can legitimately bind to one physical table — e.g. a hub's
    staging plus a satellite whose ``source_table`` names the hub's own relation, or a
    hub and a standard satellite the modeller named off the same base. A dbt
    ``sources.yml`` (and the documented interface it renders) must list each table
    exactly ONCE: dbt raises a compilation error on two source tables with the same name.
    Returns ``(source_model, expected columns unioned in first-appearance order,
    all_bound)`` per distinct relation, in first-appearance order — so the output stays
    byte-identical when every spec already has a distinct ``source_model``."""
    merged: dict[str, list[str]] = {}
    bound: dict[str, bool] = {}
    order: list[str] = []
    for spec in specs:
        if spec.source_model not in merged:
            merged[spec.source_model] = []
            bound[spec.source_model] = True
            order.append(spec.source_model)
        cols = merged[spec.source_model]
        for col in spec.source_columns:
            if col not in cols:
                cols.append(col)
        bound[spec.source_model] = bound[spec.source_model] and spec.bound
    return [(name, merged[name], bound[name]) for name in order]


def _render_sources_yml(
    specs: dict[str, StagingSpec], blocks: list[SourceBlock]
) -> str:
    if blocks:
        # Grounded run with declared physical locations (WP7 §7.2): REAL source blocks —
        # the staging models listed under them reference their table via source().
        lines = [
            "# Generated by vault-agent — dbt sources for the declared raw inputs "
            "(ADR-0004).",
            "#",
            "# Grounded run: staging models whose declared source table carries a "
            "physical",
            "# location (schema/database) reference it through automate_dv.stage's "
            "source()",
            "# mapping form (`source_model: {<source name>: <table>}`), bound to the "
            "blocks",
            "# below. Relations in the trailing comment are still referenced by BARE "
            "name",
            "# (a seed, model, or table in the target schema).",
            "version: 2",
            "",
            "sources:",
        ]
        in_blocks = {spec.name for block in blocks for spec in block.specs}
        for block in blocks:
            lines.append(f"  - name: {block.name}")
            if block.database is not None:
                lines.append(f"    database: {block.database}")
            if block.schema_name is not None:
                lines.append(f"    schema: {block.schema_name}")
            lines.append("    tables:")
            for source_model, source_columns, _ in _merge_source_tables(block.specs):
                lines.append(f"      - name: {source_model}")
                cols = ", ".join(source_columns)
                lines.append(f"        # expected columns: {cols}")
        bare = [spec for spec in specs.values() if spec.name not in in_blocks]
        if bare:
            lines.append("")
            lines.append(
                "# Referenced by BARE relation name (no declared physical location):"
            )
            for spec in bare:
                note = "" if spec.bound else " — inferred binding, review"
                lines.append(f"#   - {spec.source_model} (feeds {spec.name}){note}")
        return "\n".join(lines) + "\n"

    lines = [
        "# Generated by vault-agent — the raw inputs the staging layer expects.",
        "#",
        "# The stg_* models reference their raw input by BARE relation name (a seed, model,",
        "# or table in the target schema named like `source_model` below). This file",
        "# DOCUMENTS that interface. To bind to an external schema instead, set database/",
        "# schema here and switch the staging model's source_model to a source() mapping",
        "# (automate_dv.stage accepts `source_model: {source_name: table_name}`).",
        "version: 2",
        "",
        "sources:",
        "  - name: raw",
        "    # database: <set me>",
        "    # schema: <set me>",
        "    tables:",
    ]
    for source_model, source_columns, all_bound in _merge_source_tables(specs.values()):
        lines.append(f"      - name: {source_model}")
        cols = ", ".join(source_columns)
        lines.append(f"        # expected columns: {cols}")
        if not all_bound:
            lines.append(
                "        # NOTE: inferred binding (no declared source table matched) — review"
            )
    return "\n".join(lines) + "\n"


def _render_readme(specs: dict[str, StagingSpec]) -> str:
    inputs = "\n".join(
        f"- `{spec.source_model}` → feeds `{spec.name}` "
        f"(expected columns: {', '.join(spec.source_columns)})"
        for spec in specs.values()
    )
    return f"""# Generated Data Vault project (vault-agent)

A runnable dbt project: `models/staging/` computes the hash keys / hashdiffs via
AutomateDV's `stage` macro, `models/raw_vault/` holds the generated hubs, links, and
satellites. Review `review-queue.md` and `contracts/` before agreeing the model.

## Provide the raw inputs

Each staging model reads one raw relation by name — provide it either as a dbt seed
(`seeds/<name>.csv`, headers exactly as listed) or as a table/view in the target schema:

{inputs}

Every raw relation must also carry `{LOAD_DATETIME_COLUMN}` and `{RECORD_SOURCE_COLUMN}`.

## Run it

1. Define a `{PROJECT_NAME}` profile in `profiles.yml` (any AutomateDV-supported warehouse).
2. `dbt deps`
3. `dbt seed` (if using seeds), then `dbt build`.
"""


def build_staging(
    model: DVModel,
    source_schemas: list[SourceTable],
    contracts: list[dict[str, Any]] | None = None,
    source_overrides: dict[str, str] | None = None,
) -> StagingResult:
    """The full staging pass: specs -> bindings -> rendered models + scaffolding.

    ``contracts`` (``state.artifacts.contracts``, drafted by the data-contract agent —
    which runs BEFORE the code generator in the graph) pins seed column types for
    staging sources whose contract matches by name (WP7 §7.3).

    ``source_overrides`` (WP9 §6) binds specs to the source tables a ratified/proposed
    business↔source mapping resolved them to (the source_mapper's re-bind); ``None`` /
    empty leaves the WP7 inference untouched, so unmapped runs stay byte-identical."""
    specs = collect_staging_specs(model)
    flags = bind_sources(specs, source_schemas, source_overrides)
    # Grounded runs only (ungrounded: no blocks, no source_name — byte-identical output).
    blocks = group_sources(specs, source_schemas)
    seed_column_types = _collect_seed_column_types(specs, contracts or [])
    models = {name: render_stage_model(spec) for name, spec in specs.items()}
    metadata = {name: _stage_metadata(spec) for name, spec in specs.items()}
    scaffolding = {
        "dbt_project.yml": _render_dbt_project(seed_column_types),
        "packages.yml": _render_packages(),
        "models/staging/sources.yml": _render_sources_yml(specs, blocks),
        "README.md": _render_readme(specs),
    }
    return StagingResult(
        models=models, metadata=metadata, scaffolding=scaffolding, flags=flags
    )
