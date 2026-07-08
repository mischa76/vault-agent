"""WP8 / ADR-0009 acceptance tests: role-qualified link hub references.

Covers the naming helpers, the generator + staging role-qualified FK columns for a
self-referencing link, the new/adapted validator gates, and — the load-bearing one —
backward compatibility: a plain-string link must produce byte-identical output (acceptance
criterion #1). Keyless and deterministic (no Anthropic call)."""
import pytest

from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.staging_generator import collect_staging_specs
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.rules.dv2_rules import role_bk_column, role_fk_column
from vault_agent.state import (
    DVModel,
    Hub,
    Link,
    LinkHubRef,
    SourceTable,
    VaultAgentState,
)

# --- naming helpers -------------------------------------------------------------------


def test_role_fk_column_prefixes_normalised_role() -> None:
    assert role_fk_column("ACCOUNT_HK", "counterparty") == "COUNTERPARTY_ACCOUNT_HK"
    assert role_fk_column("ACCOUNT_HK", "the payer") == "THE_PAYER_ACCOUNT_HK"


def test_role_bk_column_prefixes_normalised_role() -> None:
    assert role_bk_column("ACCOUNT_NUMBER", "counterparty") == "COUNTERPARTY_ACCOUNT_NUMBER"


def test_role_helpers_are_identity_for_unqualified_refs() -> None:
    """role=None returns the column unchanged — the backward-compat invariant."""
    assert role_fk_column("ACCOUNT_HK", None) == "ACCOUNT_HK"
    assert role_bk_column("ACCOUNT_NUMBER", None) == "ACCOUNT_NUMBER"


# --- fixtures -------------------------------------------------------------------------


def _self_ref_model() -> DVModel:
    """A single hub_account with a self-referencing transactional link_transfer."""
    return DVModel(
        hubs=[
            Hub(
                name="hub_account",
                business_key="account number",
                source_entity="account",
                description="An account.",
            )
        ],
        links=[
            Link(
                name="link_transfer",
                connected_hubs=[
                    "hub_account",
                    LinkHubRef(hub="hub_account", role="counterparty"),
                ],
                description="A transfer between two accounts.",
                link_type="transactional",
                payload=["amount"],
                event_timestamp="transfer timestamp",
            )
        ],
    )


# --- generator ------------------------------------------------------------------------


async def test_self_referencing_link_generates_distinct_role_fk_columns() -> None:
    state = await CodeGeneratorAgent().run(VaultAgentState(dv_model=_self_ref_model()))
    meta = state.artifacts.automatedv_yaml["links"]["link_transfer"]
    assert meta["src_fk"] == ["ACCOUNT_HK", "COUNTERPARTY_ACCOUNT_HK"]
    sql = state.artifacts.dbt_models["link_transfer"]
    assert '"ACCOUNT_HK", "COUNTERPARTY_ACCOUNT_HK"' in sql
    assert "automate_dv.t_link" in sql
    # No generation-gap flag: the self-referencing link is fully modelable now.
    assert [f for f in state.flags if f.kind == "generation_gap"] == []


async def test_role_qualified_driving_key_selects_the_role_fk() -> None:
    """An eff_sat's driving key naming a role resolves to the role-qualified FK column."""
    model = DVModel(
        hubs=[
            Hub(name="hub_account", business_key="account number",
                source_entity="account", description="a"),
        ],
        links=[
            Link(
                name="link_transfer",
                connected_hubs=["hub_account", LinkHubRef(hub="hub_account", role="counterparty")],
                description="d",
                driving_key=["hub_account:counterparty"],
            )
        ],
        satellites=[],
    )
    # Add an effectivity satellite on the link so the driving/secondary split is exercised.
    from vault_agent.state import Satellite

    model.satellites.append(
        Satellite(
            name="sat_transfer_eff",
            parent="link_transfer",
            attributes=["effective from", "effective to"],
            description="active period",
            sat_type="effectivity",
        )
    )
    state = await CodeGeneratorAgent().run(VaultAgentState(dv_model=model))
    eff = state.artifacts.automatedv_yaml["satellites"]["sat_transfer_eff"]
    assert eff["src_dfk"] == "COUNTERPARTY_ACCOUNT_HK"
    assert eff["src_sfk"] == ["ACCOUNT_HK"]


# --- staging --------------------------------------------------------------------------


def test_staging_hashes_role_qualified_columns() -> None:
    specs = collect_staging_specs(_self_ref_model())
    spec = specs["stg_transfer"]
    hashed = dict(spec.hashed)
    assert hashed["ACCOUNT_HK"] == "ACCOUNT_NUMBER"
    assert hashed["COUNTERPARTY_ACCOUNT_HK"] == "COUNTERPARTY_ACCOUNT_NUMBER"
    # The link hash key covers both role-qualified business-key columns in declared order.
    assert hashed["LINK_TRANSFER_HK"] == ["ACCOUNT_NUMBER", "COUNTERPARTY_ACCOUNT_NUMBER"]
    assert "COUNTERPARTY_ACCOUNT_NUMBER" in spec.source_columns


# --- validator ------------------------------------------------------------------------


def _codes(state: VaultAgentState) -> set[str]:
    return {issue.code for issue in state.validation_report.issues}


async def test_dup_role_gate_fires_on_unqualified_self_reference() -> None:
    """hub_account twice with no role would collapse to one FK — E_LINK_DUP_ROLE."""
    model = DVModel(
        hubs=[Hub(name="hub_account", business_key="account number",
                  source_entity="account", description="a")],
        links=[Link(name="link_bad", connected_hubs=["hub_account", "hub_account"],
                    description="d")],
    )
    state = await ValidatorAgent().run(VaultAgentState(dv_model=model))
    assert "E_LINK_DUP_ROLE" in _codes(state)


async def test_role_qualified_self_reference_passes_dup_role_gate() -> None:
    state = await ValidatorAgent().run(VaultAgentState(dv_model=_self_ref_model()))
    assert "E_LINK_DUP_ROLE" not in _codes(state)


async def test_role_qualified_driving_key_is_accepted_by_validator() -> None:
    model = _self_ref_model()
    model.links[0].driving_key = ["hub_account:counterparty"]
    state = await ValidatorAgent().run(VaultAgentState(dv_model=model))
    assert "E_DRIVING_KEY_NOT_IN_LINK" not in _codes(state)


async def test_driving_key_naming_absent_role_is_flagged() -> None:
    model = _self_ref_model()
    model.links[0].driving_key = ["hub_account:nonexistent"]
    state = await ValidatorAgent().run(VaultAgentState(dv_model=model))
    assert "E_DRIVING_KEY_NOT_IN_LINK" in _codes(state)


async def test_grounded_run_flags_missing_role_bk_column() -> None:
    """A declared schema without the role-prefixed BK column raises W_ROLE_BK_NOT_IN_SOURCE."""
    model = _self_ref_model()
    state = VaultAgentState(
        dv_model=model,
        source_schemas=[
            SourceTable(table="raw_transfer", columns=["ACCOUNT_NUMBER", "AMOUNT"])
        ],
    )
    state = await ValidatorAgent().run(state)
    assert "W_ROLE_BK_NOT_IN_SOURCE" in _codes(state)


async def test_grounded_run_with_role_bk_column_is_clean() -> None:
    model = _self_ref_model()
    state = VaultAgentState(
        dv_model=model,
        source_schemas=[
            SourceTable(
                table="raw_transfer",
                columns=["ACCOUNT_NUMBER", "COUNTERPARTY_ACCOUNT_NUMBER", "AMOUNT"],
            )
        ],
    )
    state = await ValidatorAgent().run(state)
    assert "W_ROLE_BK_NOT_IN_SOURCE" not in _codes(state)


# --- backward compatibility (acceptance criterion #1) ---------------------------------


def _plain_model() -> DVModel:
    return DVModel(
        hubs=[
            Hub(name="hub_account", business_key="account number",
                source_entity="account", description="a"),
            Hub(name="hub_customer", business_key="customer id",
                source_entity="customer", description="c"),
        ],
        links=[
            Link(name="link_account_customer",
                 connected_hubs=["hub_account", "hub_customer"],
                 description="ownership", driving_key=["hub_account"]),
        ],
    )


async def test_plain_link_output_is_unaffected_by_role_support() -> None:
    """A link with only unqualified refs renders exactly as before roles existed:
    bare hub hash keys, no role prefix anywhere."""
    state = await CodeGeneratorAgent().run(VaultAgentState(dv_model=_plain_model()))
    meta = state.artifacts.automatedv_yaml["links"]["link_account_customer"]
    assert meta["src_fk"] == ["ACCOUNT_HK", "CUSTOMER_HK"]
    assert "COUNTERPARTY" not in state.artifacts.dbt_models["link_account_customer"]
    specs = collect_staging_specs(_plain_model())
    hashed = dict(specs["stg_account_customer"].hashed)
    assert hashed["LINK_ACCOUNT_CUSTOMER_HK"] == ["ACCOUNT_NUMBER", "CUSTOMER_ID"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
