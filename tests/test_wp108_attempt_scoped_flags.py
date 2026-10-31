"""WP108 — the code generator and the model merger re-derive their flags on every run, so a
flag an earlier modeler attempt earned does not reach the sign-off (C8). Committed red before
the change. Keyless."""
from __future__ import annotations

from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.model_merger import merge_models
from vault_agent.state import DVModel, FlagKind, PipelineFlag, VaultAgentState


def _hub(name: str) -> dict[str, str]:
    return {"name": name, "business_key": f"{name[4:]}_id", "source_entity": name[4:],
            "description": "x"}


def _link() -> dict[str, object]:
    return {"name": "link_a_b", "description": "x", "connected_hubs": ["hub_a", "hub_b"]}


def _attempt_one() -> DVModel:
    """The link names `hub_b`, which this attempt did not build: a generation gap."""
    return DVModel.model_validate({"hubs": [_hub("hub_a")], "links": [_link()], "satellites": []})


def _attempt_two() -> DVModel:
    """The repaired model: both hubs, the same link — nothing to flag."""
    return DVModel.model_validate(
        {"hubs": [_hub("hub_a"), _hub("hub_b")], "links": [_link()], "satellites": []}
    )


def _gaps(state: VaultAgentState) -> list[str]:
    return [str(f.asset) for f in state.flags
            if f.agent == "code_generator" and f.kind == FlagKind.GENERATION_GAP]


async def test_the_generator_drops_an_earlier_attempts_flags_before_raising_this_ones() -> None:
    state = VaultAgentState(dv_model=_attempt_one())
    state = await CodeGeneratorAgent().run(state)
    assert _gaps(state) == ["link_a_b"]
    state.dv_model = _attempt_two()
    state = await CodeGeneratorAgent().run(state)
    assert _gaps(state) == []
    assert "link_a_b" in state.artifacts.dbt_models


async def test_other_agents_flags_survive_the_generators_re_run() -> None:
    state = VaultAgentState(dv_model=_attempt_one())
    kept = [
        PipelineFlag(agent="requirements_parser", message="segmented",
                     kind=FlagKind.INPUT_SEGMENTED, asset="doc.md"),
        PipelineFlag(agent="dv2_modeler", message="orphan", kind=FlagKind.RETIRED_ORPHAN,
                     asset="sat_gone"),
        PipelineFlag(agent="link_proposer", message="evidence", kind=FlagKind.LINK_BINDING_EVIDENCE,
                     asset="link_a_b", reason="key"),
    ]
    state.flags.extend(kept)
    state = await CodeGeneratorAgent().run(state)
    state.dv_model = _attempt_two()
    state = await CodeGeneratorAgent().run(state)
    assert [f for f in state.flags if f.agent != "code_generator"] == kept


def test_the_merger_re_derives_its_conflicts_from_this_attempts_delta() -> None:
    existing = DVModel.model_validate(
        {"hubs": [_hub("hub_a"), _hub("hub_b")], "links": [_link()], "satellites": []}
    )
    state = VaultAgentState()
    restating = DVModel.model_validate({"hubs": [], "links": [_link()], "satellites": []})
    merge_models(existing, restating, state)
    assert [f.asset for f in state.flags if f.kind == FlagKind.EXTENSION_CONFLICT] == ["link_a_b"]
    clean = DVModel.model_validate({"hubs": [_hub("hub_c")], "links": [], "satellites": []})
    merge_models(existing, clean, state)
    assert [f for f in state.flags if f.kind == FlagKind.EXTENSION_CONFLICT] == []


def test_the_merger_keeps_a_conflict_the_last_delta_still_earns() -> None:
    existing = DVModel.model_validate(
        {"hubs": [_hub("hub_a"), _hub("hub_b")], "links": [_link()], "satellites": []}
    )
    state = VaultAgentState()
    restating = DVModel.model_validate({"hubs": [], "links": [_link()], "satellites": []})
    merge_models(existing, restating, state)
    merge_models(existing, restating, state)
    assert [f.asset for f in state.flags if f.kind == FlagKind.EXTENSION_CONFLICT] == ["link_a_b"]
