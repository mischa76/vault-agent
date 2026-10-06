"""WP52 — honest chain metrics, the refused satellite's home, a conflict that is a decision
(spec §3). Committed before the change, failing.
"""
from __future__ import annotations

from tests.test_agents.test_dv2_modeler import StubExtractor, _state
from tests.test_wp46_composite_fk_components import _routing_model, _routing_schema
from eval.datasets import DATASETS_ROOT, load_eval_case
from eval.run import score_chain
from eval.scorers import pipeline_health
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.model_merger import merge_models
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    Link,
    PipelineFlag,
    RetiredConstruct,
    Satellite,
    ValidationIssue,
    ValidationReport,
    VaultAgentState,
)


def _hub(name: str) -> Hub:
    return Hub(name=name, business_key=f"{name}_id", source_entity=name[4:], description=name)


def _clean(hubs: list[str]) -> VaultAgentState:
    return VaultAgentState(
        dv_model=DVModel(hubs=[_hub(h) for h in hubs],
                         satellites=[Satellite(name=f"sat_{h[4:]}", parent=h, attributes=["x"],
                                               description="s") for h in hubs]),
        validation_report=ValidationReport(passed=True, issues=[]),
    )


# --- Guard 1: the chain's gate and health are the minimum over steps -------------------------


def test_chain_gate_and_health_are_the_minimum_over_steps() -> None:
    case = load_eval_case(DATASETS_ROOT / "adventureworks_incremental" / "dataset.yml")
    step1 = _clean(["hub_a"])
    step2 = _clean(["hub_a", "hub_b"])
    step2.validation_report = ValidationReport(
        passed=False,
        issues=[ValidationIssue(severity="error", code="E_NO_HUBS", construct="m", message="x")],
    )
    step2.flags.append(PipelineFlag(agent="dv2_modeler", message="bad", severity="error",
                                    kind=FlagKind.GENERIC))
    step3 = _clean(["hub_a", "hub_b", "hub_c"])  # the final state is clean
    results = score_chain(case, [(case, step1), (case, step2), (case, step3)], None)
    gate = next(r for r in results if r.name == "validation_gate")
    health = next(r for r in results if r.name == "pipeline_health")
    assert gate.score == 0.0 and "min over 3 step(s)" in gate.details
    assert health.score == 0.0 and "min over 3 step(s)" in health.details


# --- Guard 2: a refused satellite re-emitted unchanged lands on its single candidate ----------


def _retired(*, twin: str | None) -> RetiredConstruct:
    return RetiredConstruct(
        name="sat_work_order_operation_detail", kind="satellite", code="E_SAT_KEY_NOT_IN_SOURCE",
        attempt=1, parent="link_work_order_operation", source_table="WorkOrderRouting",
        kept_twin=twin,
    )


async def test_the_validator_records_the_single_candidate_as_the_satellites_twin() -> None:
    state = VaultAgentState(
        source_schemas=_routing_schema(),
        dv_model=DVModel.model_validate(_routing_model()),
        modeling_attempts=1,
    )
    await ValidatorAgent().run(state)
    [issue] = [i for i in state.validation_report.issues if i.code == "E_SAT_KEY_NOT_IN_SOURCE"]
    assert issue.retires_into == "hub_work_order"
    [retired] = state.retired_constructs
    assert retired.kind == "satellite" and retired.kept_twin == "hub_work_order"


async def test_a_refused_satellite_re_emitted_unchanged_moves_to_its_candidate() -> None:
    state = _state()
    state.source_schemas = _routing_schema()
    state.retired_constructs = [_retired(twin="hub_work_order")]
    state = await Dv2ModelerAgent(extractor=StubExtractor(_routing_model())).run(state)
    [sat] = state.dv_model.satellites
    assert sat.name == "sat_work_order_operation_detail" and sat.parent == "hub_work_order"
    assert [f.asset for f in state.flags if f.kind == FlagKind.RETIRED_REPARENTED] == [sat.name]
    assert not [f for f in state.flags if f.kind == FlagKind.RETIRED_ORPHAN]


async def test_without_a_candidate_the_orphan_decision_stands() -> None:
    state = _state()
    state.source_schemas = _routing_schema()
    state.retired_constructs = [_retired(twin=None)]
    state = await Dv2ModelerAgent(extractor=StubExtractor(_routing_model())).run(state)
    assert state.dv_model.satellites == []
    assert [f.asset for f in state.flags if f.kind == FlagKind.RETIRED_ORPHAN] == [
        "sat_work_order_operation_detail"
    ]


# --- Guard 3: an extension conflict is a decision, not a failure ------------------------------


def test_a_re_stated_existing_link_is_an_advisory_decision_and_the_vault_stands() -> None:
    existing = DVModel(
        hubs=[_hub("hub_a"), _hub("hub_b")],
        links=[Link(name="link_a_b", connected_hubs=["hub_a", "hub_b"], description="old")],
    )
    delta = DVModel(
        links=[Link(name="link_a_b", connected_hubs=["hub_a", "hub_b"], description="re-stated")],
    )
    state = VaultAgentState(existing_model=existing)
    merged = merge_models(existing, delta, state)
    [link] = merged.links
    assert link.description == "old"  # the vault is unchanged
    [flag] = [f for f in state.flags if f.kind == FlagKind.EXTENSION_CONFLICT]
    assert flag.severity == "advisory"
    case = load_eval_case(DATASETS_ROOT / "adventureworks_incremental" / "dataset.yml")
    assert pipeline_health(state, case).score == 1.0
