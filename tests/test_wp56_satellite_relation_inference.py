"""WP56 — a relation-less satellite whose attributes name exactly one declared table reads that
table (spec §3). Committed before the change, failing. The fixture is the ninth chain's step-1
attempt-1 records on the person step's declared tables."""
from __future__ import annotations

from typing import Any

from tests.test_agents.test_dv2_modeler import StubExtractor, _state
from vault_agent import llm
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.orchestrator import flag_role
from vault_agent.rules.dv2_rules import infer_satellite_relation
from vault_agent.state import FlagKind, PipelineFlag, Satellite, SourceTable, VaultAgentState


def _schema() -> list[SourceTable]:
    fk = [{"columns": ["BusinessEntityID"], "references_table": "Person",
           "references_columns": ["BusinessEntityID"]}]
    return [
        SourceTable(table="Person", columns=["BusinessEntityID", "PersonType", "FirstName",
                                             "LastName", "rowguid", "ModifiedDate"]),
        SourceTable(table="EmailAddress", foreign_keys=fk,
                    columns=["BusinessEntityID", "EmailAddressID", "EmailAddress", "rowguid",
                             "ModifiedDate"]),
        SourceTable(table="Password", foreign_keys=fk,
                    columns=["BusinessEntityID", "PasswordHash", "PasswordSalt", "rowguid",
                             "ModifiedDate"]),
    ]


def _sat(name: str, parent: str, attributes: list[str], **extra: Any) -> dict[str, Any]:
    return {"name": name, "parent": parent, "attributes": attributes, "description": name,
            **extra}


def _payload(satellites: list[dict[str, Any]], links: list[dict[str, Any]] | None = None
             ) -> dict[str, Any]:
    return {
        "hubs": [{"name": "hub_person", "business_key": "BusinessEntityID",
                  "source_entity": "Person", "description": "A person."}],
        "links": links or [],
        "satellites": satellites,
    }


async def _run(payload: dict[str, Any]) -> tuple[VaultAgentState, list[llm.TraceEvent]]:
    state = _state()
    state.source_schemas = _schema()
    events: list[llm.TraceEvent] = []
    llm.set_trace_recorder(events.append)
    try:
        state = await Dv2ModelerAgent(extractor=StubExtractor(payload)).run(state)
    finally:
        llm.set_trace_recorder(None)
    return state, events


def test_the_relation_is_the_one_table_that_carries_every_attribute() -> None:
    def sat(attrs: list[str], cdk: str | None = None) -> Satellite:
        return Satellite(name="sat_x", parent="hub_person", attributes=attrs, description="x",
                         child_dependent_key=[cdk] if cdk else [])
    assert infer_satellite_relation(sat(["EmailAddress", "ModifiedDate"]), _schema()) == (
        "EmailAddress"
    )
    assert infer_satellite_relation(sat(["ModifiedDate"]), _schema()) is None  # every table
    assert infer_satellite_relation(sat(["EmailAddress", "PasswordHash"]), _schema()) is None
    assert infer_satellite_relation(sat([]), _schema()) is None
    assert infer_satellite_relation(sat(["ModifiedDate"], cdk="EmailAddressID"), _schema()) == (
        "EmailAddress"
    )


async def test_a_collapsed_links_satellite_moves_with_its_inferred_relation() -> None:
    links = [
        {"name": "link_person_email_address", "connected_hubs": ["hub_person"],
         "description": "An email address of a person."},
        {"name": "link_person_credential", "connected_hubs": ["hub_person"],
         "description": "The sign-in credential belonging to a person."},
    ]
    sats = [
        _sat("sat_email_address_detail", "link_person_email_address",
             ["EmailAddress", "ModifiedDate"]),
        _sat("sat_credential_status", "link_person_credential", ["ModifiedDate"]),
    ]
    state, events = await _run(_payload(sats, links))
    [sat] = state.dv_model.satellites
    assert sat.name == "sat_email_address_detail" and sat.parent == "hub_person"
    assert sat.source_table == "EmailAddress"
    watched = (FlagKind.LINK_COLLAPSED, FlagKind.RELATION_INFERRED, FlagKind.DROPPED_RECORD)
    kinds = {k: [f.asset for f in state.flags if f.kind == k] for k in watched}
    assert kinds[FlagKind.LINK_COLLAPSED] == ["sat_email_address_detail"]
    assert kinds[FlagKind.RELATION_INFERRED] == ["sat_email_address_detail"]
    assert kinds[FlagKind.DROPPED_RECORD] == ["sat_credential_status"]
    [event] = [e for e in events
               if e.kind == "backstop" and e.backstop_id == "satellite_relation_inferred"]
    assert event.detail == {"satellite": "sat_email_address_detail", "table": "EmailAddress",
                            "path": "collapse"}


async def test_on_a_hub_only_a_foreign_relation_is_inferred_and_a_link_is_untouched() -> None:
    links = [{"name": "link_person_person", "connected_hubs": ["hub_person", "hub_person"],
              "description": "self"}]
    sats = [
        _sat("sat_person_email", "hub_person", ["EmailAddress", "ModifiedDate"]),
        _sat("sat_person_names", "hub_person", ["FirstName", "LastName"]),
        _sat("sat_link_email", "link_person_person", ["EmailAddress"]),
    ]
    state, _ = await _run(_payload(sats, links))
    by = {s.name: s for s in state.dv_model.satellites}
    assert by["sat_person_email"].source_table == "EmailAddress"
    assert by["sat_person_names"].source_table is None  # the hub's own table stays implicit
    assert by["sat_link_email"].source_table is None
    assert [f.asset for f in state.flags if f.kind == FlagKind.RELATION_INFERRED] == [
        "sat_person_email"
    ]


def test_relation_inferred_is_a_disclosure() -> None:
    flag = PipelineFlag(agent="dv2_modeler", message="m", kind=FlagKind.RELATION_INFERRED,
                        asset="s")
    assert flag_role(flag) == "disclosure"
