"""Orchestrator agent (ADR-0002, ADR-0006).

Two deterministic responsibilities, no LLM:

1. **Planning entry node.** Runs first in the graph (``START -> orchestrator -> …``). It
   validates the run's inputs and records a typed :class:`~vault_agent.state.ExecutionPlan`
   on the state, so the trace shows the planned stages, declared inputs, and whether
   source-schema grounding is active.

2. **Human-in-the-loop checkpoint.** :func:`assemble_review_queue` derives a categorized
   :class:`HumanReviewQueue` from a finished run — the validation issues, contracts still
   awaiting an owner, and the agents' review flags. Per ADR-0006 this deterministic queue is
   surfaced to the human (CLI / file) and, when it blocks sign-off, the
   :class:`HumanCheckpointAgent` pauses the graph on a live LangGraph ``interrupt()`` until a
   human resumes with their decision. Everything before ``interrupt()`` must stay
   pure/idempotent because the node re-executes from the top on resume —
   :func:`assemble_review_queue` is pure, so re-assembling the queue is safe.

Being deterministic, the whole agent is unit-tested without an API key.
"""
import logging
from typing import Any, Literal

from langgraph.types import interrupt
from pydantic import BaseModel, Field

from vault_agent.agents.base import BaseAgent
from vault_agent.models.contract import ContractOwner
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import (
    ExecutionPlan,
    FlagKind,
    Hub,
    HubSource,
    Proposal,
    VaultAgentState,
    concept_ref_matches,
    match_concept_refs,
    resolve_concept_ref,
    split_concept_key,
)

logger = logging.getLogger(__name__)

ReviewKind = Literal[
    "contract_owner", "validation_error", "validation_warning", "review_flag"
]

# Stable categories for routine, repetitive advisory ``review_flag`` items, keyed by the
# flag's typed ``kind`` (never by message text). Used only to *aggregate* identical-shape
# flags at render time (finding #3) so they don't bury the substantive items. Flags whose
# kind is not listed here fall into ``"other"`` and are always rendered individually.
REVIEW_FLAG_GROUPS: dict[str, str] = {
    FlagKind.UNDETERMINED_TYPE: "undetermined-type",
    FlagKind.NO_SOURCE_SCHEMA: "no-source-schema",
    FlagKind.SOURCE_BINDING: "source-binding",
    FlagKind.MAPPING_GAP: "mapping-gap",
    FlagKind.MAPPING_UNRESOLVED: "mapping-unresolved",
}
_DEFAULT_GROUP = "other"
# Above this many items in one group, the renderers collapse it to a single summarised line.
AGGREGATE_THRESHOLD = 3

# Human-readable noun phrase per aggregatable group, for the collapsed summary line.
_GROUP_LABELS: dict[str, str] = {
    "undetermined-type": "undetermined field type",
    "no-source-schema": "contract(s) without a source schema",
    "source-binding": "inferred staging source binding(s)",
    "mapping-gap": "concept(s) with no in-scope source (coverage gap)",
    "mapping-unresolved": "concept(s) with an unresolved source mapping",
}


def _sample_term(item: "ReviewItem") -> str:
    """A short representative term for a collapsed line: the flag's typed asset."""
    return item.asset or item.summary


def _sample_phrase(members: list["ReviewItem"], limit: int = 2) -> str:
    terms = [_sample_term(member) for member in members[:limit]]
    suffix = ", …" if len(members) > limit else ""
    return ", ".join(terms) + suffix


class ReviewItem(BaseModel):
    """One thing a human must look at before the model/contracts are considered agreed."""

    kind: ReviewKind
    summary: str
    detail: str = ""
    source: str = ""  # the agent / construct the item originates from
    group: str = _DEFAULT_GROUP  # advisory-flag category, for render-time aggregation
    asset: str | None = None  # the affected asset/construct, carried from the typed flag


class HumanReviewQueue(BaseModel):
    """The categorized checkpoint payload derived from a finished run."""

    items: list[ReviewItem] = Field(default_factory=list)

    @property
    def requires_signoff(self) -> bool:
        """True when something blocks agreement: a hard validation error or an unassigned
        contract owner. Warnings and advisory flags inform review but do not block."""
        return any(
            item.kind in ("validation_error", "contract_owner") for item in self.items
        )

    def by_kind(self) -> dict[str, list[ReviewItem]]:
        grouped: dict[str, list[ReviewItem]] = {}
        for item in self.items:
            grouped.setdefault(item.kind, []).append(item)
        return grouped


def assemble_review_queue(state: VaultAgentState) -> HumanReviewQueue:
    """Build the human-review checkpoint from a finished run's state (deterministic)."""
    items: list[ReviewItem] = []

    # Validation issues — severity maps to a blocking error vs an advisory warning.
    for issue in state.validation_report.issues:
        kind: ReviewKind = (
            "validation_error" if issue.severity == "error" else "validation_warning"
        )
        code = issue.code or "issue"
        construct = issue.construct or "model"
        items.append(
            ReviewItem(
                kind=kind,
                summary=f"{code} on {construct}",
                detail=issue.message,
                source="validator",
            )
        )

    # Contracts still carrying the placeholder owner — a required human assignment.
    for contract in state.artifacts.contracts:
        owner = contract.get("owner") or {}
        if owner.get("name") == ContractOwner.PLACEHOLDER_NAME:
            name = str(contract.get("name", "<unnamed>"))
            items.append(
                ReviewItem(
                    kind="contract_owner",
                    summary=f"Assign an owner for contract {name!r}",
                    detail="The agent never invents an owner; assign one before agreeing "
                    "the contract.",
                    source="data_contract",
                )
            )

    # Remaining advisory flags. The owner concern is already a structured contract_owner
    # item above, so drop those flags (matched on their typed kind, never on message text)
    # to avoid listing the same thing twice.
    for flag in state.flags:
        if flag.kind == FlagKind.OWNER_PLACEHOLDER:
            continue
        items.append(
            ReviewItem(
                kind="review_flag",
                summary=str(flag),
                source=flag.agent,
                group=REVIEW_FLAG_GROUPS.get(flag.kind, _DEFAULT_GROUP),
                asset=flag.asset,
            )
        )

    return HumanReviewQueue(items=items)


# Single owner of the review-queue *presentation knowledge* (WP5 §5.1): the heading per
# kind and the stable blocking-first order. Both renderers — render_review_queue_md here
# and the CLI's rich-console _print_checkpoint — import these, so they can never drift.
KIND_HEADINGS: dict[str, str] = {
    "validation_error": "Validation errors (block agreement)",
    "contract_owner": "Contract owners to assign (block agreement)",
    "validation_warning": "Validation warnings (advisory)",
    "review_flag": "Review flags (advisory)",
}
# Stable presentation order: blocking concerns first, advisory last.
KIND_ORDER: tuple[str, ...] = (
    "validation_error",
    "contract_owner",
    "validation_warning",
    "review_flag",
)


def _collapsed_source(members: list[ReviewItem]) -> str:
    """The agent a collapsed line is attributed to: the members' one source, or "multiple
    agents" when they disagree (honest attribution beats a plausible single name)."""
    sources = {item.source for item in members}
    return sources.pop() if len(sources) == 1 else "multiple agents"


def aggregate_review_flags(flags: list[ReviewItem]) -> list[ReviewItem]:
    """Collapse repetitive advisory flags for display (finding #3).

    A group with more than :data:`AGGREGATE_THRESHOLD` items becomes one summarised
    ``ReviewItem`` (count + a short sample); smaller groups and the catch-all ``"other"``
    pass through individually. Presentation only — no data is lost, the per-item detail still
    lives in the artifacts (e.g. the contracts). Groups render in first-appearance order."""
    by_group: dict[str, list[ReviewItem]] = {}
    for item in flags:
        by_group.setdefault(item.group, []).append(item)

    collapsed: list[ReviewItem] = []
    for group, members in by_group.items():
        if group != _DEFAULT_GROUP and len(members) > AGGREGATE_THRESHOLD:
            label = _GROUP_LABELS.get(group, group)
            collapsed.append(
                ReviewItem(
                    kind="review_flag",
                    summary=f"{len(members)}× {label}",
                    detail=f"e.g. {_sample_phrase(members)} — review before agreeing",
                    # Derived from the members, never hardcoded (WP21 §2.3): the collapsed
                    # groups come from three different agents (contracts from data_contract,
                    # source bindings from code_generator, mappings from source_mapper), and
                    # naming the wrong one sends a reviewer to the wrong artifact.
                    source=_collapsed_source(members),
                    group=group,
                )
            )
        else:
            collapsed.extend(members)
    return collapsed


def render_review_queue_md(queue: HumanReviewQueue) -> str:
    """Render the queue as a Markdown checkpoint document (one artifact per run)."""
    lines = ["# Human-in-the-loop checkpoint", ""]
    if not queue.items:
        lines.append("No items require human review. ✅")
        return "\n".join(lines) + "\n"

    verdict = "requires sign-off" if queue.requires_signoff else "advisory only"
    lines.append(f"**Status:** {verdict} — {len(queue.items)} item(s).")
    lines.append("")
    grouped = queue.by_kind()
    for kind in KIND_ORDER:
        group = grouped.get(kind)
        if not group:
            continue
        if kind == "review_flag":
            group = aggregate_review_flags(group)
        lines.append(f"## {KIND_HEADINGS[kind]}")
        lines.append("")
        for item in group:
            line = f"- **{item.summary}**"
            if item.detail:
                line += f" — {item.detail}"
            if item.source:
                line += f" _({item.source})_"
            lines.append(line)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


class OrchestratorAgent(BaseAgent):
    """Deterministic planning entry node; also owns the review-queue helpers above."""

    def __init__(self, planned_stages: list[str] | None = None) -> None:
        # The downstream stages this run will execute, injected by the graph so the plan
        # tracks the real pipeline without this module importing graph (no import cycle).
        self._planned_stages = planned_stages or []

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        notes: list[str] = []
        if not state.input_documents:
            notes.append(
                "no input documents declared; downstream parsing will produce nothing"
            )
            state.flag(
                "orchestrator",
                "no input documents declared",
                severity="error",
                kind=FlagKind.MISSING_INPUT,
            )

        plan = ExecutionPlan(
            stages=list(self._planned_stages),
            input_documents=len(state.input_documents),
            grounded=bool(state.source_schemas),
            extending=state.existing_model is not None,
            notes=notes,
        )
        state.plan = plan
        logger.info(
            "planned %d stage(s), %d input document(s), grounding %s",
            len(plan.stages),
            plan.input_documents,
            "on" if plan.grounded else "off",
        )
        state.decisions.append(
            {
                "agent": "orchestrator",
                "stages": len(plan.stages),
                "inputs": plan.input_documents,
                "grounded": plan.grounded,
            }
        )
        return state


def apply_human_decision(state: VaultAgentState, decision: Any) -> list[str]:
    """Apply a human's sign-off decision to the state, returning the assets re-owned.

    ``decision`` is whatever the resume supplied, expected as
    ``{"owners": {asset: {"name": ..., "email": ...}}, "accept": bool}``. Owners are written
    onto the matching contracts, and the now-resolved placeholder-owner review flags are
    pruned — matched on the flag's typed kind and *exact* asset name, so assigning
    ``customer`` never prunes the still-unresolved flag for ``customer_address``.
    Deterministic and pure (no interrupt), so it is unit-tested directly."""
    owners = decision.get("owners", {}) if isinstance(decision, dict) else {}
    assigned: list[str] = []
    for contract in state.artifacts.contracts:
        name = contract.get("name")
        proposed = owners.get(name) if isinstance(owners, dict) else None
        if name and isinstance(proposed, dict) and proposed.get("name"):
            contract["owner"] = {
                "name": proposed["name"],
                "email": proposed.get("email"),
            }
            assigned.append(str(name))

    if assigned:
        resolved = set(assigned)
        state.flags = [
            flag
            for flag in state.flags
            if not (flag.kind == FlagKind.OWNER_PLACEHOLDER and flag.asset in resolved)
        ]

    # WP9: ratify / override business↔source mappings, then re-bind staging to them.
    mappings = decision.get("mappings", {}) if isinstance(decision, dict) else {}
    accept = bool(decision.get("accept")) if isinstance(decision, dict) else False
    _apply_mapping_decision(state, mappings if isinstance(mappings, dict) else {}, accept)
    # WP10: resolve a multi-candidate key into a multi-source hub (Hub.sources).
    sources = decision.get("mapping_sources", {}) if isinstance(decision, dict) else {}
    _apply_mapping_sources(state, sources if isinstance(sources, dict) else {})
    return assigned


def _resolve_hub_for_concept(state: VaultAgentState, given: str) -> Hub | None:
    """The hub a human's concept reference names, via the one WP32 matching rule.

    A bare business-key label is honoured only when exactly one hub carries it; when several
    do, the reference is genuinely ambiguous and is ignored rather than applied to an arbitrary
    one of them (the defect WP32 fixed was doing exactly that, silently)."""
    index = resolve_concept_ref(
        given, [(h.business_key, h.source_entity) for h in state.dv_model.hubs]
    )
    return state.dv_model.hubs[index] if index is not None else None


def _prune_concept(
    state: VaultAgentState, concept: str, entity: str | None, *, label_unique: bool,
    kinds: tuple[str, ...],
) -> None:
    """Drop a ratified concept from ``unresolved``/``gaps`` and prune its flags (WP32).

    Entries and flag assets are concept KEYS since WP32, but a checkpoint written before it —
    or a hand-edited file — holds bare labels, so both are matched through
    :func:`concept_ref_matches`: the key always, the label only where it is unique. Without
    the uniqueness condition, ratifying one of three concepts labelled ``Name`` would clear
    its two siblings' entries as well."""
    def stale(ref: str) -> bool:
        return concept_ref_matches(ref, concept, entity, label_unique=label_unique)

    state.mappings.unresolved = [u for u in state.mappings.unresolved if not stale(u)]
    state.mappings.gaps = [g for g in state.mappings.gaps if not stale(g)]
    state.flags = [
        f
        for f in state.flags
        if not (f.kind in kinds and f.asset and stale(f.asset))
    ]


def _apply_mapping_sources(
    state: VaultAgentState, sources_by_concept: dict[str, Any]
) -> None:
    """Resolve ratified multi-source key feeds into ``Hub.sources`` (WP10 §2.4).

    For each concept the human resolved with a ``sources:`` list, set the matching hub's
    ``sources``, drop the concept from ``unresolved`` and prune its flag. A subsequent
    generation renders the hub as multi-source; regeneration of an already-emitted run is a
    fresh run, not an in-place resume rewrite."""
    for concept, feeds in sources_by_concept.items():
        if not isinstance(feeds, list) or not feeds:
            continue
        hub = _resolve_hub_for_concept(state, concept)
        if hub is None:
            continue
        hub.sources = [
            HubSource(source_table=str(f["table"]), business_key_column=str(f["column"]))
            for f in feeds
            if isinstance(f, dict) and f.get("table") and f.get("column")
        ]
        label_unique = (
            sum(
                1
                for h in state.dv_model.hubs
                if normalize_identifier(h.business_key)
                == normalize_identifier(hub.business_key)
            )
            == 1
        )
        _prune_concept(
            state, hub.business_key, hub.source_entity, label_unique=label_unique,
            kinds=(FlagKind.MAPPING_UNRESOLVED,),
        )


def _apply_mapping_decision(
    state: VaultAgentState, overrides: dict[str, Any], accept: bool
) -> None:
    """Apply a human's mapping ratification (WP9 §5): ``{concept: "TABLE.COLUMN"}`` overrides
    plus a global ``accept``. Overrides update/promote a proposal (from unresolved/gap),
    mark it ``overridden``, and prune its mapping flag; ``accept`` marks every still-proposed
    proposal ``accepted``. Any change re-binds staging so it reads the ratified source."""
    changed = False
    for concept, target in overrides.items():
        if not isinstance(target, str) or "." not in target:
            continue
        table, column = target.rsplit(".", 1)
        # WP32: resolve against the run's WHOLE concept universe — proposals plus the
        # unresolved and gap entries — not just the proposals. Ambiguity is a property of the
        # run: a bare "Name" that happens to be unique among the proposals may still name any
        # of three unresolved concepts, and choosing one of them is the defect being fixed.
        universe: list[tuple[str, str | None]] = [
            (p.concept, p.entity) for p in state.mappings.proposals
        ] + [
            split_concept_key(entry)
            for entry in list(state.mappings.unresolved) + list(state.mappings.gaps)
        ]
        matches = match_concept_refs(concept, universe)
        if len(matches) > 1:
            # Genuinely ambiguous: refuse rather than guess. The concept keeps its flag, so
            # the human sees it again with the key to address it by.
            logger.warning(
                "mapping override %r matches %d concepts; ignored — address one by its key",
                concept, len(matches),
            )
            continue
        index = matches[0] if matches and matches[0] < len(state.mappings.proposals) else None
        if index is not None:
            existing = state.mappings.proposals[index]
            existing.table, existing.column = table.strip(), column.strip()
            existing.ratification_status = "overridden"
            label, entity = existing.concept, existing.entity
        elif matches:
            # Resolved to an unresolved/gap entry: promote it, keeping ITS identity rather
            # than whatever form the human typed.
            label, entity = universe[matches[0]]
            state.mappings.proposals.append(
                Proposal(
                    concept=label,
                    entity=entity,
                    table=table.strip(),
                    column=column.strip(),
                    confidence=1.0,
                    evidence=["human override"],
                    ratification_status="overridden",
                )
            )
        else:
            # Promoting an unresolved concept / gap: split the reference so the new proposal
            # records the entity it belongs to (WP32) instead of losing it. A bare label
            # yields entity=None, i.e. exactly the pre-WP32 shape.
            label, entity = split_concept_key(concept)
            state.mappings.proposals.append(
                Proposal(
                    concept=label,
                    entity=entity,
                    table=table.strip(),
                    column=column.strip(),
                    confidence=1.0,
                    evidence=["human override"],
                    ratification_status="overridden",
                )
            )
        label_unique = (
            sum(
                1
                for p in state.mappings.proposals
                if normalize_identifier(p.concept) == normalize_identifier(label)
            )
            == 1
        )
        _prune_concept(
            state, label, entity, label_unique=label_unique,
            kinds=(FlagKind.MAPPING_UNRESOLVED, FlagKind.MAPPING_GAP),
        )
        changed = True

    if accept:
        for proposal in state.mappings.proposals:
            if proposal.ratification_status == "proposed":
                proposal.ratification_status = "accepted"
                changed = True

    if changed:
        from vault_agent.agents.source_mapper import rebind_staging

        rebind_staging(state)


class HumanCheckpointAgent(BaseAgent):
    """Human-in-the-loop gate (ADR-0006). On the validated path it assembles the review
    queue and, when something blocks agreement, pauses the graph with LangGraph's
    ``interrupt()`` until a human resumes with their decision. When nothing blocks it passes
    straight through. Requires the graph to be compiled with a checkpointer.

    Everything before ``interrupt()`` must stay pure/idempotent: on resume the node
    re-executes from the top, so queue assembly (and logging) runs again —
    :func:`assemble_review_queue` is pure, which makes that safe."""

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        queue = assemble_review_queue(state)
        logger.info(
            "human checkpoint: %d review item(s), requires sign-off: %s",
            len(queue.items),
            queue.requires_signoff,
        )
        if not queue.requires_signoff:
            state.decisions.append(
                {"agent": "human_checkpoint", "interrupted": False, "assigned": []}
            )
            return state

        # Everything above interrupt() re-executes on resume, so it must stay
        # pure/idempotent — no state mutation before this line.
        decision = interrupt(
            {
                "review_queue": queue.model_dump(),
                "instructions": (
                    "Assign owners for the listed contracts and/or accept to proceed; "
                    "resume with vault-agent resume."
                ),
            }
        )
        assigned = apply_human_decision(state, decision)
        state.decisions.append(
            {
                "agent": "human_checkpoint",
                "interrupted": True,
                "assigned": assigned,
                "accepted": bool(decision.get("accept"))
                if isinstance(decision, dict)
                else False,
            }
        )
        return state
