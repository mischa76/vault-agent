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
    # transactional -> automate_dv.t_link).
    link_type: Literal["standard", "transactional"] = "standard"
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
    requirement_ids: list[str] = Field(default_factory=list)


class DVModel(BaseModel):
    hubs: list[Hub] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    satellites: list[Satellite] = Field(default_factory=list)


class Artifacts(BaseModel):
    automatedv_yaml: dict[str, Any] = Field(default_factory=dict)
    dbt_models: dict[str, str] = Field(default_factory=dict)
    contracts: list[dict[str, Any]] = Field(default_factory=list)


class ValidationReport(BaseModel):
    passed: bool = False
    issues: list[dict[str, Any]] = Field(default_factory=list)


class VaultAgentState(BaseModel):
    """Single state object shared across all agents in the graph."""
    # Inputs
    input_documents: list[str] = Field(default_factory=list)
    source_schemas: list[str] = Field(default_factory=list)
    # Working state
    requirements: list[ParsedRequirement] = Field(default_factory=list)
    business_keys: list[BusinessKeyCandidate] = Field(default_factory=list)
    dv_model: DVModel = Field(default_factory=DVModel)
    artifacts: Artifacts = Field(default_factory=Artifacts)
    validation_report: ValidationReport = Field(default_factory=ValidationReport)
    adrs: list[str] = Field(default_factory=list)
    # Audit
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
