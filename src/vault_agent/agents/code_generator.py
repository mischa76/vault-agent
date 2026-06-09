"""Code Generator agent.

Deterministically renders the logical Data Vault model in ``VaultAgentState.dv_model`` into
AutomateDV-compatible dbt models (plus a machine-readable metadata summary) in
``VaultAgentState.artifacts``. No LLM is involved: the typed Hub / Link / Satellite
constructs map 1:1 onto AutomateDV macro arguments (ADR-0003), so generation is
reproducible and runs in CI without an API key.

The generator is a dispatcher — each construct's type selects the matching AutomateDV
macro template. Construct types we do not yet template (transactional links,
effectivity / multi-active satellites) are flagged for human review rather than emitted
as wrong SQL, so coverage grows by adding (type on the model + a template), never by
hacking heuristics into the generator.
"""
import re
from typing import Any

from vault_agent.agents.base import BaseAgent
from vault_agent.rules.dv2_rules import (
    HASHDIFF_SUFFIX,
    HASHKEY_SUFFIX,
    LOAD_DATETIME_COLUMN,
    RECORD_SOURCE_COLUMN,
    STAGING_PREFIX,
)
from vault_agent.state import Hub, Link, Satellite, VaultAgentState

_CONSTRUCT_PREFIXES = ("hub_", "link_", "sat_")

# Macro a non-standard construct type would need once templated (used in flag messages).
_LINK_MACRO = {"transactional": "t_link"}
_SAT_MACRO = {"effectivity": "eff_sat", "multi_active": "ma_sat"}


def _to_column(label: str) -> str:
    """Normalise a business label into a SQL identifier (UPPER_SNAKE)."""
    return re.sub(r"[^0-9a-zA-Z]+", "_", label).strip("_").upper()


def _base_name(name: str) -> str:
    """Strip the hub_/link_/sat_ prefix from a construct name."""
    for prefix in _CONSTRUCT_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def _staging_model(name: str) -> str:
    return STAGING_PREFIX + _base_name(name)


def _sql_list(items: list[str]) -> str:
    return "[" + ", ".join(f'"{item}"' for item in items) + "]"


def _set_block(assignments: list[tuple[str, str]]) -> str:
    """Render the dbt/Jinja ``{%- set ... -%}`` header lines."""
    return "".join(f'{{%- set {var} = {value} -%}}\n' for var, value in assignments)


def _hub_hashkey(hub: Hub) -> str:
    return _to_column(hub.source_entity) + HASHKEY_SUFFIX


def _link_hashkey(link: Link) -> str:
    return _to_column(link.name) + HASHKEY_SUFFIX


def _render_hub(hub: Hub) -> tuple[str, dict[str, Any]]:
    meta: dict[str, Any] = {
        "source_model": _staging_model(hub.name),
        "src_pk": _hub_hashkey(hub),
        "src_nk": _to_column(hub.business_key),
        "src_ldts": LOAD_DATETIME_COLUMN,
        "src_source": RECORD_SOURCE_COLUMN,
    }
    sql = (
        "{{ config(materialized='incremental') }}\n\n"
        + _set_block(
            [
                ("source_model", f'"{meta["source_model"]}"'),
                ("src_pk", f'"{meta["src_pk"]}"'),
                ("src_nk", f'"{meta["src_nk"]}"'),
                ("src_ldts", f'"{LOAD_DATETIME_COLUMN}"'),
                ("src_source", f'"{RECORD_SOURCE_COLUMN}"'),
            ]
        )
        + "\n{{ automate_dv.hub(src_pk=src_pk, src_nk=src_nk, src_ldts=src_ldts,\n"
        + "                   src_source=src_source, source_model=source_model) }}\n"
    )
    return sql, meta


def _render_link(link: Link, hub_hashkeys: dict[str, str]) -> tuple[str, dict[str, Any]]:
    src_fk = [hub_hashkeys[hub_name] for hub_name in link.connected_hubs]
    meta: dict[str, Any] = {
        "source_model": _staging_model(link.name),
        "src_pk": _link_hashkey(link),
        "src_fk": src_fk,
        "src_ldts": LOAD_DATETIME_COLUMN,
        "src_source": RECORD_SOURCE_COLUMN,
    }
    sql = (
        "{{ config(materialized='incremental') }}\n\n"
        + _set_block(
            [
                ("source_model", f'"{meta["source_model"]}"'),
                ("src_pk", f'"{meta["src_pk"]}"'),
                ("src_fk", _sql_list(src_fk)),
                ("src_ldts", f'"{LOAD_DATETIME_COLUMN}"'),
                ("src_source", f'"{RECORD_SOURCE_COLUMN}"'),
            ]
        )
        + "\n{{ automate_dv.link(src_pk=src_pk, src_fk=src_fk, src_ldts=src_ldts,\n"
        + "                    src_source=src_source, source_model=source_model) }}\n"
    )
    return sql, meta


def _render_sat(sat: Satellite, parent_hashkey: str) -> tuple[str, dict[str, Any]]:
    payload = [_to_column(attr) for attr in sat.attributes]
    src_hashdiff = _to_column(_base_name(sat.name)) + HASHDIFF_SUFFIX
    meta: dict[str, Any] = {
        "source_model": _staging_model(sat.parent),
        "src_pk": parent_hashkey,
        "src_hashdiff": src_hashdiff,
        "src_payload": payload,
        "src_ldts": LOAD_DATETIME_COLUMN,
        "src_source": RECORD_SOURCE_COLUMN,
    }
    sql = (
        "{{ config(materialized='incremental') }}\n\n"
        + _set_block(
            [
                ("source_model", f'"{meta["source_model"]}"'),
                ("src_pk", f'"{parent_hashkey}"'),
                ("src_hashdiff", f'"{src_hashdiff}"'),
                ("src_payload", _sql_list(payload)),
                ("src_ldts", f'"{LOAD_DATETIME_COLUMN}"'),
                ("src_source", f'"{RECORD_SOURCE_COLUMN}"'),
            ]
        )
        + "\n{{ automate_dv.sat(src_pk=src_pk, src_hashdiff=src_hashdiff, "
        + "src_payload=src_payload,\n"
        + "                   src_ldts=src_ldts, src_source=src_source, "
        + "source_model=source_model) }}\n"
    )
    return sql, meta


class CodeGeneratorAgent(BaseAgent):
    """Renders the Data Vault model into AutomateDV-compatible dbt models."""

    prompt_path = "code_generator.md"  # type: ignore[assignment]

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        model = state.dv_model
        if not model.hubs:
            state.errors.append(
                "code_generator: no hubs in dv_model; run the DV2.0 modeler first"
            )
            return state

        hub_hashkeys = {hub.name: _hub_hashkey(hub) for hub in model.hubs}
        parent_hashkeys: dict[str, str] = dict(hub_hashkeys)

        dbt_models: dict[str, str] = {}
        metadata: dict[str, dict[str, Any]] = {"hubs": {}, "links": {}, "satellites": {}}

        for hub in model.hubs:
            sql, meta = _render_hub(hub)
            dbt_models[hub.name] = sql
            metadata["hubs"][hub.name] = meta

        for link in model.links:
            if link.link_type != "standard":
                macro = _LINK_MACRO.get(link.link_type, "?")
                state.errors.append(
                    f"code_generator: link {link.name!r} is {link.link_type!r}, not yet "
                    f"templated (needs automate_dv.{macro}); flagged for human review"
                )
                continue
            missing = [h for h in link.connected_hubs if h not in hub_hashkeys]
            if missing:
                state.errors.append(
                    f"code_generator: link {link.name!r} references unknown hubs "
                    f"{missing}; skipped"
                )
                continue
            sql, meta = _render_link(link, hub_hashkeys)
            dbt_models[link.name] = sql
            metadata["links"][link.name] = meta
            parent_hashkeys[link.name] = _link_hashkey(link)

        for sat in model.satellites:
            if sat.sat_type != "standard":
                macro = _SAT_MACRO.get(sat.sat_type, "?")
                state.errors.append(
                    f"code_generator: satellite {sat.name!r} is {sat.sat_type!r}, not yet "
                    f"templated (needs automate_dv.{macro}); flagged for human review"
                )
                continue
            if sat.parent not in parent_hashkeys:
                state.errors.append(
                    f"code_generator: satellite {sat.name!r} has parent {sat.parent!r} "
                    f"with no generated hub/link; skipped"
                )
                continue
            sql, meta = _render_sat(sat, parent_hashkeys[sat.parent])
            dbt_models[sat.name] = sql
            metadata["satellites"][sat.name] = meta

        state.artifacts.dbt_models = dbt_models
        state.artifacts.automatedv_yaml = metadata
        state.decisions.append(
            {
                "agent": "code_generator",
                "models_generated": len(dbt_models),
                "hubs": len(metadata["hubs"]),
                "links": len(metadata["links"]),
                "satellites": len(metadata["satellites"]),
            }
        )
        return state
