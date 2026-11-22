"""Data-contract domain model (ADR-0005).

A JSON-Schema-based contract spec for each source-to-staging data asset, per Sanderson,
Freeman & Schmidt, *Data Contracts* (O'Reilly, 2025). JSON ↔ YAML is 1:1, so a contract
serialises losslessly either way (``model_dump(by_alias=True)`` → plain dict).

Structure mirrors the book's spec: a *contract-management* header (name / namespace /
owner / doc), a required *schema* block of typed fields, and an optional *semantics* block
of value-level constraints. Every constraint carries a **hard** vs **soft** failure mode so
the dbt / CI layer knows whether a violation blocks or merely alerts.

These types are pure data: the :class:`~vault_agent.agents.data_contract.DataContractAgent`
assembles and validates them. Keeping the spec as our own pydantic model (rather than an
external standard) keeps it transparent and the serializer swappable — see ADR-0005.
"""
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

# The JSON Schema base types the book maps source types onto. ``"unknown"`` is our explicit
# "could not be determined — flag for human review" marker (never guess a narrow type).
JsonSchemaType = Literal[
    "string", "number", "integer", "object", "array", "boolean", "null", "unknown"
]
# A field's type is one base type, or a union (e.g. ``["null", "string"]`` for an optional).
DataType = JsonSchemaType | list[JsonSchemaType]

# A violation either blocks the pipeline (hard) or only raises an alert (soft). Schema /
# primary-key / not-null breaches default to hard; semantic thresholds default to soft.
FailureMode = Literal["hard", "soft"]


class ContractOwner(BaseModel):
    """Accountable party for the asset. The agent never invents a real owner — when it
    cannot infer one it emits the placeholder ``{"name": "TODO: assign", "email": null}``
    and flags the contract for human assignment."""

    # Single source of truth for the "no owner yet" marker, reused by the orchestrator's
    # review queue to spot contracts still awaiting a human owner assignment.
    PLACEHOLDER_NAME: ClassVar[str] = "TODO: assign"

    name: str
    email: str | None = None

    @classmethod
    def placeholder(cls) -> "ContractOwner":
        return cls(name=cls.PLACEHOLDER_NAME, email=None)

    @property
    def is_placeholder(self) -> bool:
        return self.name == self.PLACEHOLDER_NAME


class SemanticConstraint(BaseModel):
    """One value-level constraint (opt-in depth), e.g. ``charLength``, ``min``, ``max``,
    ``pattern``, ``isNotEmpty``, ``isNullThreshold``. Generated only when grounded in a
    stated requirement — never fabricated. Soft by default (alerts, does not block)."""

    kind: str
    value: str | int | float | bool | None = None
    failure_mode: FailureMode = "soft"


class FieldConstraints(BaseModel):
    """Schema-level constraints for one field — the default deliverable of the contract."""

    primaryKey: bool = False  # noqa: N815 - the book's spec key; emitted verbatim
    data_type: DataType = "unknown"
    # Constrained value set (the book's enum types); empty = unconstrained.
    enum: list[str] = Field(default_factory=list)
    is_nullable: bool = True
    is_updatable: bool = True
    precision: int | None = None


class ContractField(BaseModel):
    """One field of the data asset: its description, examples, schema constraints, and any
    value-level semantics. ``failure_mode`` covers the schema-level constraints
    (type / primary-key / nullability); semantic constraints carry their own."""

    name: str
    description: str = ""
    examples: list[str] = Field(default_factory=list)
    constraints: FieldConstraints = Field(default_factory=FieldConstraints)
    semantics: list[SemanticConstraint] = Field(default_factory=list)
    failure_mode: FailureMode = "hard"


class DataContract(BaseModel):
    """A draft data contract for one source-to-staging asset.

    ``spec_version`` serialises as ``spec-version`` (the book's hyphenated key); pydantic's
    alias handles the JSON/YAML form while keeping a valid Python identifier. ``fields``
    serialises as ``schema`` — the contract's required schema block."""

    model_config = ConfigDict(populate_by_name=True)

    spec_version: str = Field(default="1.0.0", alias="spec-version")
    name: str
    namespace: str
    dataAssetResourceName: str  # noqa: N815 - the book's spec key; emitted verbatim
    doc: str = ""
    owner: ContractOwner = Field(default_factory=ContractOwner.placeholder)
    fields: list[ContractField] = Field(default_factory=list, alias="schema")

    def to_dict(self) -> dict[str, object]:
        """Serialise to a plain, JSON/YAML-round-trippable dict (book's hyphenated keys)."""
        return self.model_dump(by_alias=True)
