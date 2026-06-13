"""Unit tests for the ADR Author agent (deterministic, no API key needed)."""
from vault_agent.agents.adr_author import AdrAuthorAgent
from vault_agent.state import (
    Artifacts,
    BusinessKeyCandidate,
    DVModel,
    Hub,
    Link,
    ParsedRequirement,
    Satellite,
    VaultAgentState,
)


def _state() -> VaultAgentState:
    return VaultAgentState(
        input_documents=["examples/inputs/bank_account_requirements.md"],
        requirements=[ParsedRequirement(id="REQ-007", text="…", category="business-rule")],
        business_keys=[BusinessKeyCandidate(entity="customer", field="national customer ID",
                                            score=0.95, rationale="REQ-007")],
        dv_model=DVModel(
            hubs=[Hub(name="hub_customer", business_key="national customer ID",
                      source_entity="customer", description="The customer.",
                      requirement_ids=["REQ-007"])],
            links=[Link(name="link_account_customer",
                        connected_hubs=["hub_account", "hub_customer"],
                        description="Account ownership.", requirement_ids=["REQ-001"])],
            satellites=[Satellite(name="sat_customer_details", parent="hub_customer",
                                  attributes=["customer name", "date of birth"],
                                  description="Customer attributes.",
                                  requirement_ids=["REQ-009", "REQ-010"])],
        ),
        artifacts=Artifacts(dbt_models={"hub_customer": "...", "sat_customer_details": "..."}),
    )


async def test_renders_finalized_adr() -> None:
    result = await AdrAuthorAgent(today="2026-06-10", start_number=4).run(_state())

    assert len(result.adrs) == 1
    adr = result.adrs[0]
    assert adr.startswith("# ADR-0004: Data Vault model derived from requirements")
    assert "**Status:** Proposed" in adr
    assert "**Date:** 2026-06-10" in adr
    assert "**hub_customer** — business key `national customer ID`" in adr
    assert "_(requirements: REQ-009, REQ-010)_" in adr  # satellite traceability
    assert "payload: customer name, date of birth" in adr
    assert "examples/inputs/bank_account_requirements.md" in adr  # references
    assert "Generated dbt models: 2" in adr
    assert result.decisions[-1] == {
        "agent": "adr_author", "adr_number": 4, "adrs_written": 1,
    }


async def test_finalized_adr_overwrites_any_preexisting_adrs() -> None:
    # The ADR Author is the sole writer (L-4); it overwrites defensively, so even if
    # anything had pre-populated state.adrs the result is a single finalized ADR.
    state = _state()
    state.adrs = ["## stray pre-existing entry", "## another"]
    result = await AdrAuthorAgent(today="2026-06-10").run(state)

    assert len(result.adrs) == 1
    assert result.adrs[0].startswith("# ADR-0004")


async def test_special_constructs_are_flagged_as_caveat() -> None:
    state = _state()
    state.dv_model.satellites.append(
        Satellite(name="sat_customer_addresses", parent="hub_customer",
                  attributes=["address"], description="multi-active",
                  sat_type="multi_active")
    )
    result = await AdrAuthorAgent(today="2026-06-10").run(state)

    adr = result.adrs[0]
    assert "Caveat:" in adr
    assert "sat_customer_addresses" in adr
    assert "specialised Data Vault types" in adr


async def test_optional_rationale_fields_surface_in_adr() -> None:
    state = _state()
    state.dv_model.links[0].unit_of_work = "one account-ownership event per (account, customer)"
    state.dv_model.satellites[0].split_rationale = "split from PII by rate of change"
    result = await AdrAuthorAgent(today="2026-06-10").run(state)

    adr = result.adrs[0]
    assert "Unit of work: one account-ownership event per (account, customer)." in adr
    assert "Split rationale: split from PII by rate of change." in adr


async def test_no_model_reports_error_and_writes_no_adr() -> None:
    result = await AdrAuthorAgent(today="2026-06-10").run(VaultAgentState())

    assert result.adrs == []
    assert any("no model to document" in e for e in result.errors)
