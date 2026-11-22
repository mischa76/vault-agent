"""WP47 — a typed reason on every inferred staging binding, and the cumulative-catalogue chain
variant (spec §3). Committed before the change, failing.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from eval import run as run_mod
from eval.datasets import DATASETS_ROOT, ChainSpec, EvalCase, load_eval_case
from eval.run import UsageTotals, run_metrics
from vault_agent.agents.orchestrator import flag_role
from vault_agent.agents.staging_generator import bind_sources, collect_staging_specs
from vault_agent.link_proposal import link_binding_reasons
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    Link,
    PipelineFlag,
    SourceTable,
    VaultAgentState,
)


def _hub(name: str, entity: str, key: str = "Id") -> Hub:
    return Hub(name=name, business_key=key, source_entity=entity, description=name)


# --- Guard 1: the binder stamps the reason -----------------------------------------------


def test_bind_sources_stamps_none_by_default_and_the_given_reason_otherwise() -> None:
    model = DVModel(
        hubs=[_hub("hub_customer", "Customer"), _hub("hub_product", "Product")],
        links=[Link(name="link_customer_product", connected_hubs=["hub_customer", "hub_product"],
                    description="l")],
    )
    specs = collect_staging_specs(model)
    flags = bind_sources(
        specs, [SourceTable(table="Customer", columns=["Id"])],
        binding_reasons={"CUSTOMER_PRODUCT": "ambiguous"},  # keyed like the overrides
    )
    by_asset = {f.asset: f for f in flags}
    assert by_asset["stg_product"].reason == "none"  # nothing declares Product
    assert by_asset["stg_customer_product"].reason == "ambiguous"
    assert "stg_customer" not in by_asset  # bound by name: no flag at all
    assert all(f.kind == FlagKind.SOURCE_BINDING for f in flags)


# --- Guard 2: the reasons come from the resolution the overrides come from ----------------


def _two_offers() -> VaultAgentState:
    """Two declared relations each offering (hub_a, hub_b): the link binds nothing (WP42)."""
    fks = [
        {"columns": ["AId"], "references_table": "A", "references_columns": ["AId"]},
        {"columns": ["BId"], "references_table": "B", "references_columns": ["BId"]},
    ]
    return VaultAgentState(
        dv_model=DVModel(
            hubs=[_hub("hub_a", "A", "AId"), _hub("hub_b", "B", "BId"),
                  _hub("hub_shared", "Shared", "SId")],
            links=[
                Link(name="link_a_b", connected_hubs=["hub_a", "hub_b"], description="l"),
                Link(name="link_shared", connected_hubs=["hub_shared", "hub_a"], description="s"),
                Link(name="link_a_lonely", connected_hubs=["hub_a", "hub_b"], description="n"),
            ],
        ),
        source_schemas=[
            SourceTable(table="A", columns=["AId"]),
            SourceTable(table="B", columns=["BId"]),
            SourceTable(table="Shared", columns=["SId", "AId"],
                        foreign_keys=[fks[0]]),
            SourceTable(table="R1", columns=["AId", "BId"], foreign_keys=fks),
            SourceTable(table="R2", columns=["AId", "BId"], foreign_keys=fks),
        ],
    )


def test_link_binding_reasons_name_shared_ambiguous_and_none() -> None:
    reasons = link_binding_reasons(_two_offers())
    assert reasons["SHARED"] == "shared"  # link_shared's base is hub_shared's
    assert reasons["A_B"] == "ambiguous"  # R1 and R2 both offer (hub_a, hub_b)
    assert reasons["A_LONELY"] == "ambiguous"  # same participations, same two offers
    assert "A" not in reasons and "B" not in reasons  # hubs are not links


def test_a_link_bound_by_one_offer_or_by_name_has_no_reason_entry() -> None:
    state = _two_offers()
    state.source_schemas = [t for t in state.source_schemas if t.table != "R2"]
    reasons = link_binding_reasons(state)
    assert "A_B" not in reasons  # exactly one offer now: bound by the override, not flagged
    assert reasons.get("SHARED") == "shared"


# --- Guard 3: the role follows the reason -------------------------------------------------


def test_an_ambiguous_binding_is_a_decision_and_the_others_disclosures() -> None:
    def flag(reason: str | None) -> PipelineFlag:
        return PipelineFlag(agent="code_generator", message="m", kind=FlagKind.SOURCE_BINDING,
                            asset="stg_x", reason=reason)
    assert flag_role(flag("ambiguous")) == "decision"
    assert flag_role(flag("none")) == "disclosure"
    assert flag_role(flag("shared")) == "disclosure"
    assert flag_role(flag(None)) == "disclosure"


# --- Guard 4: metrics and identity --------------------------------------------------------


def test_run_metrics_carry_flag_reasons_and_identity_tells_reasons_apart() -> None:
    state = VaultAgentState()
    for reason in ("none", "none", "ambiguous"):
        state.flags.append(PipelineFlag(agent="code_generator", message="m",
                                        kind=FlagKind.SOURCE_BINDING, asset="stg_x",
                                        reason=reason))
    metrics = run_metrics(state, 1.0, UsageTotals())
    assert metrics["flag_reasons"] == {"source_binding": {"ambiguous": 1, "none": 2}}
    a, b = state.flags[0], state.flags[2]
    assert a.identity() != b.identity()


# --- Guard 5: the cumulative chain variant -------------------------------------------------


def test_chain_spec_has_the_cumulative_flag_and_the_new_case_loads() -> None:
    assert ChainSpec(steps=["a", "b"]).cumulative_schema is False
    case = load_eval_case(DATASETS_ROOT / "adventureworks_incremental_cumulative" / "dataset.yml")
    assert case.chain is not None and case.chain.cumulative_schema is True
    assert case.chain.steps == load_eval_case(
        DATASETS_ROOT / "adventureworks_incremental" / "dataset.yml"
    ).chain.steps  # type: ignore[union-attr]
    assert case.expectations.min_scores["existing_construct_preservation"] == 1.0


def test_run_chain_once_hands_each_step_the_earlier_steps_schemas_when_cumulative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[str, list[str]]] = []

    async def fake_run_case_once(case: EvalCase) -> VaultAgentState:
        seen.append((case.name, [p.parent.name for p in case.extra_source_schemas]))
        return VaultAgentState()

    monkeypatch.setattr(run_mod, "run_case_once", fake_run_case_once)
    cumulative = load_eval_case(
        DATASETS_ROOT / "adventureworks_incremental_cumulative" / "dataset.yml"
    )
    asyncio.run(run_mod.run_chain_once(cumulative, tmp_path / "c"))
    assert seen[0] == ("adventureworks_person", [])
    assert seen[1] == ("adventureworks_humanresources", ["adventureworks_person"])
    assert seen[4][1] == ["adventureworks_person", "adventureworks_humanresources",
                          "adventureworks_production", "adventureworks_purchasing"]

    seen.clear()
    plain = load_eval_case(DATASETS_ROOT / "adventureworks_incremental" / "dataset.yml")
    asyncio.run(run_mod.run_chain_once(plain, tmp_path / "p"))
    assert all(extra == [] for _, extra in seen)  # the existing chain is untouched


def test_extra_schemas_merge_first_declaration_wins(tmp_path: Path) -> None:
    own = tmp_path / "own.yml"
    own.write_text("source_schemas:\n- table: T\n  columns: [A, B]\n- table: U\n  columns: [X]\n")
    earlier = tmp_path / "earlier.yml"
    earlier.write_text("source_schemas:\n- table: T\n  columns: [A]\n- table: V\n  columns: [Y]\n")
    tables = run_mod.merged_source_schemas(own, [earlier])
    assert [t.table for t in tables] == ["T", "U", "V"]
    assert [c for c in tables[0].column_names] == ["A", "B"]  # the step's own T wins
