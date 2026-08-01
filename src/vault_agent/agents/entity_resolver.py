"""Entity resolution against an existing vault (WP29, brownfield Phase 2).

Answers the one question brownfield mode could previously only put to a human: *"the new
source calls this PARTNER — is that the existing ``hub_customer``, or a new hub?"* The Phase 2
spike measured that the model can propose that answer safely — zero false merges across 25
runs, and, decisively, honest degradation: blinded, it answers ``unresolved`` at low
confidence exactly where the evidence runs out instead of guessing confidently.

**The class asymmetry governs the design.** A false merge pushes foreign business keys into a
hub holding live history; a false split costs a redundant hub someone deletes at the
checkpoint. So nothing here merges anything — the agent proposes, a human ratifies, and only a
*ratified* resolution steers the modeler (see :func:`render_resolution_prompt_section`).

Placement (spec §2.1, binding): BEFORE ``dv2_modeler``. Once the modeler names a construct,
WP23's ``merge_models`` folds it by name and the decision is already made — so the proposal
has to exist, and be ratifiable, before modelling.

Inert unless BOTH an existing model and a declared source schema are present: greenfield and
ungrounded runs make no LLM call and change no state, which is what keeps
``test_greenfield_inertness.py`` and the WP23/WP28 guards byte-identical.

Split, mirroring ``source_mapper``:

* **Deterministic (keyless-tested):** the concept work-list, post-validation, the derived
  category, the flags, the prompt section.
* **Injectable :class:`ResolutionProposer`:** the forced-tool call (Sonnet-tier — measured
  sufficient in the spike; do not reach for the heavy model without a measurement).
"""
import json
import logging
from typing import Any, Protocol, cast

from langgraph.types import interrupt

from vault_agent.agents.base import BaseAgent
from vault_agent.agents.orchestrator import apply_resolution_decision
from vault_agent.llm import call_with_truncation_split
from vault_agent.rules.dv2_rules import normalize_identifier, resolution_category
from vault_agent.state import (
    RESOLUTION_CLASSES,
    RESOLUTION_SAME_AS,
    RESOLUTION_UNRESOLVED,
    DVModel,
    EntityResolution,
    FlagKind,
    ResolutionCategory,
    ResolutionProposal,
    VaultAgentState,
    concept_key,
    split_concept_key,
)

logger = logging.getLogger(__name__)

_TOOL_NAME = "emit_resolution"
_MAX_TOKENS = 8192


def _tool_schema() -> dict[str, Any]:
    """One decision per concept (concepts are data → keyed under ``additionalProperties``)."""
    entry = {
        "type": "object",
        "properties": {
            "resolution": {
                "type": "string",
                "description": (
                    "An existing construct's exact name (this concept IS it), or NEW, or "
                    "same_as_candidate, or unresolved."
                ),
            },
            "same_as": {
                "type": "string",
                "description": "For same_as_candidate: the construct it corresponds to.",
            },
            "confidence": {"type": "number", "description": "0..1, calibrated"},
            "evidence": {
                "type": "array",
                "items": {"type": "string"},
                "description": "What decided it — or precisely what was missing.",
            },
        },
        "required": ["resolution"],
    }
    return {
        "type": "object",
        "properties": {"resolutions": {"type": "object", "additionalProperties": entry}},
        "required": ["resolutions"],
    }


class ResolutionProposer(Protocol):
    """Turns the inventory + schema + concepts payload into per-concept decisions."""

    async def propose(self, *, system_prompt: str, user_content: str) -> dict[str, Any]: ...


class AnthropicResolutionProposer:
    """Default proposer backed by the shared forced-tool-use call path (Sonnet-tier)."""

    def __init__(self, model: str | None = None) -> None:
        from vault_agent.config import get_settings
        from vault_agent.llm import ForcedToolCaller

        self._caller = ForcedToolCaller(model or get_settings().primary_model)

    async def propose(self, *, system_prompt: str, user_content: str) -> dict[str, Any]:
        payload = await self._caller.call(
            tool_name=_TOOL_NAME,
            tool_description="Emit one resolution decision per new business concept.",
            input_schema=_tool_schema(),
            system_prompt=system_prompt,
            user_content=user_content,
            max_tokens=_MAX_TOKENS,
        )
        return cast(dict[str, Any], payload.get("resolutions", {}))


class _Concept:
    """One unit of work: a candidate business concept the new source introduces."""

    __slots__ = ("concept", "entity")

    def __init__(self, concept: str, entity: str | None) -> None:
        self.concept = concept
        self.entity = entity

    @property
    def key(self) -> str:
        """Identity is (label, entity) — the same rule as WP32's mapping concepts."""
        return concept_key(self.concept, self.entity)


def _split_concepts(concepts: list[_Concept]) -> tuple[list[_Concept], list[_Concept]] | None:
    """Halve the concept list; ``None`` at a single concept.

    Only the concepts split — every segment still sees the whole existing inventory, because a
    concept can only be resolved against all of it."""
    if len(concepts) < 2:
        return None
    midpoint = len(concepts) // 2
    return concepts[:midpoint], concepts[midpoint:]


def merge_decisions(segments: list[dict[str, Any]]) -> dict[str, Any]:
    """Fold per-segment decisions into one map; the first answer for a concept wins.

    Segments carry disjoint concept lists, so a repeat means the model answered about a
    concept it was not asked for; keeping the first is deterministic and harmless."""
    merged: dict[str, Any] = {}
    for segment in segments:
        for concept, decision in segment.items():
            merged.setdefault(concept, decision)
    return merged


def _inventory(existing: DVModel) -> list[dict[str, Any]]:
    """The existing constructs a concept can resolve to, with the keys that decide it."""
    items: list[dict[str, Any]] = [
        {
            "name": hub.name,
            "kind": "hub",
            "business_key": hub.business_key,
            "source_entity": hub.source_entity,
            **(
                {"fed_by": [s.source_table for s in hub.sources]}
                if hub.sources
                else {}
            ),
        }
        for hub in existing.hubs
    ]
    items += [
        {"name": link.name, "kind": "link", "connects": [ref.hub for ref in link.hub_refs]}
        for link in existing.links
    ]
    items += [
        {"name": sat.name, "kind": "satellite", "on": sat.parent, "type": sat.sat_type}
        for sat in existing.satellites
    ]
    return items


def pending_resolution_decisions(resolutions: EntityResolution) -> list[ResolutionProposal]:
    """The proposals a human must decide BEFORE modelling — undecided merges and same-as.

    A merge is the unsafe direction (it writes foreign business keys into a hub holding live
    history) and a same-as candidate is the deferred-equivalence case; both change what the
    modeler should emit, so both are worth stopping for. ``NEW`` needs no answer — it is what
    an unsteered modeler does anyway — and ``unresolved`` carries no answer to ratify, so
    neither triggers a stop. Both still reach the sign-off review queue as advisory items,
    exactly as before, and the review file written at the pause lists every proposal, so a
    human who wants to decide an ``unresolved`` one in the same edit can.

    Pure, and evaluated identically on the resume re-execution — which is what makes it safe
    to call above :func:`ResolutionCheckpointAgent.run`'s ``interrupt()``."""
    return [
        p
        for p in resolutions.proposals
        if p.ratification_status == "proposed"
        and (p.is_merge or p.resolution == RESOLUTION_SAME_AS)
    ]


def render_resolution_prompt_section(resolutions: EntityResolution) -> str:
    """Render RATIFIED resolutions as a modeler prompt section; ``''`` when there are none.

    Returning ``''`` unless a human has ratified something is the safety property, not a
    formality: an unratified proposal must never steer the modeler, because the modeler naming
    an existing construct is exactly what makes WP23's ``merge_models`` fold it — i.e. the
    merge would happen without anyone agreeing to it.

    The ratification reaches this function via :class:`ResolutionCheckpointAgent`, which
    pauses the graph between the resolver and the modeler. The original WP29 build had no such
    pause and assumed "a first run proposes, a subsequent run is steered" — which nothing
    implemented: the sign-off checkpoint sits after ``source_mapper``, so it ratifies only
    after this run's modeler is long done, and no later run read the ratification back. This
    function therefore returned ``''`` on every reachable path (defect and fix recorded in
    ``docs/log.md``, 2026-08-01).

    It also keeps the prompt byte-identical for greenfield, ungrounded and first runs, so the
    WP16 steering fixture and prompt caching are untouched."""
    ratified = [
        p
        for p in resolutions.proposals
        if p.ratification_status in ("accepted", "overridden")
        and (p.is_merge or p.resolution == RESOLUTION_SAME_AS)
    ]
    if not ratified:
        return ""
    lines = [
        "",
        "## Concepts a human has already resolved",
        "",
        "These decisions are ratified. Follow them exactly — they are not suggestions:",
        "",
    ]
    for proposal in ratified:
        label, entity = split_concept_key(proposal.concept)
        origin = f" (from {entity})" if entity else ""
        if proposal.resolution == RESOLUTION_SAME_AS:
            lines.append(
                f"- `{label}`{origin} is asserted equivalent to **{proposal.same_as}** but is "
                f"keyed differently: model it as its OWN hub. Do not reuse that name, and do "
                f"not merge the two — a human decides what links them."
            )
        else:
            lines.append(
                f"- `{label}`{origin} IS the existing **{proposal.resolution}**. Attach to it "
                f"by that exact name; do not introduce a second construct for it."
            )
    return "\n".join(lines) + "\n"


class EntityResolverAgent(BaseAgent):
    """Proposes, per new concept, whether it is an existing construct (WP29)."""

    prompt_path = "entity_resolver.md"

    def __init__(self, proposer: ResolutionProposer | None = None) -> None:
        self._proposer = proposer

    def _get_proposer(self) -> ResolutionProposer:
        if self._proposer is None:
            self._proposer = AnthropicResolutionProposer()
        return self._proposer

    @staticmethod
    def _concepts(state: VaultAgentState) -> list[_Concept]:
        """The candidate concepts this increment introduces: the identified business keys.

        Deterministic order, de-duplicated on (label, entity) — the WP32 identity rule, for
        the same reason: two entities can carry the same key label, and collapsing them into
        one question would apply one answer to both."""
        seen: set[str] = set()
        concepts: list[_Concept] = []
        for candidate in state.business_keys:
            if not candidate.field.strip():
                continue
            key = normalize_identifier(concept_key(candidate.field, candidate.entity))
            if key in seen:
                continue
            seen.add(key)
            concepts.append(_Concept(candidate.field, candidate.entity))
        return concepts

    def _payload(self, state: VaultAgentState, concepts: list[_Concept]) -> str:
        assert state.existing_model is not None  # guarded by run()
        schema = [
            {
                "table": table.table,
                "column": col.name,
                **({"type": col.type} if col.type else {}),
                **({"comment": " ".join(col.comment.split())} if col.comment else {}),
            }
            for table in state.source_schemas
            for col in table.column_refs
        ]
        payload = {
            "existing_vault": _inventory(state.existing_model),
            "new_source_schema": schema,
            # The key is SENT, never composed by the model (WP32): a label carrying
            # punctuation cannot produce an unparseable key if there is nothing to parse.
            "concepts": [
                {"key": c.key, "concept": c.concept, "entity": c.entity} for c in concepts
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        # Grounding-gated (ADR-0004 pattern) AND extension-gated: without both an existing
        # vault and a declared schema there is nothing to resolve against — inert.
        if state.existing_model is None or not state.source_schemas:
            return state
        concepts = self._concepts(state)
        if not concepts:
            return state

        logger.info(
            "resolving %d concept(s) against %d existing construct(s)",
            len(concepts),
            len(state.existing_model.hubs)
            + len(state.existing_model.links)
            + len(state.existing_model.satellites),
        )
        system_prompt = self.load_prompt()
        proposer = self._get_proposer()

        async def propose(chunk: list[_Concept]) -> dict[str, Any]:
            return await proposer.propose(
                system_prompt=system_prompt, user_content=self._payload(state, chunk)
            )

        segments = await call_with_truncation_split(propose, concepts, _split_concepts)
        raw = merge_decisions(segments)
        if len(segments) > 1:
            logger.info("resolved over %d segment(s)", len(segments))
            state.flag(
                "entity_resolver",
                f"the {len(concepts)} concept(s) did not fit one model response; resolution "
                f"ran over {len(segments)} segment(s) of the concept list (each saw the full "
                f"existing vault) — review the proposals for consistency",
                kind=FlagKind.INPUT_SEGMENTED,
            )
        state.resolutions = self._post_validate(state, concepts, raw)
        merges = sum(1 for p in state.resolutions.proposals if p.is_merge)
        state.decisions.append(
            {
                "agent": "entity_resolver",
                "proposals": len(state.resolutions.proposals),
                "merges_proposed": merges,
                "same_as": sum(
                    1 for p in state.resolutions.proposals if p.resolution == RESOLUTION_SAME_AS
                ),
                "unresolved": sum(
                    1
                    for p in state.resolutions.proposals
                    if p.resolution == RESOLUTION_UNRESOLVED
                ),
            }
        )
        return state

    def _post_validate(
        self, state: VaultAgentState, concepts: list[_Concept], raw: dict[str, Any]
    ) -> EntityResolution:
        """Validate every decision against the vault that actually exists (§2.4).

        A resolution naming a construct that is not there becomes ``unresolved`` with the
        violation appended to its evidence — never a silent drop, and never an invented
        construct. The same for a ``same_as`` target. This is the WP9 safety property, and it
        is what makes a hallucinated hub name harmless rather than a merge into nothing."""
        assert state.existing_model is not None
        existing = state.existing_model
        names = {
            c["name"]: c
            for c in _inventory(existing)
        }
        by_norm = {normalize_identifier(k): v for k, v in raw.items() if isinstance(v, dict)}
        label_counts: dict[str, int] = {}
        for c in concepts:
            norm = normalize_identifier(c.concept)
            label_counts[norm] = label_counts.get(norm, 0) + 1

        proposals: list[ResolutionProposal] = []
        for c in concepts:
            entry = by_norm.get(normalize_identifier(c.key))
            if entry is None and label_counts[normalize_identifier(c.concept)] == 1:
                # A bare-label answer is honoured only where the label is unambiguous in this
                # work-list; where it is not, there is deliberately no fallback (WP32).
                entry = by_norm.get(normalize_identifier(c.concept))
            answer = str(entry.get("resolution", RESOLUTION_UNRESOLVED)) if entry else ""
            evidence = [str(e) for e in entry.get("evidence", [])] if entry else []
            same_as = str(entry.get("same_as", "")) if entry else ""
            confidence = entry.get("confidence", 0.0) if entry else 0.0

            resolution, same_as_target, evidence = self._validate_answer(
                answer, same_as, evidence, names
            )
            proposals.append(
                ResolutionProposal(
                    concept=c.key,
                    resolution=resolution,
                    same_as=same_as_target,
                    confidence=max(
                        0.0,
                        min(
                            1.0,
                            float(confidence)
                            if isinstance(confidence, (int, float))
                            else 0.0,
                        ),
                    ),
                    # §2.3: DERIVED, never the model's own claim. Measured reason: the spike's
                    # resolver reported "semantic" for every case, including the exact-key ones
                    # where its answer was right.
                    category=cast(
                        ResolutionCategory,
                        resolution_category(
                            c.concept,
                            resolution,
                            existing.hubs,
                            state.source_schemas,
                            evidence,
                        ),
                    ),
                    evidence=evidence,
                )
            )
            self._flag(state, c, proposals[-1])
        return EntityResolution(proposals=proposals)

    @staticmethod
    def _validate_answer(
        answer: str, same_as: str, evidence: list[str], names: dict[str, Any]
    ) -> tuple[str, str | None, list[str]]:
        """Map a raw answer onto a valid resolution, demoting anything unverifiable."""
        if answer in RESOLUTION_CLASSES:
            if answer != RESOLUTION_SAME_AS:
                return answer, None, evidence
            if same_as in names:
                return answer, same_as, evidence
            return (
                RESOLUTION_UNRESOLVED,
                None,
                evidence
                + [
                    f"demoted: same-as target {same_as!r} is not a construct of the existing "
                    f"vault"
                ],
            )
        if answer in names:
            return answer, None, evidence
        return (
            RESOLUTION_UNRESOLVED,
            None,
            evidence
            + [f"demoted: {answer!r} is not a construct of the existing vault"],
        )

    @staticmethod
    def _flag(state: VaultAgentState, concept: _Concept, proposal: ResolutionProposal) -> None:
        """Raise the review-queue flag a proposal needs; a merge or NEW needs none.

        Neither flag blocks sign-off: an unresolved concept is honest output, the same call
        WP9 made for mapping gaps (``requires_signoff`` semantics stay unchanged)."""
        if proposal.resolution == RESOLUTION_UNRESOLVED:
            state.flag(
                "entity_resolver",
                f"concept {concept.concept!r} could not be resolved against the existing "
                f"vault — a human decides whether it is an existing construct or new",
                kind=FlagKind.RESOLUTION_UNRESOLVED,
                asset=concept.key,
            )
        elif proposal.resolution == RESOLUTION_SAME_AS:
            state.flag(
                "entity_resolver",
                f"concept {concept.concept!r} is asserted equivalent to "
                f"{proposal.same_as!r} but is keyed differently — two constructs are modelled "
                f"and a human decides what relates them; never merged",
                kind=FlagKind.RESOLUTION_SAME_AS,
                asset=concept.key,
            )


class ResolutionCheckpointAgent(BaseAgent):
    """Pauses between the resolver and the modeler so a ratification can still steer it.

    It sits in this file rather than its own because it has no prompt and no model call: it is
    the second half of WP29's mechanism, and the pause condition
    (:func:`pending_resolution_decisions`) belongs beside the proposals it reads — the same
    reason ``HumanCheckpointAgent`` rides with the orchestrator.

    **Why a second checkpoint exists at all.** Only a ratified resolution steers the modeler,
    and the sign-off checkpoint runs after ``source_mapper`` — i.e. after modelling, code
    generation and validation. A ratification made there can no longer affect the model it was
    about, and nothing carried it into a later run, so the steering path was unreachable
    end-to-end. Ratifying HERE is what closes it, within one run and one resume.

    **Inert unless there is something to decide.** No pending merge or same-as candidate means
    no pause and no state change — greenfield, ungrounded and NEW/unresolved-only runs are
    untouched, which is what keeps ``test_greenfield_inertness.py`` byte-identical.

    Everything above ``interrupt()`` must stay pure/idempotent: on resume the node re-executes
    from the top, so the pause condition is computed a second time. It is a pure filter over
    state, so that is safe — and deliberately so, since the resolver's paid model call sits in
    the PREVIOUS node and must never be re-run by a resume."""

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        pending = pending_resolution_decisions(state.resolutions)
        if not pending:
            return state

        logger.info("resolution checkpoint: %d proposal(s) await a decision", len(pending))
        # No state mutation above this line — see the class docstring.
        decision = interrupt(
            {
                "checkpoint": "resolution",
                "pending": [p.model_dump() for p in pending],
                "instructions": (
                    "Decide these before the model is built: resume with "
                    "vault-agent resume --resolve \"<concept>=<construct>\", an edited "
                    "resolutions.review.yml via --resolutions, or --accept to ratify them "
                    "as proposed."
                ),
            }
        )
        decided = apply_resolution_decision(state, decision)
        state.decisions.append(
            {
                "agent": "resolution_checkpoint",
                "pending": len(pending),
                "decided": len(decided),
                "steering": len(pending_resolution_decisions(state.resolutions)) < len(pending),
            }
        )
        return state
