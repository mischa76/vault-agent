"""Unit tests for the DV2.0 Modeler agent.

The LLM call is stubbed via the ``DVModelExtractor`` protocol so these tests run in CI
without an Anthropic API key (``asyncio_mode = auto`` runs the async tests directly).
"""
from typing import Any

from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.rules.dv2_rules import DV_MODELING_RULES
from vault_agent.state import (
    BusinessKeyCandidate,
    ParsedRequirement,
    SourceTable,
    VaultAgentState,
)


class StubExtractor:
    """Returns a canned payload and records how it was called."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    async def model(self, *, system_prompt: str, payload_json: str) -> dict[str, Any]:
        self.calls.append((system_prompt, payload_json))
        return self.payload


def _state() -> VaultAgentState:
    return VaultAgentState(
        requirements=[
            ParsedRequirement(id="REQ-001", text="A customer can open accounts.",
                              category="functional", actor="customer", action="open",
                              obj="account"),
            ParsedRequirement(id="REQ-009", text="A customer has a name.",
                              category="business-rule"),
        ],
        business_keys=[
            BusinessKeyCandidate(entity="customer", field="national customer ID",
                                 score=0.95, rationale="REQ-007"),
            BusinessKeyCandidate(entity="account", field="account number",
                                 score=0.95, rationale="REQ-004"),
        ],
    )


def _valid_payload() -> dict[str, Any]:
    return {
        "hubs": [
            {"name": "hub_customer", "business_key": "national customer ID",
             "source_entity": "customer", "description": "The customer.",
             "requirement_ids": ["REQ-007"]},
            {"name": "hub_account", "business_key": "account number",
             "source_entity": "account", "description": "The account.",
             "requirement_ids": ["REQ-004"]},
        ],
        "links": [
            {"name": "link_account_customer", "connected_hubs": ["hub_account", "hub_customer"],
             "description": "Account ownership.", "requirement_ids": ["REQ-001"]},
        ],
        "satellites": [
            {"name": "sat_customer_details", "parent": "hub_customer",
             "attributes": ["name", "date of birth"], "description": "Customer attributes.",
             "requirement_ids": ["REQ-009"]},
        ],
    }


async def test_builds_model_from_requirements_and_keys() -> None:
    stub = StubExtractor(_valid_payload())
    agent = Dv2ModelerAgent(extractor=stub)

    result = await agent.run(_state())

    assert [h.name for h in result.dv_model.hubs] == ["hub_customer", "hub_account"]
    assert [lk.name for lk in result.dv_model.links] == ["link_account_customer"]
    assert [s.name for s in result.dv_model.satellites] == ["sat_customer_details"]
    assert result.dv_model.hubs[0].business_key == "national customer ID"
    assert not result.errors

    # Modelling rules injected; both input arrays handed to the LLM.
    system_prompt, payload_json = stub.calls[0]
    assert DV_MODELING_RULES[0] in system_prompt
    assert "national customer ID" in payload_json
    assert "REQ-001" in payload_json

    # Decision recorded. The modeler does not write ADRs — the ADR Author is the sole
    # writer (L-4), so no draft fragment accumulates here.
    assert result.decisions[-1] == {
        "agent": "dv2_modeler", "hubs": 2, "links": 1, "satellites": 1,
    }
    assert result.adrs == []
    assert result.modeling_attempts == 1


async def test_dangling_link_is_dropped() -> None:
    payload = _valid_payload()
    payload["links"].append(
        {"name": "link_account_ghost", "connected_hubs": ["hub_account", "hub_ghost"],
         "description": "dangling", "requirement_ids": []}
    )
    stub = StubExtractor(payload)
    result = await Dv2ModelerAgent(extractor=stub).run(_state())

    assert [lk.name for lk in result.dv_model.links] == ["link_account_customer"]
    assert any("dropped link 'link_account_ghost'" in e for e in result.errors)


async def test_link_with_single_hub_is_dropped() -> None:
    payload = _valid_payload()
    payload["links"].append(
        {"name": "link_lonely", "connected_hubs": ["hub_customer"],
         "description": "only one hub", "requirement_ids": []}
    )
    stub = StubExtractor(payload)
    result = await Dv2ModelerAgent(extractor=stub).run(_state())

    assert "link_lonely" not in [lk.name for lk in result.dv_model.links]
    assert any("link_lonely" in e for e in result.errors)


async def test_dangling_satellite_is_dropped() -> None:
    payload = _valid_payload()
    payload["satellites"].append(
        {"name": "sat_orphan", "parent": "hub_missing", "attributes": ["x"],
         "description": "orphan", "requirement_ids": []}
    )
    stub = StubExtractor(payload)
    result = await Dv2ModelerAgent(extractor=stub).run(_state())

    assert [s.name for s in result.dv_model.satellites] == ["sat_customer_details"]
    assert any("dropped satellite 'sat_orphan'" in e for e in result.errors)


async def test_satellite_on_link_parent_is_kept() -> None:
    payload = _valid_payload()
    payload["satellites"].append(
        {"name": "sat_ownership_effectivity", "parent": "link_account_customer",
         "attributes": ["valid_from"], "description": "effectivity", "requirement_ids": []}
    )
    stub = StubExtractor(payload)
    result = await Dv2ModelerAgent(extractor=stub).run(_state())

    assert "sat_ownership_effectivity" in [s.name for s in result.dv_model.satellites]
    assert not result.errors


async def test_invalid_hub_is_skipped_and_logged() -> None:
    payload = _valid_payload()
    payload["hubs"].append({"name": "hub_broken"})  # missing required fields
    stub = StubExtractor(payload)
    result = await Dv2ModelerAgent(extractor=stub).run(_state())

    assert "hub_broken" not in [h.name for h in result.dv_model.hubs]
    assert any("dropped invalid hub" in e for e in result.errors)


async def test_no_business_keys_short_circuits_without_calling_llm() -> None:
    stub = StubExtractor(_valid_payload())
    result = await Dv2ModelerAgent(extractor=stub).run(VaultAgentState())

    assert result.dv_model.hubs == []
    assert any("no business keys" in e for e in result.errors)
    assert stub.calls == []


async def test_no_source_schema_keeps_modeler_prompt_ungrounded() -> None:
    # Regression guard: no declared schema -> no schema section in the modeler prompt.
    stub = StubExtractor(_valid_payload())
    agent = Dv2ModelerAgent(extractor=stub)

    await agent.run(_state())

    system_prompt, _ = stub.calls[0]
    assert "Known source columns" not in system_prompt


async def test_source_schema_is_injected_into_modeler_prompt() -> None:
    # Phase 2 grounding (ADR-0004): declared columns are rendered into the modeler prompt.
    stub = StubExtractor(_valid_payload())
    agent = Dv2ModelerAgent(extractor=stub)
    state = _state()
    state.source_schemas = [
        SourceTable(table="customer", columns=["national_customer_id", "date_of_birth"]),
    ]

    await agent.run(state)

    system_prompt, _ = stub.calls[0]
    assert "Known source columns" in system_prompt
    assert "date_of_birth" in system_prompt
