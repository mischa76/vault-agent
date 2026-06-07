"""Shared state passed through the LangGraph nodes."""
from typing import Any

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


class DVModel(BaseModel):
    hubs: list[dict[str, Any]] = Field(default_factory=list)
    links: list[dict[str, Any]] = Field(default_factory=list)
    satellites: list[dict[str, Any]] = Field(default_factory=list)


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
