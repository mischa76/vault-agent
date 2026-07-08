"""Shared state passed through the LangGraph nodes."""
import warnings
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FlagSeverity = Literal["error", "advisory"]


class FlagKind:
    """Stable, machine-readable categories for :class:`PipelineFlag`.

    Consumers (review queue, HITL pruning, aggregation) branch on these — never on the
    flag's human-readable message text."""

    MISSING_INPUT = "missing_input"  # a stage ran without its required upstream output
    DROPPED_RECORD = "dropped_record"  # an invalid LLM record was dropped, not guessed at
    COLUMN_COLLISION = "column_collision"  # two labels normalise to the same identifier
    GENERATION_GAP = "generation_gap"  # a construct could not be generated; human review
    OWNER_PLACEHOLDER = "owner_placeholder"  # contract awaiting a real owner (blocking)
    UNDETERMINED_TYPE = "undetermined_type"  # contract field type unknown; review required
    NO_SOURCE_SCHEMA = "no_source_schema"  # contract inferred from prose, not a schema
    SOURCE_BINDING = "source_binding"  # staging source relation inferred, not declared
    INPUT_TRUNCATED = "input_truncated"  # oversized input document cut to the size guard
    GENERIC = "generic"


class PipelineFlag(BaseModel):
    """One typed flag raised by an agent for the audit trail / human review queue.

    Replaces the former free-text ``state.errors`` strings: consumers match on ``kind``
    and ``asset`` (exact), so rewording a message can never break classification,
    de-duplication, or HITL pruning."""

    agent: str  # the raising agent, e.g. "data_contract"
    message: str  # human-readable description (presentation only — never parsed)
    severity: FlagSeverity = "advisory"
    kind: str = FlagKind.GENERIC
    # The affected asset/construct (contract name, satellite name, "contract.field", …).
    # Exact-match key for consumers, e.g. pruning resolved owner flags on resume.
    asset: str | None = None

    def __str__(self) -> str:
        return f"{self.agent}: {self.message}"


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
    business-key prompts are steered toward these real columns.

    ``schema_name`` / ``database`` (WP7 §7.2) locate the table physically; when
    declared, grounded runs bind the matching staging model through a real dbt
    ``source()`` mapping instead of a bare relation name. ``schema_name`` is aliased to
    ``schema`` in input files (the natural key there) because ``schema`` collides with a
    ``BaseModel`` attribute."""

    model_config = ConfigDict(populate_by_name=True)

    table: str  # the source table / entity name
    columns: list[str] = Field(default_factory=list)  # its column names, as in the source
    schema_name: str | None = Field(default=None, alias="schema")
    database: str | None = None


class Hub(BaseModel):
    """A Data Vault hub: one business concept, anchored on its business key."""
    name: str  # e.g. "hub_customer"
    business_key: str  # the natural key field this hub is built on
    source_entity: str  # the business object, e.g. "customer"
    description: str
    requirement_ids: list[str] = Field(default_factory=list)


class LinkHubRef(BaseModel):
    """One hub participation in a link, optionally role-qualified (ADR-0009).

    A plain hub name in ``Link.connected_hubs`` coerces to ``LinkHubRef(hub=<name>)``
    (unqualified, ``role=None``). A role qualifier disambiguates one hub participating
    twice in different roles — e.g. ``hub_account`` as the unqualified payer side and as
    the ``counterparty`` side of a transfer — so the generator can render distinct
    role-prefixed FK columns (``ACCOUNT_HK`` vs ``COUNTERPARTY_ACCOUNT_HK``, via
    :func:`rules.dv2_rules.role_fk_column`). Unqualified refs render byte-identically to
    the pre-ADR-0009 plain-string behaviour."""

    hub: str  # hub name, e.g. "hub_account"
    role: str | None = None  # e.g. "counterparty"; None = unqualified

    def __str__(self) -> str:
        return self.hub if self.role is None else f"{self.hub}:{self.role}"


class Link(BaseModel):
    """A Data Vault link: a relationship connecting two or more hubs."""
    name: str  # e.g. "link_account_customer"
    # Hub participations (>= 2). A plain string is a hub name (unqualified); a LinkHubRef
    # (or ``{"hub": ..., "role": ...}`` dict) role-qualifies a participation so one hub can
    # take part more than once (ADR-0009). The union keeps plain-string YAML/tool-schema
    # inputs working; the before-validator normalises every entry to LinkHubRef so
    # downstream code sees one shape — read it through ``hub_refs``.
    connected_hubs: list[str | LinkHubRef]
    description: str
    # Discriminator the code generator dispatches on (standard -> automate_dv.link,
    # transactional -> automate_dv.t_link, the non-historized/transactional link).
    link_type: Literal["standard", "transactional"] = "standard"
    # Hub reference(s) that stay fixed while the others rotate over time (the "one at a
    # time" side of a relationship). Each entry names a connected participation — a bare
    # hub name, or "hub:role" for a role-qualified one (ADR-0009); resolve via
    # resolve_driving_refs(). Required when an effectivity satellite hangs off this link so
    # it can end-date per driving key.
    driving_key: list[str] = Field(default_factory=list)
    # Optional: the modeler's rationale for the link's Unit of Work — which business keys
    # form the one atomic event this link captures. Surfaced in the ADR trail, not enforced.
    unit_of_work: str | None = None
    # For a transactional link only: the transaction's data columns (automate_dv.t_link's
    # src_payload) and the event-date column used as src_eff. event_timestamp is required to
    # generate a t_link.
    payload: list[str] = Field(default_factory=list)
    event_timestamp: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)

    @field_validator("connected_hubs", mode="before")
    @classmethod
    def _normalise_hub_refs(cls, value: Any) -> Any:
        """Coerce every entry to a LinkHubRef so downstream code sees one shape (ADR-0009).

        Plain strings become unqualified refs; dicts/LinkHubRefs pass through to pydantic.
        Runs on construction/validation; direct field assignment bypasses it, which is why
        :attr:`hub_refs` re-coerces defensively."""
        if isinstance(value, list):
            return [LinkHubRef(hub=v) if isinstance(v, str) else v for v in value]
        return value

    @property
    def hub_refs(self) -> list[LinkHubRef]:
        """``connected_hubs`` as normalised :class:`LinkHubRef`s — the single read path.

        The before-validator already normalises validated input; this re-coerces any plain
        string (e.g. from a post-construction field assignment that skips validation) so
        every consumer can rely on ``.hub`` / ``.role`` without a union check."""
        return [LinkHubRef(hub=h) if isinstance(h, str) else h for h in self.connected_hubs]

    def resolve_driving_refs(self) -> list["LinkHubRef"]:
        """Resolve ``driving_key`` entries to the connected refs they name (ADR-0009).

        An entry is a bare hub name (matches the unqualified connected ref) or ``"hub:role"``
        (matches the role-qualified one). This is the single interpretation point for the
        driving key; unmatched entries are dropped here and reported by the validator's
        ``E_DRIVING_KEY_NOT_IN_LINK`` gate."""
        refs = self.hub_refs
        resolved: list[LinkHubRef] = []
        for entry in self.driving_key:
            hub, sep, role = entry.partition(":")
            wanted = (hub, role if sep else None)
            for ref in refs:
                if (ref.hub, ref.role) == wanted:
                    resolved.append(ref)
                    break
        return resolved


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
    # The raw relation this satellite's rows come from, when it differs from its parent's
    # (WP7 §7.1): multi-active payloads usually live in their own finer-grain source
    # table. When set, the staging generator emits a dedicated stg_<sat base> model bound
    # to it VERBATIM (declared — never inferred, never flagged) and the satellite reads
    # that staging model. The parent's business-key column(s) must exist in this relation
    # — that is what makes the rows attachable to the parent's hash key. Ignored for
    # effectivity satellites (their date pair lives in the relationship's own relation).
    source_table: str | None = None
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
    # Generated AutomateDV staging models (stg_* -> SQL), kept separate from the raw-vault
    # dbt_models so each layer can be written/tested/asserted independently.
    staging_models: dict[str, str] = Field(default_factory=dict)
    # dbt project scaffolding (relative path -> content): dbt_project.yml, packages.yml,
    # models/staging/sources.yml, README.md — what makes the output a runnable project.
    scaffolding: dict[str, str] = Field(default_factory=dict)


IssueSeverity = Literal["error", "warning"]


# The DV term of art is "construct" (hub/link/satellite); pydantic warns because it
# shadows the *deprecated* classmethod ``BaseModel.construct`` (v1 alias of
# ``model_construct``), which this project never calls. Suppress that one definition-time
# warning rather than bending the domain vocabulary.
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message='Field name "construct" in "ValidationIssue"')

    class ValidationIssue(BaseModel):
        """A single validator finding, keyed by a stable machine code.

        Consumers branch on ``severity``/``code``/``construct``; ``message`` is
        human-readable presentation only and is never parsed."""
        severity: IssueSeverity
        code: str  # stable machine code, e.g. "E_NO_HUBS" / "W_SAT_WIDE"
        # The construct (or comma-joined constructs) concerned. The ignore matches the
        # runtime suppression above: the shadowed classmethod is deprecated and unused.
        construct: str  # type: ignore[assignment]
        message: str  # human-readable; presentation only, never parsed


class ValidationReport(BaseModel):
    passed: bool = False
    issues: list[ValidationIssue] = Field(default_factory=list)


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
    # Typed advisory/error flags raised by the agents (dropped records, generation gaps,
    # contract review items, …). Consumers branch on kind/asset, never on message text.
    flags: list[PipelineFlag] = Field(default_factory=list)

    def flag(
        self,
        agent: str,
        message: str,
        *,
        severity: FlagSeverity = "advisory",
        kind: str = FlagKind.GENERIC,
        asset: str | None = None,
    ) -> None:
        """Raise a typed pipeline flag (convenience helper for the agents)."""
        self.flags.append(
            PipelineFlag(
                agent=agent, message=message, severity=severity, kind=kind, asset=asset
            )
        )
