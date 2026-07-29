"""WP24 §2.3 — the WP7 × WP8 × WP10 composition matrix.

Three model features touch staging naming and hashing, and each was tested alone:

* **WP7 §7.1** — ``Satellite.source_table``: the satellite's rows live in their own
  (usually finer-grain) relation, so it gets a dedicated ``stg_<sat base>`` model.
* **WP8 / ADR-0009** — role-qualified link participations: one hub takes part twice.
* **WP10** — ``Hub.sources``: one business key fed by several source systems, one
  ``stg_<entity>_<source>`` per feed.

Their *combinations* were not tested, and two of them shipped broken (project review
2026-07-29, findings 2 + 3). This module fills the cross-product; every cell states its
expected outcome below, and the cells that are deliberately NOT generated say so:

| # | WP7 | WP8 | WP10 | outcome                                                      |
|---|-----|-----|------|--------------------------------------------------------------|
| 1 |  -  |  -  |  -   | generates                                                     |
| 2 |  x  |  -  |  -   | generates — dedicated sat staging                             |
| 3 |  -  |  x  |  -   | generates — role-qualified FKs                                |
| 4 |  -  |  -  |  x   | generates — one staging + one satellite per feed              |
| 5 |  x  |  x  |  -   | generates — sat staging hashes role-qualified parent-link FKs |
| 6 |  x  |  -  |  x   | ADR-0011: `source_table` naming a FEED binds the satellite    |
| 6b|  x  |  -  |  x   | **FLAGGED** — `source_table` naming a NON-feed (ADR-0011 row 3)|
| 7 |  -  |  x  |  x   | generates — role-qualified FK over the CANONICAL key column   |
| 8 |  x  |  x  |  x   | generates — the satellite's parent is the link, not the hub   |

Cell 6 SPLIT IN TWO when ADR-0011 landed (WP28). WP24 had rejected `source_table` on a
multi-source hub outright, reasoning that one relation cannot feed two independent sources.
That is true of a satellite describing ALL feeds and false of one describing ONE — and the
alternative it steered to was measurably broken (the split asked every feed's staging for
the named feed's columns). So the cell divides: naming a FEED binds the satellite to it
(cell 6, generated once), naming anything else stays rejected in three agreeing places
(cell 6b — validator gate, generation flag, no staging).

The load-bearing assertion is :func:`_hash_inputs`: across ALL staging models of one DV
model, a target column must be hashed from exactly ONE input set. Finding 2 was precisely
a violation of it (``CUSTOMER_HK`` hashed from ``CUSTOMER_KEY`` in the hub's staging and
from ``CUSTOMER_ID`` in the link's), and it is checked over every fixture model the suite
builds, not only the ones defined here. Keyless.
"""
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tests.test_agents.test_multi_source_hub import _multi_source_model
from tests.test_agents.test_wp8_role_links import _plain_model, _self_ref_model
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.staging_generator import (
    StagingSpec,
    _HashDiff,
    collect_staging_specs,
)
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.rules.dv2_rules import source_table_on_multi_source_hub
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    HubSource,
    Link,
    LinkHubRef,
    Satellite,
    VaultAgentState,
)

# ── model builders: one per matrix cell ───────────────────────────────────────────────────

# The feeds AGREE on a physical column name that differs from the business-key label, so
# canonical (CUSTOMER_KEY) != normalize(business_key) (CUSTOMER_ID). That is the case the
# whole pre-WP24 suite lacked: with disagreeing feeds the two coincide and finding 2 hides.
_AGREEING_FEEDS = [
    HubSource(source_table="crm_customer", business_key_column="customer_key"),
    HubSource(source_table="victor_partner", business_key_column="customer_key"),
]


def _hub(*, sources: list[HubSource] | None = None) -> Hub:
    return Hub(
        name="hub_customer",
        business_key="customer_id",
        source_entity="customer",
        description="the customer",
        sources=sources or [],
    )


def _account_hub() -> Hub:
    return Hub(
        name="hub_account",
        business_key="account_number",
        source_entity="account",
        description="the account",
    )


def _link(*, roles: bool) -> Link:
    """A link to the customer hub; with ``roles`` the account participates twice (WP8)."""
    hubs: list[str | LinkHubRef] = ["hub_account", "hub_customer"]
    if roles:
        hubs.append(LinkHubRef(hub="hub_account", role="counterparty"))
    return Link(
        name="link_account_customer",
        connected_hubs=hubs,
        description="account held by customer",
    )


def _sat(*, parent: str, source_table: str | None) -> Satellite:
    return Satellite(
        name="sat_" + parent.split("_", 1)[1] + "_details",
        parent=parent,
        attributes=["full_name"],
        description="details",
        source_table=source_table,
    )


def _cell(*, wp7: bool, wp8: bool, wp10: bool) -> DVModel:
    """One matrix cell. WP7 attaches the ``source_table`` satellite to the LINK, except in
    the cells that deliberately probe it on the multi-source hub (6) — see ``_cell_6``."""
    return DVModel(
        hubs=[_hub(sources=_AGREEING_FEEDS if wp10 else None), _account_hub()],
        links=[_link(roles=wp8)],
        satellites=[
            _sat(parent="link_account_customer", source_table="raw_roles" if wp7 else None)
        ],
    )


def _cell_6(source_table: str = "crm_customer") -> DVModel:
    """WP7 × WP10 on the MULTI-SOURCE HUB itself.

    Default: ``source_table`` names one of the hub's feeds → ADR-0011 binds it.
    Pass a non-feed table for cell 6b, which stays an error."""
    return DVModel(
        hubs=[_hub(sources=_AGREEING_FEEDS)],
        satellites=[_sat(parent="hub_customer", source_table=source_table)],
    )


MATRIX: dict[str, DVModel] = {
    "1-none": _cell(wp7=False, wp8=False, wp10=False),
    "2-wp7": _cell(wp7=True, wp8=False, wp10=False),
    "3-wp8": _cell(wp7=False, wp8=True, wp10=False),
    "4-wp10": _cell(wp7=False, wp8=False, wp10=True),
    "5-wp7-wp8": _cell(wp7=True, wp8=True, wp10=False),
    "6-wp7-wp10-feed": _cell_6(),
    "6b-wp7-wp10-nonfeed": _cell_6("raw_customer_details"),
    "7-wp8-wp10": _cell(wp7=False, wp8=True, wp10=True),
    "8-wp7-wp8-wp10": _cell(wp7=True, wp8=True, wp10=True),
}

# Cell 6b is the one combination that must NOT generate (ADR-0011 row 3).
FLAGGED_CELLS = {"6b-wp7-wp10-nonfeed"}


# ── the invariant ─────────────────────────────────────────────────────────────────────────
def _signature(value: str | list[str] | _HashDiff) -> tuple[Any, ...]:
    """Hashable shape of one hash input, comparable across staging models."""
    if isinstance(value, _HashDiff):
        return ("hashdiff", tuple(value.columns))
    if isinstance(value, list):
        return ("multi", tuple(value))
    return ("column", value)


def _hash_inputs(model: DVModel) -> dict[str, set[tuple[Any, ...]]]:
    """target column -> the distinct input sets it is hashed from, across ALL staging."""
    inputs: dict[str, set[tuple[Any, ...]]] = {}
    specs: dict[str, StagingSpec] = collect_staging_specs(model)
    for spec in specs.values():
        for target, value in spec.hashed:
            inputs.setdefault(target, set()).add(_signature(value))
    return inputs


def assert_one_input_per_target(model: DVModel, label: str) -> None:
    for target, signatures in _hash_inputs(model).items():
        assert len(signatures) == 1, (
            f"{label}: {target} is hashed from {len(signatures)} different inputs "
            f"{sorted(signatures)} — models referencing it can never join"
        )


async def _generate(model: DVModel) -> VaultAgentState:
    state = VaultAgentState(document_path="doc.md", dv_model=model)
    await CodeGeneratorAgent().run(state)
    return state


async def _validate(model: DVModel) -> list[str]:
    state = VaultAgentState(document_path="doc.md", dv_model=model)
    state = await ValidatorAgent().run(state)
    return [issue.code for issue in state.validation_report.issues]


# ── §3.6 the invariant over every fixture model in the suite ──────────────────────────────
def _demo_module(relative: str) -> ModuleType:
    path = Path(__file__).parents[2] / "demo" / relative / "build_vault_models.py"
    spec = importlib.util.spec_from_file_location(f"builder_{relative}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _suite_models() -> dict[str, DVModel]:
    """Every DV model the suite builds elsewhere, plus the matrix cells.

    The demo builders and the WP8/WP10 fixtures are the models the byte-identity guards and
    the Postgres verifications rest on — the invariant has to hold for them too, or the
    guards are guarding wrong output."""
    bank = _demo_module("bank_postgres")
    mapping = _demo_module("mapping_postgres")
    models = {
        "demo-bank": bank.build_bank_dv_model(),
        "demo-bank-transfer": bank.build_bank_dv_model_with_transfer(),
        "demo-mapping-grounded": mapping.build_grounded_bank_model(),
        "wp8-self-ref": _self_ref_model(),
        "wp8-plain": _plain_model(),
        "wp10-multi-source": _multi_source_model(),
    }
    models.update(MATRIX)
    return models


@pytest.mark.parametrize("label", sorted(_suite_models()))
def test_no_target_column_is_hashed_from_two_different_inputs(label: str) -> None:
    """Acceptance #1 — the invariant that catches finding 2 and any future repeat."""
    assert_one_input_per_target(_suite_models()[label], label)


# ── §3.2-3.4 the composition cells that must generate ─────────────────────────────────────
@pytest.mark.parametrize("label", sorted(set(MATRIX) - FLAGGED_CELLS))
@pytest.mark.asyncio
async def test_supported_cells_generate_without_a_generation_gap(label: str) -> None:
    state = await _generate(MATRIX[label])
    gaps = [flag for flag in state.flags if flag.kind == FlagKind.GENERATION_GAP]
    assert not gaps, f"{label}: unexpected generation gap {[flag.message for flag in gaps]}"
    assert state.artifacts.dbt_models, f"{label}: nothing generated"
    assert state.artifacts.staging_models, f"{label}: no staging generated"


def test_link_fk_hashes_the_hubs_canonical_column(  # §3.2 (review finding 2)
) -> None:
    """A link to a multi-source hub whose feeds AGREE stages the canonical source column —
    pre-WP24 it staged the business-key label and could never join the hub's hash key."""
    specs = collect_staging_specs(MATRIX["4-wp10"])
    link_spec = specs["stg_account_customer"]
    assert ("CUSTOMER_HK", "CUSTOMER_KEY") in link_spec.hashed
    assert all(target != "CUSTOMER_HK" or value == "CUSTOMER_KEY"
               for target, value in link_spec.hashed)
    hub_spec = specs["stg_customer_crm_customer"]
    assert ("CUSTOMER_HK", "CUSTOMER_KEY") in hub_spec.hashed


def test_source_table_sat_on_link_parent_hashes_canonical_columns() -> None:  # §3.3
    specs = collect_staging_specs(MATRIX["8-wp7-wp8-wp10"])
    sat_spec = specs["stg_account_customer_details"]
    hashed = dict(sat_spec.hashed)
    assert hashed["LINK_ACCOUNT_CUSTOMER_HK"] == [
        "ACCOUNT_NUMBER", "CUSTOMER_KEY", "COUNTERPARTY_ACCOUNT_NUMBER"
    ]


def test_role_qualified_participation_on_multi_source_hub() -> None:  # §3.4
    """The role prefix composes ON TOP of the canonical column, not instead of it."""
    model = DVModel(
        hubs=[_hub(sources=_AGREEING_FEEDS)],
        links=[
            Link(
                name="link_referral",
                connected_hubs=["hub_customer", LinkHubRef(hub="hub_customer",
                                                           role="referrer")],
                description="a customer referred by another customer",
            )
        ],
    )
    spec = collect_staging_specs(model)["stg_referral"]
    assert ("CUSTOMER_HK", "CUSTOMER_KEY") in spec.hashed
    assert ("REFERRER_CUSTOMER_HK", "REFERRER_CUSTOMER_KEY") in spec.hashed
    assert_one_input_per_target(model, "role-on-multi-source")


# ── §3.5 the rejected cell: gate + flag + nothing generated, staging included ──────────────
@pytest.mark.asyncio
async def test_source_table_naming_a_feed_binds_the_satellite_to_it() -> None:
    """ADR-0011 cell 6: the DV2.0-canonical one-satellite-per-source shape."""
    model = _cell_6()

    assert "E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB" not in await _validate(model)

    state = await _generate(model)
    assert not [f for f in state.flags if f.kind == FlagKind.GENERATION_GAP]
    # ONE satellite (no per-source suffix), bound to the named feed's staging.
    assert "sat_customer_details" in state.artifacts.dbt_models
    assert not [n for n in state.artifacts.dbt_models if n.startswith("sat_customer_details_")]
    assert "stg_customer_crm_customer" in state.artifacts.dbt_models["sat_customer_details"]
    # The OTHER feed's staging is not asked for this satellite's columns — the fix the
    # ADR's probe named.
    specs = collect_staging_specs(model)
    assert "FULL_NAME" not in specs["stg_customer_victor_partner"].source_columns
    assert "FULL_NAME" in specs["stg_customer_crm_customer"].source_columns


@pytest.mark.asyncio
async def test_source_table_naming_a_non_feed_is_flagged_not_generated() -> None:
    model = _cell_6("raw_customer_details")

    codes = await _validate(model)
    assert "E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB" in codes

    state = await _generate(model)
    gaps = [flag for flag in state.flags
            if flag.kind == FlagKind.GENERATION_GAP and flag.asset == "sat_customer_details"]
    assert len(gaps) == 1
    assert "source_table" in gaps[0].message

    generated = set(state.artifacts.dbt_models)
    assert not any(name.startswith("sat_") for name in generated), generated
    # ... and no ORPHAN staging model: the staging generator must skip exactly what the
    # raw-vault generator skipped, or the project references a hashdiff nothing computes.
    assert "stg_customer_details" not in state.artifacts.staging_models
    assert set(state.artifacts.staging_models) == {
        "stg_customer_crm_customer",
        "stg_customer_victor_partner",
    }


@pytest.mark.asyncio
async def test_source_table_sat_on_single_source_hub_still_generates() -> None:
    """The gate is about the COMBINATION — WP7 alone on a single-source hub is untouched."""
    model = DVModel(
        hubs=[_hub()],
        satellites=[_sat(parent="hub_customer", source_table="raw_customer_details")],
    )
    assert "E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB" not in await _validate(model)
    state = await _generate(model)
    assert "sat_customer_details" in state.artifacts.dbt_models
    assert "stg_customer_details" in state.artifacts.staging_models


# ── the shared predicate: what the three agreeing sites actually ask ───────────────────────
@pytest.mark.parametrize(
    ("sat_type", "source_table", "multi_source", "parent_is_hub", "expected"),
    [
        ("standard", "raw_details", True, True, True),  # the rejected cell
        ("multi_active", "raw_details", True, True, True),  # any non-eff type
        ("standard", None, True, True, False),  # WP10 alone
        ("standard", "raw_details", False, True, False),  # WP7 alone
        # source_table is documented as ignored for effectivity sats (they stage with the
        # parent link), so the combination is not theirs to reject.
        ("effectivity", "raw_details", True, True, False),
        ("standard", "raw_details", True, False, False),  # link parent: never this case
    ],
)
def test_source_table_on_multi_source_hub_predicate(
    sat_type: str, source_table: str | None, multi_source: bool,
    parent_is_hub: bool, expected: bool,
) -> None:
    sat = Satellite(
        name="sat_customer_details",
        parent="hub_customer" if parent_is_hub else "link_account_customer",
        attributes=["a", "b"],
        description="d",
        sat_type=sat_type,  # type: ignore[arg-type]
        child_dependent_key=["a"] if sat_type == "multi_active" else [],
        source_table=source_table,
    )
    parent = _hub(sources=_AGREEING_FEEDS if multi_source else None) if parent_is_hub else None
    assert source_table_on_multi_source_hub(sat, parent) is expected
