"""Unit tests for the ADR Author agent (deterministic, no API key needed)."""
from vault_agent.agents.adr_author import AdrAuthorAgent
from vault_agent.state import (
    Artifacts,
    BusinessKeyCandidate,
    DVModel,
    FlagKind,
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
    assert result.decisions[-1] == {
        "agent": "adr_author", "adr_number": 4, "adrs_written": 1,
    }


async def test_number_defaults_to_one_within_the_output() -> None:
    # The generated ADR is a per-run output artifact: always ADR-0001 within its output
    # directory, never derived from the repo's docs/architecture/adrs sequence.
    result = await AdrAuthorAgent(today="2026-06-10").run(_state())

    assert result.adrs[0].startswith("# ADR-0001: Data Vault model derived from requirements")
    assert result.decisions[-1]["adr_number"] == 1


async def test_same_state_yields_byte_identical_adr() -> None:
    # Idempotency guarantee: same model in, byte-identical ADR out — consistent with the
    # code generator, and safe for re-runs into the same output directory.
    first = await AdrAuthorAgent(today="2026-06-10").run(_state())
    second = await AdrAuthorAgent(today="2026-06-10").run(_state())

    assert first.adrs == second.adrs


async def test_finalized_adr_overwrites_any_preexisting_adrs() -> None:
    # The ADR Author is the sole writer (L-4); it overwrites defensively, so even if
    # anything had pre-populated state.adrs the result is a single finalized ADR.
    state = _state()
    state.adrs = ["## stray pre-existing entry", "## another"]
    result = await AdrAuthorAgent(today="2026-06-10", start_number=7).run(state)

    assert len(result.adrs) == 1
    assert result.adrs[0].startswith("# ADR-0007")


async def test_generated_special_constructs_get_no_caveat() -> None:
    # A non-standard type that the generator handled (no GENERATION_GAP flag) works —
    # the ADR must not claim otherwise.
    state = _state()
    state.dv_model.links[0].driving_key = ["hub_account"]
    state.dv_model.satellites.append(
        Satellite(name="eff_sat_account_customer", parent="link_account_customer",
                  attributes=["effective_from", "effective_to"],
                  description="Ownership validity.", sat_type="effectivity")
    )
    result = await AdrAuthorAgent(today="2026-06-10").run(state)

    assert "Caveat" not in result.adrs[0]


async def test_generation_gap_flags_produce_caveat_naming_the_construct() -> None:
    # Constructs the generator skipped carry GENERATION_GAP flags (kind/asset matching,
    # never message text); the caveat names exactly those, deduplicated.
    state = _state()
    state.dv_model.satellites.append(
        Satellite(name="sat_customer_addresses", parent="hub_customer",
                  attributes=["address"], description="multi-active",
                  sat_type="multi_active")
    )
    state.flag(
        "code_generator",
        "multi-active satellite 'sat_customer_addresses' has no child_dependent_key; "
        "cannot generate automate_dv.ma_sat, flagged for human review",
        kind=FlagKind.GENERATION_GAP,
        asset="sat_customer_addresses",
    )
    state.flag(  # duplicate asset — must not double-count
        "code_generator", "second flag for the same construct",
        kind=FlagKind.GENERATION_GAP, asset="sat_customer_addresses",
    )
    state.flag(  # different kind — must not leak into the caveat
        "code_generator", "sat_customer_addresses vs SAT_CUSTOMER_ADDRESSES",
        kind=FlagKind.COLUMN_COLLISION, asset="sat_customer_addresses",
    )
    result = await AdrAuthorAgent(today="2026-06-10").run(state)

    adr = result.adrs[0]
    assert ("- Caveat: 1 construct(s) could not be generated and are flagged for "
            "human review: sat_customer_addresses.") in adr
    assert "not yet generated" not in adr  # the old false capability claim is gone


async def test_reference_line_counts_raw_vault_and_staging_models() -> None:
    state = _state()
    state.artifacts.staging_models = {"stg_customer": "...", "stg_account_customer": "..."}
    result = await AdrAuthorAgent(today="2026-06-10").run(state)

    assert ("- Generated dbt models: 2 raw-vault model(s) + 2 staging model(s) "
            "(see `state.artifacts`)") in result.adrs[0]


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
    assert any("no model to document" in e.message for e in result.flags)
