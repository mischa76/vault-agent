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


def _render_nh_link(link: Link, hub_hashkeys: dict[str, str]) -> tuple[str, dict[str, Any]]:
    """Render a transactional (non-historized) link. Caller guarantees event_timestamp."""
    src_fk = [hub_hashkeys[hub_name] for hub_name in link.connected_hubs]
    payload = [_to_column(col) for col in link.payload]
    src_eff = _to_column(link.event_timestamp or "")
    meta: dict[str, Any] = {
        "source_model": _staging_model(link.name),
        "src_pk": _link_hashkey(link),
        "src_fk": src_fk,
        "src_payload": payload,
        "src_eff": src_eff,
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
                ("src_payload", _sql_list(payload)),
                ("src_eff", f'"{src_eff}"'),
                ("src_ldts", f'"{LOAD_DATETIME_COLUMN}"'),
                ("src_source", f'"{RECORD_SOURCE_COLUMN}"'),
            ]
        )
        + "\n{{ automate_dv.nh_link(src_pk=src_pk, src_fk=src_fk, src_payload=src_payload,\n"
        + "                       src_eff=src_eff, src_ldts=src_ldts, "
        + "src_source=src_source, source_model=source_model) }}\n"
    )
    return sql, meta


def _render_ma_sat(sat: Satellite, parent_hashkey: str) -> tuple[str, dict[str, Any]]:
    payload = [_to_column(attr) for attr in sat.attributes]
    cdk = [_to_column(key) for key in sat.child_dependent_key]
    src_hashdiff = _to_column(_base_name(sat.name)) + HASHDIFF_SUFFIX
    meta: dict[str, Any] = {
        "source_model": _staging_model(sat.parent),
        "src_pk": parent_hashkey,
        "src_cdk": cdk,
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
                ("src_cdk", _sql_list(cdk)),
                ("src_hashdiff", f'"{src_hashdiff}"'),
                ("src_payload", _sql_list(payload)),
                ("src_ldts", f'"{LOAD_DATETIME_COLUMN}"'),
                ("src_source", f'"{RECORD_SOURCE_COLUMN}"'),
            ]
        )
        + "\n{{ automate_dv.ma_sat(src_pk=src_pk, src_cdk=src_cdk, "
        + "src_hashdiff=src_hashdiff,\n"
        + "                      src_payload=src_payload, src_ldts=src_ldts, "
        + "src_source=src_source, source_model=source_model) }}\n"
    )
    return sql, meta


def _render_eff_sat(
    sat: Satellite, link_hashkey: str, driving_fks: list[str], secondary_fks: list[str]
) -> tuple[str, dict[str, Any]]:
    dates = [_to_column(attr) for attr in sat.attributes]
    start_date, end_date = dates[0], dates[1]
    # AutomateDV's src_dfk takes a bare key for a single driving hub, a list for several
    # — mirror how src_fk / src_cdk are rendered elsewhere.
    single_driver = len(driving_fks) == 1
    src_dfk: str | list[str] = driving_fks[0] if single_driver else driving_fks
    dfk_render = f'"{driving_fks[0]}"' if single_driver else _sql_list(driving_fks)
    meta: dict[str, Any] = {
        "source_model": _staging_model(sat.parent),
        "src_pk": link_hashkey,
        "src_dfk": src_dfk,
        "src_sfk": secondary_fks,
        "src_start_date": start_date,
        "src_end_date": end_date,
        "src_eff": start_date,
        "src_ldts": LOAD_DATETIME_COLUMN,
        "src_source": RECORD_SOURCE_COLUMN,
    }
    sql = (
        "{{ config(materialized='incremental') }}\n\n"
        + _set_block(
            [
                ("source_model", f'"{meta["source_model"]}"'),
                ("src_pk", f'"{link_hashkey}"'),
                ("src_dfk", dfk_render),
                ("src_sfk", _sql_list(secondary_fks)),
                ("src_start_date", f'"{start_date}"'),
                ("src_end_date", f'"{end_date}"'),
                ("src_eff", f'"{start_date}"'),
                ("src_ldts", f'"{LOAD_DATETIME_COLUMN}"'),
                ("src_source", f'"{RECORD_SOURCE_COLUMN}"'),
            ]
        )
        + "\n{{ automate_dv.eff_sat(src_pk=src_pk, src_dfk=src_dfk, src_sfk=src_sfk,\n"
        + "                       src_start_date=src_start_date, src_end_date=src_end_date,\n"
        + "                       src_eff=src_eff, src_ldts=src_ldts, "
        + "src_source=src_source, source_model=source_model) }}\n"
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
        # link name -> the hub hashkeys it connects, in declared order. Membership marks a
        # parent as a generated link (eff_sat must hang off one).
        link_fks: dict[str, list[str]] = {}
        # link name -> driving / secondary hub hashkeys, split per link.driving_key (the
        # declared end-dating side). Populated only when driving_key is set; eff_sat uses it.
        link_driving_fks: dict[str, list[str]] = {}
        link_secondary_fks: dict[str, list[str]] = {}

        dbt_models: dict[str, str] = {}
        metadata: dict[str, dict[str, Any]] = {"hubs": {}, "links": {}, "satellites": {}}

        for hub in model.hubs:
            sql, meta = _render_hub(hub)
            dbt_models[hub.name] = sql
            metadata["hubs"][hub.name] = meta

        for link in model.links:
            missing = [h for h in link.connected_hubs if h not in hub_hashkeys]
            if missing:
                state.errors.append(
                    f"code_generator: link {link.name!r} references unknown hubs "
                    f"{missing}; skipped"
                )
                continue
            if link.link_type == "transactional":
                if link.event_timestamp is None:
                    state.errors.append(
                        f"code_generator: transactional link {link.name!r} has no "
                        f"event_timestamp; cannot generate automate_dv.nh_link, flagged "
                        f"for human review"
                    )
                    continue
                sql, meta = _render_nh_link(link, hub_hashkeys)
            else:
                sql, meta = _render_link(link, hub_hashkeys)
            dbt_models[link.name] = sql
            metadata["links"][link.name] = meta
            parent_hashkeys[link.name] = _link_hashkey(link)
            link_fks[link.name] = [hub_hashkeys[h] for h in link.connected_hubs]
            if link.driving_key:
                # Driving keys in their declared order; secondaries = the remaining
                # connected hubs in theirs. Order-independent of connected_hubs ordering.
                link_driving_fks[link.name] = [
                    hub_hashkeys[h] for h in link.driving_key if h in hub_hashkeys
                ]
                link_secondary_fks[link.name] = [
                    hub_hashkeys[h]
                    for h in link.connected_hubs
                    if h not in link.driving_key
                ]

        for sat in model.satellites:
            rendered = self._render_satellite(
                sat, parent_hashkeys, link_fks, link_driving_fks, link_secondary_fks, state
            )
            if rendered is None:
                continue
            sql, meta = rendered
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

    @staticmethod
    def _render_satellite(
        sat: Satellite,
        parent_hashkeys: dict[str, str],
        link_fks: dict[str, list[str]],
        link_driving_fks: dict[str, list[str]],
        link_secondary_fks: dict[str, list[str]],
        state: VaultAgentState,
    ) -> tuple[str, dict[str, Any]] | None:
        """Dispatch a satellite to the template for its type; flag what can't be generated."""
        if sat.parent not in parent_hashkeys:
            state.errors.append(
                f"code_generator: satellite {sat.name!r} has parent {sat.parent!r} "
                f"with no generated hub/link; skipped"
            )
            return None

        if sat.sat_type == "standard":
            return _render_sat(sat, parent_hashkeys[sat.parent])

        if sat.sat_type == "multi_active":
            if not sat.child_dependent_key:
                state.errors.append(
                    f"code_generator: multi-active satellite {sat.name!r} has no "
                    f"child_dependent_key; cannot generate automate_dv.ma_sat, flagged "
                    f"for human review"
                )
                return None
            return _render_ma_sat(sat, parent_hashkeys[sat.parent])

        # effectivity
        if sat.parent not in link_fks:
            state.errors.append(
                f"code_generator: effectivity satellite {sat.name!r} must hang off a "
                f"generated link; parent {sat.parent!r} is not one, flagged for human review"
            )
            return None
        if len(sat.attributes) < 2:
            state.errors.append(
                f"code_generator: effectivity satellite {sat.name!r} needs start and end "
                f"date attributes; flagged for human review"
            )
            return None
        # The eff_sat end-dates by the link's declared driving key, never by whichever hub
        # happens to come first. The validator gate (E_EFFSAT_NO_DRIVING_KEY) should already
        # block an empty driving key, but the generator is an independent stage: flag and
        # skip rather than silently fall back to the first hub.
        driving_fks = link_driving_fks.get(sat.parent, [])
        if not driving_fks:
            state.errors.append(
                f"code_generator: effectivity satellite {sat.name!r} on link "
                f"{sat.parent!r} has no driving_key; cannot end-date by driving key, "
                f"flagged for human review"
            )
            return None
        return _render_eff_sat(
            sat,
            parent_hashkeys[sat.parent],
            driving_fks,
            link_secondary_fks.get(sat.parent, []),
        )
