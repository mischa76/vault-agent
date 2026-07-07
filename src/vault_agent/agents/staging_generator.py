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
from dataclasses import dataclass, field

from vault_agent.rules.dv2_rules import (
    AUTOMATE_DV_VERSION,
    EFFECTIVITY_APPLIED_COLUMN,
    HASHDIFF_SUFFIX,
    LOAD_DATETIME_COLUMN,
    RAW_SOURCE_PREFIX,
    RECORD_SOURCE_COLUMN,
    STAGING_PREFIX,
    normalize_identifier,
)
from vault_agent.state import DVModel, FlagKind, PipelineFlag, SourceTable

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
    return STAGING_PREFIX + _base_name(construct_name)


def collect_staging_specs(model: DVModel) -> dict[str, StagingSpec]:
    """Group the raw-vault constructs by the staging model that feeds them.

    Mirrors the raw-vault generator's guards (unknown hubs/parents are skipped there and
    therefore need no staging here); insertion order is deterministic: hubs, links, then
    the satellites' additions to their parents' staging models."""
    from vault_agent.agents.code_generator import _hub_hashkey, _link_hashkey

    specs: dict[str, StagingSpec] = {}
    hub_by_name = {hub.name: hub for hub in model.hubs}

    def spec_for(construct_name: str) -> StagingSpec:
        name = _staging_name(construct_name)
        if name not in specs:
            specs[name] = StagingSpec(name=name, base=_base_name(construct_name))
        return specs[name]

    for hub in model.hubs:
        spec = spec_for(hub.name)
        bk_col = _to_column(hub.business_key)
        spec.add_hashed(_hub_hashkey(hub), bk_col)
        spec.add_source_column(bk_col)

    generated_links = []
    for link in model.links:
        if any(h not in hub_by_name for h in link.connected_hubs):
            continue  # the raw-vault generator skips (and flags) this link
        if link.link_type == "transactional" and link.event_timestamp is None:
            continue  # not generated as nh_link either
        generated_links.append(link)
        spec = spec_for(link.name)
        bk_cols = []
        for hub_name in link.connected_hubs:
            hub = hub_by_name[hub_name]
            bk_col = _to_column(hub.business_key)
            bk_cols.append(bk_col)
            spec.add_hashed(_hub_hashkey(hub), bk_col)
            spec.add_source_column(bk_col)
        spec.add_hashed(_link_hashkey(link), bk_cols)
        if link.link_type == "transactional":
            for col in link.payload:
                spec.add_source_column(_to_column(col))
            if link.event_timestamp:
                spec.add_source_column(_to_column(link.event_timestamp))

    link_names = {link.name for link in generated_links}
    for sat in model.satellites:
        if sat.parent not in hub_by_name and sat.parent not in link_names:
            continue  # dangling parent — skipped/flagged by the raw-vault generator
        spec = spec_for(sat.parent)
        attr_cols = [_to_column(attr) for attr in sat.attributes]
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
    specs: dict[str, StagingSpec], source_schemas: list[SourceTable]
) -> list[PipelineFlag]:
    """Bind each staging model to its raw relation; flag every *inferred* binding.

    A declared source table matches by normalised name against the construct base or its
    ``raw_<base>`` form; the table name is then used verbatim (source dialect, ADR-0004).
    Without a match the binding is inferred as ``raw_<base>`` and flagged for review."""
    flags: list[PipelineFlag] = []
    for spec in specs.values():
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
        f"source_model: '{spec.source_model}'",
    ]
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
        "source_model": spec.source_model,
        "source_binding": "declared" if spec.bound else "inferred",
        "hashed_columns": hashed,
        "expected_source_columns": list(spec.source_columns),
    }
    if spec.derived:
        meta["derived_columns"] = dict(spec.derived)
    return meta


def _render_dbt_project() -> str:
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
"""


def _render_packages() -> str:
    return f"""# Generated by vault-agent. AutomateDV (Datavault-UK) — the OSS dbt package whose
# hub/link/sat/eff_sat/stage macros the generated models call. Pinned to the version
# the generator's output is verified against; bump deliberately.
packages:
  - package: Datavault-UK/automate_dv
    version: {AUTOMATE_DV_VERSION}
"""


def _render_sources_yml(specs: dict[str, StagingSpec]) -> str:
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
    for spec in specs.values():
        lines.append(f"      - name: {spec.source_model}")
        cols = ", ".join(spec.source_columns)
        lines.append(f"        # expected columns: {cols}")
        if not spec.bound:
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


def build_staging(model: DVModel, source_schemas: list[SourceTable]) -> StagingResult:
    """The full staging pass: specs -> bindings -> rendered models + scaffolding."""
    specs = collect_staging_specs(model)
    flags = bind_sources(specs, source_schemas)
    models = {name: render_stage_model(spec) for name, spec in specs.items()}
    metadata = {name: _stage_metadata(spec) for name, spec in specs.items()}
    scaffolding = {
        "dbt_project.yml": _render_dbt_project(),
        "packages.yml": _render_packages(),
        "models/staging/sources.yml": _render_sources_yml(specs),
        "README.md": _render_readme(specs),
    }
    return StagingResult(
        models=models, metadata=metadata, scaffolding=scaffolding, flags=flags
    )
