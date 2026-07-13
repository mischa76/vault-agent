"""Keyless tests for the SourceMapperAgent deterministic core (WP9 §4). Stubbed proposer."""
from typing import Any

from vault_agent.agents.source_mapper import SourceMapperAgent
from vault_agent.state import (
    ColumnProfile,
    DVModel,
    FlagKind,
    Hub,
    Satellite,
    SourceColumn,
    SourceTable,
    VaultAgentState,
)


class _StubProposer:
    """Returns a scripted decisions dict; records the payload it was given."""

    def __init__(self, decisions: dict[str, Any]) -> None:
        self.decisions = decisions
        self.calls = 0
        self.last_user_content: str | None = None

    async def propose(self, *, system_prompt: str, user_content: str) -> dict[str, Any]:
        self.calls += 1
        self.last_user_content = user_content
        return self.decisions


def _model() -> DVModel:
    return DVModel(
        hubs=[
            Hub(
                name="hub_customer",
                business_key="national customer ID",
                source_entity="customer",
                description="d",
            )
        ],
        satellites=[
            Satellite(
                name="sat_customer_details",
                parent="hub_customer",
                attributes=["customer name", "date of birth"],
                description="d",
            )
        ],
    )


def _schema() -> list[SourceTable]:
    return [
        SourceTable(
            table="raw_customer",
            columns=[
                SourceColumn(name="NATIONAL_CUSTOMER_ID", type="varchar(11)",
                             comment="the national customer identifier"),
                SourceColumn(name="CUST_NAME", type="varchar(120)", comment="customer name"),
                SourceColumn(name="DOB", type="date"),
                SourceColumn(name="BRANCH_CODE", type="varchar(4)",
                             comment="legacy branch code, not a customer number"),
            ],
        )
    ]


def _state(**kw: Any) -> VaultAgentState:
    return VaultAgentState(dv_model=_model(), source_schemas=_schema(), **kw)


async def test_ungrounded_run_is_inert_no_llm_call() -> None:
    proposer = _StubProposer({})
    state = VaultAgentState(dv_model=_model())  # no source_schemas
    out = await SourceMapperAgent(proposer).run(state)
    assert proposer.calls == 0  # keyless / byte-identical: no LLM call
    assert out.mappings.proposals == [] and not out.flags


async def test_maps_gaps_and_unresolved() -> None:
    proposer = _StubProposer(
        {
            "national customer ID": {"decision": "map", "table": "raw_customer",
                                     "column": "NATIONAL_CUSTOMER_ID", "confidence": 0.95,
                                     "evidence": ["comment: national customer identifier"]},
            "customer name": {"decision": "map", "table": "raw_customer", "column": "CUST_NAME",
                              "confidence": 0.8, "evidence": ["comment: customer name"]},
            "date of birth": {"decision": "gap", "evidence": ["no source column"]},
        }
    )
    state = _state()
    out = await SourceMapperAgent(proposer).run(state)
    proposed = {p.concept: (p.table, p.column) for p in out.mappings.proposals}
    assert proposed["national customer ID"] == ("raw_customer", "NATIONAL_CUSTOMER_ID")
    assert proposed["customer name"] == ("raw_customer", "CUST_NAME")
    assert out.mappings.gaps == ["date of birth"]
    kinds = {f.kind for f in out.flags}
    assert FlagKind.MAPPING_GAP in kinds


async def test_never_invents_a_column_demotes_to_unresolved() -> None:
    # The proposer names a column that does not exist -> unresolved, never fabricated.
    proposer = _StubProposer(
        {
            "national customer ID": {"decision": "map", "table": "raw_customer",
                                     "column": "DOES_NOT_EXIST", "confidence": 0.9},
            "customer name": {"decision": "map", "table": "raw_customer", "column": "CUST_NAME"},
            "date of birth": {"decision": "map", "table": "raw_customer", "column": "DOB"},
        }
    )
    state = _state()
    out = await SourceMapperAgent(proposer).run(state)
    assert "national customer ID" in out.mappings.unresolved
    assert all(p.concept != "national customer ID" for p in out.mappings.proposals)
    assert any(f.kind == FlagKind.MAPPING_UNRESOLVED for f in out.flags)


async def test_multi_source_key_unresolved_keeps_candidates() -> None:
    proposer = _StubProposer(
        {
            "national customer ID": {"decision": "unresolved",
                                     "evidence": ["raw_customer.NATIONAL_CUSTOMER_ID",
                                                  "crm.EXTERNAL_CUSTOMER_NO"]},
        }
    )
    state = _state()
    out = await SourceMapperAgent(proposer).run(state)
    assert "national customer ID" in out.mappings.unresolved
    flag = next(f for f in out.flags if f.kind == FlagKind.MAPPING_UNRESOLVED)
    assert "candidates" in flag.message and "WP10" in flag.message


async def test_category_tiers() -> None:
    proposer = _StubProposer(
        {
            # exact-name: concept normalises to the column name
            "NATIONAL_CUSTOMER_ID": {"decision": "map", "table": "raw_customer",
                                     "column": "NATIONAL_CUSTOMER_ID"},
            # comment-grounded: concept tokens appear in the column comment
            "customer name": {"decision": "map", "table": "raw_customer", "column": "CUST_NAME"},
        }
    )
    model = DVModel(
        hubs=[Hub(name="hub_customer", business_key="NATIONAL_CUSTOMER_ID",
                  source_entity="customer", description="d")],
        satellites=[Satellite(name="sat_customer_details", parent="hub_customer",
                              attributes=["customer name"], description="d")],
    )
    state = VaultAgentState(dv_model=model, source_schemas=_schema())
    out = await SourceMapperAgent(proposer).run(state)
    by_concept = {p.concept: p.category for p in out.mappings.proposals}
    assert by_concept["NATIONAL_CUSTOMER_ID"] == "exact_name"
    assert by_concept["customer name"] == "comment_grounded"


async def test_profiled_key_category() -> None:
    # Isolate the profiled_key tier: concept does NOT normalise to the column name (rules out
    # exact_name) and the comment tokens do NOT overlap the concept (rules out comment_grounded),
    # but it is a business_key with a clean-key profile.
    proposer = _StubProposer(
        {"partner reference": {"decision": "map", "table": "raw_customer", "column": "CUST_KEY"}}
    )
    schema = [
        SourceTable(
            table="raw_customer",
            columns=[SourceColumn(name="CUST_KEY", comment="legacy surrogate")],
        )
    ]
    state = VaultAgentState(
        dv_model=DVModel(hubs=[Hub(name="hub_customer", business_key="partner reference",
                                   source_entity="customer", description="d")]),
        source_schemas=schema,
        profiling={"raw_customer": {"CUST_KEY": ColumnProfile(
            name="CUST_KEY", uniqueness_ratio=0.999, null_ratio=0.001)}},
    )
    out = await SourceMapperAgent(proposer).run(state)
    assert out.mappings.proposals[0].category == "profiled_key"


async def test_staging_rebind_overrides_source_binding() -> None:
    # A mapped hub key binds its staging to the real source table, clearing SOURCE_BINDING.
    proposer = _StubProposer(
        {
            "national customer ID": {"decision": "map", "table": "raw_customer",
                                     "column": "NATIONAL_CUSTOMER_ID"},
            "customer name": {"decision": "map", "table": "raw_customer", "column": "CUST_NAME"},
            "date of birth": {"decision": "map", "table": "raw_customer", "column": "DOB"},
        }
    )
    state = _state()
    out = await SourceMapperAgent(proposer).run(state)
    # The customer staging model exists and binds to raw_customer (the mapped table).
    assert "stg_customer" in out.artifacts.staging_models
    meta = out.artifacts.staging_models["stg_customer"]
    assert "raw_customer" in meta
    # The override cleared the inferred-binding flag for the customer staging.
    assert not any(
        f.kind == FlagKind.SOURCE_BINDING and f.asset == "stg_customer" for f in out.flags
    )


def test_apply_human_decision_ratifies_and_rebinds() -> None:
    from vault_agent.agents.orchestrator import apply_human_decision
    from vault_agent.state import Proposal, ProposedMapping

    state = _state()
    # One proposed mapping (the hub key), one unresolved concept, plus its flag.
    state.mappings = ProposedMapping(
        proposals=[Proposal(concept="customer name", table="raw_customer", column="CUST_NAME")],
        unresolved=["national customer ID"],
    )
    state.flag("source_mapper", "unresolved", kind=FlagKind.MAPPING_UNRESOLVED,
               asset="national customer ID")
    decision = {
        "owners": {},
        "accept": True,
        "mappings": {"national customer ID": "raw_customer.NATIONAL_CUSTOMER_ID"},
    }
    apply_human_decision(state, decision)

    by_concept = {p.concept: p for p in state.mappings.proposals}
    # The overridden concept is now a proposal bound to the chosen column, status overridden.
    assert by_concept["national customer ID"].column == "NATIONAL_CUSTOMER_ID"
    assert by_concept["national customer ID"].ratification_status == "overridden"
    assert "national customer ID" not in state.mappings.unresolved
    # accept marked the pre-existing proposal accepted.
    assert by_concept["customer name"].ratification_status == "accepted"
    # The resolved unresolved-flag was pruned.
    assert not any(f.kind == FlagKind.MAPPING_UNRESOLVED for f in state.flags)
    # Staging was re-bound to the ratified table.
    assert "raw_customer" in state.artifacts.staging_models.get("stg_customer", "")


def test_concept_worklist_dedups_and_orders() -> None:
    concepts = SourceMapperAgent._concepts(_state())
    labels = [c.concept for c in concepts]
    assert labels[0] == "national customer ID"  # hub key first
    assert "customer name" in labels and "date of birth" in labels
    assert len(labels) == len(set(labels))
    kinds = {c.concept: c.kind for c in concepts}
    assert kinds["national customer ID"] == "business_key"
    assert kinds["customer name"] == "attribute"
