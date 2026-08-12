"""Shared state passed through the LangGraph nodes."""
import warnings
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    INPUT_SEGMENTED = "input_segmented"  # document extracted over several bounded calls
    MAPPING_GAP = "mapping_gap"  # concept has no in-scope source (WP9; belongs downstream)
    MAPPING_UNRESOLVED = "mapping_unresolved"  # concept's source undecided; human ratifies
    # WP23 brownfield: the extension delta asks for something that is not an extension
    # (an existing hub's key changed, an existing link/satellite re-stated). Never
    # applied — flagged, and the additive gates fail the run.
    EXTENSION_CONFLICT = "extension_conflict"
    # WP29 brownfield Phase 2: the entity resolver's two human-facing outcomes. Neither
    # blocks sign-off — an unresolved concept is honest output, as a mapping gap is.
    RESOLUTION_UNRESOLVED = "resolution_unresolved"  # is this an existing construct? undecided
    RESOLUTION_SAME_AS = "resolution_same_as"  # asserted equivalent, differently keyed
    # WP34: a declared foreign key the link proposer would not answer for — a composite key,
    # or a referenced column several hubs share. Advisory: an unproposed link is an
    # incomplete model, which is what this pass exists to reduce, not a broken one.
    LINK_PROPOSAL_SKIPPED = "link_proposal_skipped"
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


class SourceColumn(BaseModel):
    """One declared source column, optionally carrying its type and documentation (WP9 §3.1).

    The richer form ADR-0008 precondition (c) wants — ``type`` and a source ``comment`` —
    which the business↔source mapper reads to establish *intent* (a column named ``KD_NR``
    whose comment says "branch code" is not a customer number). Both are optional: a bare
    column name (the ADR-0004 shape) coerces to ``SourceColumn(name=...)`` with empty
    type/comment, so pre-WP9 schemas stay byte-for-byte inert."""

    name: str
    type: str = ""
    comment: str | None = None


class ForeignKeyRef(BaseModel):
    """One declared foreign key of a source table (WP34 §3.1).

    Optional input, like ``ColumnProfile``: transcribed from the source catalogue, never
    inferred by this pipeline and never derived from data. It exists because the evidence a
    cross-domain link needs was measurably absent — WP30.1-30.3 spent ~$46 asking the modeler
    to relate a new increment to a prior vault while the foreign keys stating those relations
    were being dropped by the schema derivation (``eval/adventureworks/derive.py``) before any
    agent could see them.

    Read by the deterministic link proposer and by nothing else. It is deliberately NOT
    rendered into the modeler's prompt (§3.8): showing it would change a one-pass run's input
    as well, and the arm comparison would then measure a changed input and a new mechanism at
    once — pinned by ``tests/test_wp34_fk_inertness.py``.

    ``columns`` and ``references_columns`` are parallel: same order, same arity."""

    columns: list[str]
    references_table: str
    references_columns: list[str]
    references_schema: str | None = None

    @model_validator(mode="after")
    def _check_arity(self) -> "ForeignKeyRef":
        """A mismatched pair is malformed input, not something to guess a pairing for."""
        if len(self.columns) != len(self.references_columns):
            raise ValueError(
                f"foreign key on {self.references_table!r} pairs {len(self.columns)} "
                f"column(s) with {len(self.references_columns)} referenced column(s); "
                "they must be parallel"
            )
        if not self.columns:
            raise ValueError("a foreign key must name at least one column")
        return self

    @property
    def is_single_column(self) -> bool:
        """WP34 §3.2 condition 2: composite keys are flagged, never guessed at."""
        return len(self.columns) == 1


class SourceTable(BaseModel):
    """A declared source table the model can be grounded against (ADR-0004).

    Optional input: when ``VaultAgentState.source_schemas`` is non-empty the validator
    flags business keys / attributes that match no declared column, and the modeler and
    business-key prompts are steered toward these real columns.

    ``columns`` accepts a bare name (``list[str]``, the ADR-0004 shape) or the enriched
    ``{name, type, comment}`` form (WP9 §3.1); a before-validator normalises every entry to
    :class:`SourceColumn`, and grounding/staging read the plain names through
    :attr:`column_names` so bare-string inputs stay byte-identical.

    ``schema_name`` / ``database`` (WP7 §7.2) locate the table physically; when
    declared, grounded runs bind the matching staging model through a real dbt
    ``source()`` mapping instead of a bare relation name. ``schema_name`` is aliased to
    ``schema`` in input files (the natural key there) because ``schema`` collides with a
    ``BaseModel`` attribute."""

    model_config = ConfigDict(populate_by_name=True)

    table: str  # the source table / entity name
    # Column definitions, as in the source. Union keeps bare-string YAML working; the
    # before-validator normalises to SourceColumn so downstream sees one shape.
    columns: list[str | SourceColumn] = Field(default_factory=list)
    schema_name: str | None = Field(default=None, alias="schema")
    database: str | None = None
    # WP34 §3.1: declared foreign keys, transcribed from the source catalogue. Empty = the
    # pre-WP34 shape, and every artifact stays byte-identical (test_wp34_fk_inertness.py).
    # Read ONLY by the deterministic link proposer — never rendered to the modeler (§3.8).
    foreign_keys: list[ForeignKeyRef] = Field(default_factory=list)

    @field_validator("columns", mode="before")
    @classmethod
    def _normalise_columns(cls, value: Any) -> Any:
        """Coerce every entry to a SourceColumn (WP9 §3.1; mirrors the WP8 LinkHubRef union).

        Plain strings become bare ``SourceColumn(name=...)``; dicts/SourceColumns pass
        through. Field assignment bypasses this, which is why :attr:`column_names` re-coerces
        defensively."""
        if isinstance(value, list):
            return [SourceColumn(name=v) if isinstance(v, str) else v for v in value]
        return value

    @property
    def column_names(self) -> list[str]:
        """The plain column names — the single read path for grounding/staging (WP9 §3.1)."""
        return [c.name if isinstance(c, SourceColumn) else c for c in self.columns]

    @property
    def column_refs(self) -> list[SourceColumn]:
        """``columns`` as normalised :class:`SourceColumn`s (re-coerces post-assignment)."""
        return [SourceColumn(name=c) if isinstance(c, str) else c for c in self.columns]


class ColumnProfile(BaseModel):
    """Per-column profiling statistics (WP9 §3.2 / ADR-0008 #4).

    A pre-step *input* artifact — produced ahead of time from a sanitised extract or a
    metadata export, never by the pipeline logging into a live source. The mapper uses it
    as BK-plausibility and post-validation evidence, never as the primary intent signal
    (the spike found comments/names carry intent; statistics establish structure, not
    intent)."""

    name: str
    uniqueness_ratio: float = 0.0
    null_ratio: float = 0.0
    distinct_count: int = 0
    example_values: list[str] = Field(default_factory=list)


# The evidence-derived confidence tier (WP9 §7): a deterministic category the review queue
# sorts/flags by, more robust than a raw self-reported confidence number across models.
MappingCategory = Literal[
    "exact_name", "comment_grounded", "profiled_key", "llm_semantic", "unresolved"
]
# Ratification lifecycle of one proposal (WP9 §5); a human accepts/overrides at the HITL.
RatificationStatus = Literal["proposed", "accepted", "overridden"]


CONCEPT_KEY_SEPARATOR = "::"


def concept_key(concept: str, entity: str | None) -> str:
    """The identity of a business concept in the mapping layer: (label, entity) (WP32).

    The label ALONE is not an identity — three reference hubs can each be keyed ``Name`` — and
    treating it as one made the mapper ask about the label once and then apply that one answer
    to every hub carrying it, binding staging models to the wrong relation (WP30 §7.3
    Finding 1, a wrong-DATA defect). Every site that identifies a concept — the mapper's
    work-list and lookup, the staging re-bind, the ratification file and ``--map`` — imports
    this; none re-derives it.

    ``::`` deliberately, not ``.``: a key must never be confusable with the ``TABLE.COLUMN``
    syntax the ratification file and ``--map`` already use. An entity-less concept keeps the
    bare label, so a single-source vault's keys are byte-identical to pre-WP32."""
    return f"{entity}{CONCEPT_KEY_SEPARATOR}{concept}" if entity else concept


def concept_ref_matches(
    ref: str, concept: str, entity: str | None, *, label_unique: bool
) -> bool:
    """Does ``ref`` refer to the concept ``(concept, entity)``? (WP32)

    ONE matching rule, used everywhere a stored or human-typed reference has to be resolved:
    **the key matches exactly, or the label matches and is unique in its universe.** The
    label fallback is what keeps a human's ``--map "customer name=T.C"``, an edited review
    file, and a checkpoint written before WP32 (whose lists hold bare labels) all working; the
    uniqueness condition is what stops it from reinstating the defect, where one reference
    resolved to several concepts at once.

    ``label_unique`` is the caller's, because uniqueness is a property of the universe being
    searched (a run's proposals, or a model's hubs), not of the pair."""
    from vault_agent.rules.dv2_rules import normalize_identifier

    if normalize_identifier(ref) == normalize_identifier(concept_key(concept, entity)):
        return True
    ref_label, ref_entity = split_concept_key(ref)
    if not label_unique or normalize_identifier(ref_label) != normalize_identifier(concept):
        return False
    # Both sides naming an entity, and naming DIFFERENT ones, is a contradiction the label
    # must not paper over: `AddressType::Name` never refers to ContactType's `Name`. The
    # fallback exists for the mixed case — one side simply does not carry an entity.
    return ref_entity is None or entity is None


def match_concept_refs(
    ref: str, candidates: Sequence[tuple[str, str | None]]
) -> list[int]:
    """Every candidate index ``ref`` could name (WP32) — exact key match, else label matches.

    Returning the full list rather than one index is what lets callers tell **ambiguous**
    (several matches: refuse to choose) from **unknown** (none: a concept the human is adding).
    Collapsing those two into one "not found" answer would either drop a legitimate addition or
    pick arbitrarily among siblings, and picking arbitrarily is the WP32 defect."""
    from vault_agent.rules.dv2_rules import normalize_identifier

    exact = [
        i
        for i, (concept, entity) in enumerate(candidates)
        if normalize_identifier(ref) == normalize_identifier(concept_key(concept, entity))
    ]
    if exact:
        return exact
    ref_label, ref_entity = split_concept_key(ref)
    label = normalize_identifier(ref_label)
    return [
        i
        for i, (concept, entity) in enumerate(candidates)
        if normalize_identifier(concept) == label
        and (ref_entity is None or entity is None)
    ]


def resolve_concept_ref(
    ref: str, candidates: Sequence[tuple[str, str | None]]
) -> int | None:
    """Index of the single concept ``ref`` names, else None (ambiguous or absent) — WP32.

    Symmetric by design: it resolves a human's bare label against qualified candidates AND a
    qualified key against candidates that carry no entity (a promoted human override), because
    both directions occur and both must land on the same concept."""
    matches = match_concept_refs(ref, candidates)
    return matches[0] if len(matches) == 1 else None


def split_concept_key(key: str) -> tuple[str, str | None]:
    """Inverse of :func:`concept_key`: ``(label, entity)``; entity None for a bare label.

    Used where a human hands back a key — ``resume --map``, an edited ``mappings.review.yml`` —
    so a promoted proposal records the entity it belongs to instead of losing it. Splits on the
    FIRST separator, since an entity name cannot contain it while a label conceivably could."""
    entity, sep, label = key.partition(CONCEPT_KEY_SEPARATOR)
    return (label, entity) if sep else (key, None)


class Proposal(BaseModel):
    """One proposed ``concept → (table, column)`` mapping with its evidence trail (WP9).

    ``confidence`` (0..1) and ``evidence`` are the ADR-0008 assist-quality machinery — the
    ratifying human sees *why* a column was proposed. ``category`` is the deterministic
    confidence tier (§7); ``ratification_status`` tracks the HITL decision (§5)."""

    concept: str
    table: str
    column: str
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    entity: str | None = None
    category: MappingCategory = "llm_semantic"
    ratification_status: RatificationStatus = "proposed"

    @property
    def key(self) -> str:
        """This proposal's concept identity (WP32) — never the bare label."""
        return concept_key(self.concept, self.entity)


class ProposedMapping(BaseModel):
    """The mapper's full answer for one run: resolved proposals plus honest non-answers.

    ``gaps`` are concepts with no in-scope source (ADR-0008 #3, a first-class output);
    ``unresolved`` are concepts the mapper could not decide (incl. multi-candidate keys held
    for WP10) — distinct from a gap, and the honest degraded-mode behaviour."""

    proposals: list[Proposal] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


# Brownfield Phase 2 (WP29): what an entity resolution can say about one concept the new
# source introduces. A construct NAME means "this IS that construct" — the only answer that
# writes foreign keys into a table holding history, and therefore the one the spike's
# zero-false-merge requirement is about. The three reserved words are the safe answers.
RESOLUTION_NEW = "NEW"
RESOLUTION_SAME_AS = "same_as_candidate"
RESOLUTION_UNRESOLVED = "unresolved"
RESOLUTION_CLASSES = (RESOLUTION_NEW, RESOLUTION_SAME_AS, RESOLUTION_UNRESOLVED)

# Deterministic confidence tier, DERIVED from the evidence — never the model's own claim.
# Measured reason (spike memo §3.3): the resolver reported "semantic" for every case,
# including the exact-key ones where its answer was right.
ResolutionCategory = Literal["exact_key", "key_overlap", "comment_grounded", "semantic"]


class ResolutionProposal(BaseModel):
    """One proposed answer to "is this new concept an existing construct?" (WP29).

    ``resolution`` is an existing construct's name, or one of :data:`RESOLUTION_CLASSES`.
    ``same_as`` names the construct a ``same_as_candidate`` corresponds to: asserted
    equivalence on a DIFFERENT key produces two constructs plus this flag, never a merge
    (brownfield charter §3.5, measured reliable in the Phase 2 spike)."""

    concept: str
    resolution: str
    same_as: str | None = None
    confidence: float = 0.0
    category: ResolutionCategory = "semantic"
    evidence: list[str] = Field(default_factory=list)
    ratification_status: RatificationStatus = "proposed"

    @property
    def is_merge(self) -> bool:
        """True when this claims the concept IS an existing construct — the unsafe direction."""
        return self.resolution not in RESOLUTION_CLASSES


class EntityResolution(BaseModel):
    """The resolver's full answer for one extension run; empty on greenfield/ungrounded."""

    proposals: list[ResolutionProposal] = Field(default_factory=list)

    def by_concept(self) -> dict[str, ResolutionProposal]:
        return {p.concept: p for p in self.proposals}


# WP34: the deterministic tier of a link proposal, DERIVED from the declared foreign key and
# never claimed by anything. Only two tiers can occur, because the proposer reads DECLARED
# foreign keys and nothing else — see `link_proposal.propose_links` for why the spec's third
# illustrative tier (`key_name_only`) is deliberately not implemented.
LinkProposalCategory = Literal["declared_fk_same_name", "declared_fk_renamed"]

# Why the proposer declined to answer for a declared foreign key. A CODE, not the sentence:
# the 2026-08-12 run left 10 of 11 viable cross-schema foreign keys unaccounted for, and the
# only record of each decision was a human-readable flag message — which nothing may branch
# on and no analysis could count. Each member is one branch of `link_proposal._target_hub`
# or of the composite-key condition above it.
LinkSkipReason = Literal[
    "composite_key",  # several columns; which pairs with which hub key is a modelling call
    "no_hub_for_key",  # no existing hub is keyed on the referenced column
    "ambiguous_hub",  # several hubs share that key and the referenced table breaks no tie
]


class LinkSkip(BaseModel):
    """One declared foreign key the proposer left alone, and why — typed, then phrased.

    A skip is honest output, not a defect (WP34 §3.2). It is recorded so the *distribution* of
    skips is countable: "the mechanism is shy" and "the vault is keyed differently than the
    source references it" are different diagnoses that produce identical link counts, and
    telling them apart is what this exists for."""

    asset: str  # "Table.column" — the same handle the flag carries
    reason: LinkSkipReason
    message: str  # human-readable; presentation only, never parsed


class LinkProposal(BaseModel):
    """One link the source's own catalogue says exists (WP34 §3.2).

    Proposed BEFORE the modeler runs and applied only once ratified, mirroring
    :class:`ResolutionProposal`: a link writes join keys into a table holding history, so the
    unsafe direction is the same one and gets the same treatment — propose, pause, ratify.

    ``source_column`` is the referencing table's own name for the key; ``target_business_key``
    is the hub's canonical one. When they differ the staging layer must ALIAS the first to the
    second before hashing, which is what :attr:`LinkHubRef.source_key_column` carries and what
    ``E_LINK_KEY_NOT_IN_SOURCE`` refuses to let go wrong."""

    source_table: str
    source_column: str
    target_hub: str
    target_business_key: str
    category: LinkProposalCategory
    evidence: list[str] = Field(default_factory=list)
    ratification_status: RatificationStatus = "proposed"

    @property
    def needs_alias(self) -> bool:
        """True when the referencing column is named differently from the hub's key."""
        return self.category == "declared_fk_renamed"


class LinkProposals(BaseModel):
    """The proposer's full answer for one run; empty on greenfield and ungrounded runs.

    ``skipped`` is part of the answer, not exhaust: a foreign key the pass declined is a
    relationship the model will not carry, and a run that proposes nothing looks identical to
    a run that was never given foreign keys unless the declines are on the record."""

    proposals: list[LinkProposal] = Field(default_factory=list)
    skipped: list[LinkSkip] = Field(default_factory=list)

    def ratified(self) -> list[LinkProposal]:
        """Only these may become links — the WP29 rule applied to relationships.

        ``accepted`` ONLY, deliberately not "anything already decided". A resolution's
        ``overridden`` carries a human's different *answer*, which still steers; a link's
        ``overridden`` is a refusal, and there is nothing to build. Written the other way
        first, and a test caught it building the very link a human had just declined."""
        return [p for p in self.proposals if p.ratification_status == "accepted"]


class HubSource(BaseModel):
    """One source feeding a multi-source hub (WP10): the physical key column in that source.

    ``business_key_column`` is the source's own name for the hub's business key (they differ
    across systems — ``partner_id`` in one, ``customer_id`` in another). Staging aliases it to
    the canonical name before hashing so the same key value hashes identically everywhere (the
    hub's integration property)."""

    source_table: str
    business_key_column: str


class Hub(BaseModel):
    """A Data Vault hub: one business concept, anchored on its business key."""
    name: str  # e.g. "hub_customer"
    business_key: str  # the natural key field this hub is built on
    source_entity: str  # the business object, e.g. "customer"
    description: str
    # WP10: when a business key lives in several sources, one HubSource per feed (the physical
    # key column in each). Empty = single-source, today's behaviour (byte-identity guard). The
    # canonical staging key name is computed once in rules.canonical_hub_key_column().
    sources: list[HubSource] = Field(default_factory=list)
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
    # WP34 §3.4: this participation's own physical name for the hub's key, when the relation
    # feeding the link calls it something else (Sales.Customer.PersonID for a hub keyed on
    # BusinessEntityID). Staging ALIASES it to the canonical name before hashing, exactly as
    # HubSource.business_key_column does for a multi-source hub's feed — without which the
    # staging model would demand a column the relation does not have, and the link would
    # either fail to build or join on a same-named column meaning something else.
    # None = today's behaviour and today's bytes. E_LINK_KEY_NOT_IN_SOURCE gates it.
    source_key_column: str | None = None

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
    # WP23 §2.7: the computed extension diff (unchanged/extended/changed_files/new) on a
    # brownfield run; empty on greenfield. Plain dict so it round-trips the checkpointer,
    # and so the Markdown artifact and the HTML report render the SAME data.
    extension_diff: dict[str, Any] = Field(default_factory=dict)
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
    # WP23: this run extends an existing vault (`--existing`) rather than modelling into
    # an empty target. Observability only — the behaviour hangs off state.existing_model.
    extending: bool = False
    notes: list[str] = Field(default_factory=list)  # planning observations, e.g. missing inputs


class VaultAgentState(BaseModel):
    """Single state object shared across all agents in the graph."""
    # Inputs
    input_documents: list[str] = Field(default_factory=list)
    # Optional source-column metadata for grounding (ADR-0004); empty = no grounding.
    source_schemas: list[SourceTable] = Field(default_factory=list)
    # Optional profiling evidence for the mapping step (WP9 §3.2 / ADR-0008 #4): a pre-step
    # file, table -> column -> ColumnProfile. Empty = no profiling (mapper leans on
    # names/comments, which the spike found sufficient for intent).
    profiling: dict[str, dict[str, ColumnProfile]] = Field(default_factory=dict)
    # WP23 brownfield mode: the logical model of the vault being EXTENDED, loaded from a
    # previous run's metadata/dv_model.yml via `run --existing`. None = greenfield, which is
    # the default and the byte-identity baseline. It is immutable context for the whole run:
    # the modeler emits only a delta against it, the merger never mutates it, and the
    # additive E_EXISTING_* gates compare the merged model back to it.
    existing_model: DVModel | None = None
    # The --existing path as the user gave it, for the diff artifact and the delta-ADR's
    # "Extends" section. Presentation only — nothing branches on it.
    existing_source: str | None = None
    # WP29: entity-resolution proposals for an extension run (concept -> existing
    # construct / NEW / same-as candidate / unresolved). Empty unless BOTH an existing
    # model and a declared schema are present — the grounding gate.
    resolutions: EntityResolution = Field(default_factory=EntityResolution)
    # WP34: link proposals derived from the new source's DECLARED foreign keys. Same
    # grounding gate as `resolutions` — an existing model AND a declared schema — so
    # greenfield and ungrounded runs keep it empty and stay byte-identical.
    link_proposals: LinkProposals = Field(default_factory=LinkProposals)
    # Working state
    # Business↔source mapping proposals (WP9): written by the source_mapper on grounded runs,
    # ratified at the HITL checkpoint, and consumed by staging binding. Empty when ungrounded.
    mappings: ProposedMapping = Field(default_factory=ProposedMapping)
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
