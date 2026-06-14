"""Shared state passed through the LangGraph nodes."""
from typing import Any, Literal

from pydantic import BaseModel, Field


class ParsedRequirement(BaseModel):
    """One requirement extracted by the Requirements Parser."""
    id: str
    text: str
    category: str  # functional | non-functional | business-rule | constraint
    actor: str | None = None
    action: str | None = None
    obj: str | None = None  # 'object' is reserved


class BusinessKeyCandidate(BaseModel):
    entity: str
    field: str
    score: float
    rationale: str


class SourceTable(BaseModel):
    """A declared source table the model can be grounded against (ADR-0004).

    Optional input: when ``VaultAgentState.source_schemas`` is non-empty the validator
    flags business keys / attributes that match no declared column, and the modeler and
    business-key prompts are steered toward these real columns."""
    table: str  # the source table / entity name
    columns: list[str] = Field(default_factory=list)  # its column names, as in the source


class Hub(BaseModel):
    """A Data Vault hub: one business concept, anchored on its business key."""
    name: str  # e.g. "hub_customer"
    business_key: str  # the natural key field this hub is built on
    source_entity: str  # the business object, e.g. "customer"
    description: str
    requirement_ids: list[str] = Field(default_factory=list)


class Link(BaseModel):
    """A Data Vault link: a relationship connecting two or more hubs."""
    name: str  # e.g. "link_account_customer"
    connected_hubs: list[str]  # hub names this link connects (>= 2)
    description: str
    # Discriminator the code generator dispatches on (standard -> automate_dv.link,
    # transactional -> automate_dv.nh_link, the non-historized link).
    link_type: Literal["standard", "transactional"] = "standard"
    # Hub reference(s) that stay fixed while the others rotate over time (the "one at a
    # time" side of a relationship). A non-empty subset of connected_hubs; required when an
    # effectivity satellite hangs off this link so it can end-date per driving key.
    driving_key: list[str] = Field(default_factory=list)
    # Optional: the modeler's rationale for the link's Unit of Work — which business keys
    # form the one atomic event this link captures. Surfaced in the ADR trail, not enforced.
    unit_of_work: str | None = None
    # For a transactional link only: the transaction's data columns (automate_dv.nh_link's
    # src_payload) and the event-date column used as src_eff. event_timestamp is required to
    # generate a nh_link.
    payload: list[str] = Field(default_factory=list)
    event_timestamp: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)


class Satellite(BaseModel):
    """A Data Vault satellite: descriptive attributes hanging off one parent."""
    name: str  # e.g. "sat_customer_details"
    parent: str  # the hub or link name this satellite describes
    attributes: list[str] = Field(default_factory=list)  # descriptive payload columns
    description: str
    # Discriminator the code generator dispatches on (standard -> automate_dv.sat,
    # multi_active -> automate_dv.ma_sat, effectivity -> automate_dv.eff_sat).
    sat_type: Literal["standard", "multi_active", "effectivity"] = "standard"
    # Child dependent key(s) that distinguish concurrently-active rows of a multi-active
    # satellite (automate_dv.ma_sat's src_cdk). Required to generate a ma_sat.
    child_dependent_key: list[str] = Field(default_factory=list)
    # Optional: why this satellite's attributes are grouped/split as they are (rate of
    # change, source, classification). Surfaced in the ADR trail, not enforced.
    split_rationale: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)


class DVModel(BaseModel):
    hubs: list[Hub] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    satellites: list[Satellite] = Field(default_factory=list)


class Artifacts(BaseModel):
    automatedv_yaml: dict[str, Any] = Field(default_factory=dict)
    dbt_models: dict[str, str] = Field(default_factory=dict)
    # One JSON-Schema-based data contract per source-to-staging asset (ADR-0005), each a
    # plain JSON/YAML-round-trippable dict (DataContract.to_dict()).
    contracts: list[dict[str, Any]] = Field(default_factory=list)
    # dbt schema-test YAML derived from the contracts, keyed by asset name (one properties
    # file per asset). Prevention runs inside the existing dbt pipeline.
    dbt_tests: dict[str, str] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    passed: bool = False
    issues: list[dict[str, Any]] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    """The orchestrator's record of what a run will execute (audit + observability).

    Deterministic: the orchestrator writes it as the entry node so the trace shows the
    planned stages, declared inputs, and whether source-schema grounding is active."""
    stages: list[str] = Field(default_factory=list)  # node ids planned after planning
    input_documents: int = 0
    grounded: bool = False
    notes: list[str] = Field(default_factory=list)  # planning observations, e.g. missing inputs


class VaultAgentState(BaseModel):
    """Single state object shared across all agents in the graph."""
    # Inputs
    input_documents: list[str] = Field(default_factory=list)
    # Optional source-column metadata for grounding (ADR-0004); empty = no grounding.
    source_schemas: list[SourceTable] = Field(default_factory=list)
    # Working state
    requirements: list[ParsedRequirement] = Field(default_factory=list)
    business_keys: list[BusinessKeyCandidate] = Field(default_factory=list)
    dv_model: DVModel = Field(default_factory=DVModel)
    artifacts: Artifacts = Field(default_factory=Artifacts)
    validation_report: ValidationReport = Field(default_factory=ValidationReport)
    # The orchestrator's execution plan, written by the entry node (None until it runs).
    plan: ExecutionPlan | None = None
    adrs: list[str] = Field(default_factory=list)
    # Loop control: how many times the modeler has run. The validation retry guard reads
    # this directly so control flow is decoupled from the audit log (decisions).
    modeling_attempts: int = 0
    # Audit
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
