"""Unit tests for the Orchestrator agent.

The orchestrator is deterministic (no LLM), so these run in CI without an API key. They
cover the planning entry node (ExecutionPlan) and the human-in-the-loop review queue
(ADR-0006): categorization, blocking-vs-advisory, owner de-duplication, and rendering.
"""
from vault_agent.agents.orchestrator import (
    AGGREGATE_THRESHOLD,
    HumanCheckpointAgent,
    OrchestratorAgent,
    ReviewItem,
    aggregate_review_flags,
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


# --- Review-queue aggregation (finding #3) -----------------------------------------------


def _noisy_state(n_type_flags: int) -> VaultAgentState:
    """A run with one substantive validation warning and many identical-shape type flags."""
    return VaultAgentState(
        validation_report=ValidationReport(
            passed=True,
            issues=[{"severity": "warning", "code": "W_LINK_REDUNDANT_GRAIN",
                     "construct": "link_a, link_b", "message": "same unit of work twice"}],
        ),
        errors=[
            f"data_contract: field VICTOR_PARTNER.{i!r} has an undetermined type; "
            f"review required before the contract is agreed"
            for i in [f"PARTN_NR_{n}" for n in range(n_type_flags)]
        ],
    )


def test_many_type_flags_collapse_to_one_line() -> None:
    queue = assemble_review_queue(_noisy_state(39))
    flags = queue.by_kind()["review_flag"]
    collapsed = aggregate_review_flags(flags)

    assert len(collapsed) == 1
    assert collapsed[0].summary == "39× undetermined field type"
    assert "VICTOR_PARTNER.PARTN_NR_0" in collapsed[0].detail
    # No data lost: the underlying queue still carries all 39 items.
    assert len(flags) == 39


def test_render_markdown_collapses_noise_but_keeps_warnings_first() -> None:
    md = render_review_queue_md(assemble_review_queue(_noisy_state(39)))

    assert "39× undetermined field type" in md
    # The substantive validation warning stays individual and is ordered before the
    # aggregated advisory block.
    assert "W_LINK_REDUNDANT_GRAIN" in md
    assert md.index("W_LINK_REDUNDANT_GRAIN") < md.index("39× undetermined field type")
    # The 39 individual lines are gone from the headline.
    assert "PARTN_NR_1 " not in md


def test_small_groups_are_not_aggregated() -> None:
    flags = assemble_review_queue(_noisy_state(AGGREGATE_THRESHOLD)).by_kind()["review_flag"]
    collapsed = aggregate_review_flags(flags)

    assert len(collapsed) == AGGREGATE_THRESHOLD
    assert all("undetermined type" in item.summary for item in collapsed)


def test_other_group_flags_always_individual() -> None:
    flags = [
        ReviewItem(kind="review_flag", summary=f"miscellaneous advisory {i}", group="other")
        for i in range(10)
    ]
    collapsed = aggregate_review_flags(flags)
    assert len(collapsed) == 10


def test_aggregation_preserves_signoff_and_item_count() -> None:
    # Aggregation is presentation-only: requires_signoff and the underlying item count are
    # driven by the queue, not the collapsed display.
    queue = assemble_review_queue(_noisy_state(39))
    assert queue.requires_signoff is False  # only advisory items here
    assert len(queue.items) == 40  # 1 validation warning + 39 type flags


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
