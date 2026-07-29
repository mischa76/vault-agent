"""Unit tests for the ADR Author agent (deterministic, no API key needed)."""
from pathlib import Path

from vault_agent.agents.adr_author import AdrAuthorAgent
from vault_agent.state import (
    Artifacts,
    BusinessKeyCandidate,
    DVModel,
    FlagKind,
    Hub,
    HubSource,
    Link,
    LinkHubRef,
    ParsedRequirement,
    Proposal,
    ProposedMapping,
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


def _rich_state() -> VaultAgentState:
    """A model exercising every field the ADR rendered BEFORE WP26 — and none it did not.

    Pinned byte-for-byte against a fixture generated from the pre-WP26 renderer, so the
    WP26 additions (multi-source feeds, driving keys, satellite types, mappings) can only
    ever be *additive*: a model that carries none of them must render exactly as it did."""
    state = _state()
    state.dv_model.links[0].unit_of_work = "one ownership event per (account, customer)"
    state.dv_model.satellites[0].split_rationale = "split from PII by rate of change"
    state.dv_model.satellites.append(
        Satellite(name="sat_account_balances", parent="hub_customer",
                  attributes=["balance"], description="Balances.",
                  requirement_ids=["REQ-011"])
    )
    state.artifacts.staging_models = {"stg_customer": "...", "stg_account_customer": "..."}
    state.flag(
        "code_generator", "could not generate", kind=FlagKind.GENERATION_GAP,
        asset="sat_account_balances",
    )
    return state


def _rich_state_with_mappings() -> VaultAgentState:
    """``_rich_state`` plus every WP26 addition, for the determinism comparison."""
    state = _rich_state()
    state.dv_model.hubs[0].sources = [
        HubSource(source_table="crm_customer", business_key_column="cust_id"),
        HubSource(source_table="victor_partner", business_key_column="partn_id"),
    ]
    state.dv_model.links[0].driving_key = ["hub_account"]
    state.mappings = ProposedMapping(
        proposals=[Proposal(concept="customer name", table="CUSTOMER", column="CUST_NAME")],
        gaps=["effective_from"],
        unresolved=["customer reference"],
    )
    return state


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


async def test_same_state_and_date_yield_byte_identical_adr() -> None:
    # Idempotency guarantee, stated as precisely as the module now does (WP26 §2.3): same
    # state AND same date in, byte-identical ADR out — consistent with the code generator,
    # and safe for re-runs into the same output directory. The date is the one input that
    # does not come from state; everything else here is a projection of it, including the
    # WP26 additions (mappings, feeds, driving keys), which this covers by using the rich
    # state rather than the minimal one.
    first = await AdrAuthorAgent(today="2026-06-10").run(_rich_state_with_mappings())
    second = await AdrAuthorAgent(today="2026-06-10").run(_rich_state_with_mappings())

    assert first.adrs == second.adrs
    assert "### Source mappings" in first.adrs[0]  # the added section is in the comparison


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


# ── WP26: completeness (§2.1/§2.2) and the byte-identity guard it must not break ──────────
_PRE_WP26_FIXTURE = Path(__file__).parents[1] / "fixtures" / "adr" / "adr_pre_wp26.md"


async def test_model_without_wp26_fields_renders_byte_identically(  # §3.1 / acceptance #3
) -> None:
    """The fixture was generated from the PRE-WP26 renderer (with the src changes stashed),
    so this pins the additions as strictly additive rather than merely self-consistent."""
    result = await AdrAuthorAgent(today="2026-06-10").run(_rich_state())

    assert result.adrs[0] == _PRE_WP26_FIXTURE.read_text(encoding="utf-8")


async def test_multi_source_hub_renders_feeds_and_canonical_key() -> None:  # §2.1
    state = _state()
    state.dv_model.hubs[0].sources = [
        HubSource(source_table="crm_customer", business_key_column="cust_id"),
        HubSource(source_table="victor_partner", business_key_column="partn_id"),
    ]
    adr = (await AdrAuthorAgent(today="2026-06-10").run(state)).adrs[0]

    assert ("Integrated from 2 source(s): crm_customer.cust_id, victor_partner.partn_id; "
            "canonical staging key column `NATIONAL_CUSTOMER_ID`.") in adr


async def test_canonical_key_comes_from_the_rules_helper() -> None:
    # Feeds that AGREE keep the source column name (WP10 §2.2) — the ADR must document the
    # column staging actually builds, so it asks rules/ instead of re-deriving the name.
    state = _state()
    state.dv_model.hubs[0].sources = [
        HubSource(source_table="crm_customer", business_key_column="customer_key"),
        HubSource(source_table="victor_partner", business_key_column="customer_key"),
    ]
    adr = (await AdrAuthorAgent(today="2026-06-10").run(state)).adrs[0]

    assert "canonical staging key column `CUSTOMER_KEY`." in adr


async def test_driving_key_renders_like_the_participation_list() -> None:  # §3.4
    state = _state()
    link = state.dv_model.links[0]
    link.connected_hubs = ["hub_account", "hub_customer",
                           LinkHubRef(hub="hub_account", role="counterparty")]
    link.driving_key = ["hub_account:counterparty"]
    adr = (await AdrAuthorAgent(today="2026-06-10").run(state)).adrs[0]

    assert "connects hub_account, hub_customer, hub_account (counterparty)." in adr
    assert "Driving key: hub_account (counterparty)." in adr


async def test_unresolvable_driving_key_entry_is_not_rendered() -> None:
    # E_DRIVING_KEY_NOT_IN_LINK owns that complaint; the ADR does not duplicate it.
    state = _state()
    state.dv_model.links[0].driving_key = ["hub_nonexistent"]
    adr = (await AdrAuthorAgent(today="2026-06-10").run(state)).adrs[0]

    assert "Driving key" not in adr


async def test_satellite_type_cdk_and_source_table_render() -> None:  # §2.1
    state = _state()
    state.dv_model.satellites.append(
        Satellite(name="sat_customer_addresses", parent="hub_customer",
                  attributes=["street", "city"], description="Addresses.",
                  sat_type="multi_active", child_dependent_key=["address_type"],
                  source_table="raw_customer_addresses")
    )
    state.dv_model.satellites.append(
        Satellite(name="sat_ownership_effectivity", parent="link_account_customer",
                  attributes=["effective_from", "effective_to"],
                  description="Validity.", sat_type="effectivity")
    )
    adr = (await AdrAuthorAgent(today="2026-06-10").run(state)).adrs[0]

    assert "Multi-active satellite, child dependent key: address_type." in adr
    assert "Source table: raw_customer_addresses." in adr
    assert "Effectivity satellite." in adr
    # A standard satellite says nothing about its type — silence means standard.
    assert "sat_customer_details** — on hub_customer; payload: customer name, date of " \
           "birth. Customer attributes. _(requirements" in adr


async def test_transactional_link_renders_payload_and_event_timestamp() -> None:
    # link_type selects automate_dv.t_link, so it changes what is built — acceptance #1.
    state = _state()
    link = state.dv_model.links[0]
    link.link_type = "transactional"
    link.payload = ["amount", "currency"]
    link.event_timestamp = "transaction_ts"
    adr = (await AdrAuthorAgent(today="2026-06-10").run(state)).adrs[0]

    assert ("Transactional link (non-historized): payload amount, currency; "
            "event timestamp transaction_ts.") in adr


async def test_ungrounded_run_has_no_mappings_section() -> None:  # §3.2
    adr = (await AdrAuthorAgent(today="2026-06-10").run(_state())).adrs[0]

    assert "Source mappings" not in adr


async def test_mappings_section_renders_proposals_gaps_and_unresolved() -> None:  # §3.3
    state = _state()
    state.mappings = ProposedMapping(
        proposals=[
            Proposal(concept="national customer ID", table="CUSTOMER",
                     column="NATIONAL_CUSTOMER_ID", category="exact_name",
                     ratification_status="accepted"),
            Proposal(concept="customer name", table="CUSTOMER", column="CUST_NAME",
                     category="comment_grounded"),
        ],
        gaps=["effective_from", "effective_to"],
        unresolved=["customer reference"],
    )
    adr = (await AdrAuthorAgent(today="2026-06-10").run(state)).adrs[0]

    assert "### Source mappings (2)" in adr
    assert ("- `national customer ID` → `CUSTOMER`.`NATIONAL_CUSTOMER_ID` — exact_name, "
            "accepted") in adr
    assert "- `customer name` → `CUSTOMER`.`CUST_NAME` — comment_grounded, proposed" in adr
    assert ("No in-scope source — Business Vault / marts (2): effective_from, "
            "effective_to.") in adr
    assert "Unresolved — the mapper could not decide (1): customer reference." in adr


async def test_gaps_only_mapping_still_renders_the_section() -> None:
    # A gap is first-class output (ADR-0008 #3), not an absence of one.
    state = _state()
    state.mappings = ProposedMapping(gaps=["effective_from"])
    adr = (await AdrAuthorAgent(today="2026-06-10").run(state)).adrs[0]

    assert "### Source mappings (0)" in adr
    assert "No in-scope source — Business Vault / marts (1): effective_from." in adr


