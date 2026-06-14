"""Unit tests for the Orchestrator agent.

The orchestrator is deterministic (no LLM), so these run in CI without an API key. They
cover the planning entry node (ExecutionPlan) and the human-in-the-loop review queue
(ADR-0006): categorization, blocking-vs-advisory, owner de-duplication, and rendering.
"""
from vault_agent.agents.orchestrator import (
    HumanCheckpointAgent,
    OrchestratorAgent,
    apply_human_decision,
    assemble_review_queue,
    render_review_queue_md,
)
from vault_agent.state import (
    Artifacts,
    SourceTable,
    ValidationReport,
    VaultAgentState,
)

_STAGES = ["requirements_parser", "dv2_modeler", "validator", "adr_author"]


async def test_plan_records_stages_inputs_and_grounding() -> None:
    state = VaultAgentState(
        input_documents=["a.md", "b.md"],
        source_schemas=[SourceTable(table="customer", columns=["id"])],
    )
    result = await OrchestratorAgent(planned_stages=_STAGES).run(state)

    assert result.plan is not None
    assert result.plan.stages == _STAGES
    assert result.plan.input_documents == 2
    assert result.plan.grounded is True
    assert result.plan.notes == []
    assert result.decisions[-1] == {
        "agent": "orchestrator", "stages": 4, "inputs": 2, "grounded": True,
    }


async def test_plan_flags_missing_inputs() -> None:
    result = await OrchestratorAgent(planned_stages=_STAGES).run(VaultAgentState())

    assert result.plan is not None
    assert result.plan.input_documents == 0
    assert result.plan.grounded is False
    assert any("no input documents" in n for n in result.plan.notes)
    assert any("no input documents" in e for e in result.errors)


def _finished_state() -> VaultAgentState:
    return VaultAgentState(
        validation_report=ValidationReport(
            passed=False,
            issues=[
                {"severity": "error", "code": "E_NO_HUBS", "construct": "dv_model",
                 "message": "model has no hubs"},
                {"severity": "warning", "code": "W_SAT_WIDE", "construct": "sat_x",
                 "message": "satellite is wide"},
            ],
        ),
        artifacts=Artifacts(
            contracts=[
                {"name": "customer", "owner": {"name": "TODO: assign", "email": None}},
                {"name": "account", "owner": {"name": "Data Team", "email": "d@x.io"}},
            ],
        ),
        errors=[
            "data_contract: contract 'customer' has a placeholder owner; assign a real owner",
            "data_contract: field customer.'status' has an undetermined type; review required",
        ],
    )


def test_review_queue_categorizes_items() -> None:
    queue = assemble_review_queue(_finished_state())
    grouped = queue.by_kind()

    assert len(grouped["validation_error"]) == 1
    assert grouped["validation_error"][0].summary == "E_NO_HUBS on dv_model"
    assert len(grouped["validation_warning"]) == 1
    # Only the placeholder-owner contract needs an assignment; the assigned one is skipped.
    assert len(grouped["contract_owner"]) == 1
    assert "customer" in grouped["contract_owner"][0].summary


def test_review_queue_dedupes_owner_flag() -> None:
    queue = assemble_review_queue(_finished_state())
    grouped = queue.by_kind()

    # The placeholder-owner *flag* string is dropped (represented as a contract_owner item);
    # the unrelated undetermined-type flag survives as an advisory review_flag.
    flags = grouped.get("review_flag", [])
    assert all("placeholder owner" not in f.summary for f in flags)
    assert any("undetermined type" in f.summary for f in flags)


def test_requires_signoff_when_blocking_present() -> None:
    assert assemble_review_queue(_finished_state()).requires_signoff is True


def test_requires_signoff_false_when_only_advisory() -> None:
    state = VaultAgentState(
        validation_report=ValidationReport(
            passed=True,
            issues=[{"severity": "warning", "code": "W_HUB_NO_SAT",
                     "construct": "hub_x", "message": "no satellite"}],
        ),
        errors=["some advisory flag"],
    )
    queue = assemble_review_queue(state)

    assert queue.requires_signoff is False
    assert {i.kind for i in queue.items} == {"validation_warning", "review_flag"}


def test_empty_state_yields_empty_queue() -> None:
    queue = assemble_review_queue(VaultAgentState())
    assert queue.items == []
    assert queue.requires_signoff is False


def test_render_markdown_groups_and_marks_status() -> None:
    md = render_review_queue_md(assemble_review_queue(_finished_state()))

    assert md.startswith("# Human-in-the-loop checkpoint")
    assert "requires sign-off" in md
    assert "Validation errors (block agreement)" in md
    assert "Contract owners to assign (block agreement)" in md
    assert "E_NO_HUBS on dv_model" in md


def test_render_markdown_empty_queue() -> None:
    md = render_review_queue_md(assemble_review_queue(VaultAgentState()))
    assert "No items require human review" in md


# --- Human checkpoint apply / passthrough (ADR-0006) -------------------------------------


def _owner_state() -> VaultAgentState:
    return VaultAgentState(
        artifacts=Artifacts(
            contracts=[
                {"name": "customer", "owner": {"name": "TODO: assign", "email": None}},
                {"name": "account", "owner": {"name": "TODO: assign", "email": None}},
            ],
        ),
        errors=[
            "data_contract: contract 'customer' has a placeholder owner; assign a real owner",
            "data_contract: contract 'account' has a placeholder owner; assign a real owner",
            "data_contract: field customer.'status' has an undetermined type; review required",
        ],
    )


def test_apply_human_decision_assigns_and_prunes() -> None:
    state = _owner_state()
    assigned = apply_human_decision(
        state, {"owners": {"customer": {"name": "Data Team", "email": "d@x.io"}}}
    )

    assert assigned == ["customer"]
    assert state.artifacts.contracts[0]["owner"] == {"name": "Data Team", "email": "d@x.io"}
    # The resolved customer owner-flag is pruned; account's flag and the type flag remain.
    assert not any("'customer' has a placeholder owner" in e for e in state.errors)
    assert any("'account' has a placeholder owner" in e for e in state.errors)
    assert any("undetermined type" in e for e in state.errors)


def test_apply_human_decision_ignores_unknown_and_empty() -> None:
    state = _owner_state()
    assigned = apply_human_decision(
        state, {"owners": {"unknown_asset": {"name": "X"}, "customer": {"name": ""}}}
    )
    # Unknown asset is skipped; an empty name is not a valid assignment.
    assert assigned == []
    assert state.artifacts.contracts[0]["owner"]["name"] == "TODO: assign"


async def test_checkpoint_passthrough_when_nothing_blocks() -> None:
    # No contracts, no validation errors → nothing blocks, so no interrupt is raised
    # (calling interrupt() outside a graph run would fail; passthrough must not).
    result = await HumanCheckpointAgent().run(VaultAgentState(errors=["advisory only"]))

    assert result.decisions[-1] == {
        "agent": "human_checkpoint", "interrupted": False, "assigned": [],
    }
