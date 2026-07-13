"""Business↔source mapping agent (WP9, ADR-0008 Accepted).

Proposes, per business concept in the *validated* DV model (hub business keys and satellite
attributes), which physical source column feeds it — or that it is a coverage gap. An
assist-level, human-ratified step: the agent never finalises an unreviewed mapping (ADR-0008
#1). The mechanism is the spike's measured winner (LLM-first): one forced-tool pass proposes
everything from the enriched schema + profiling + comments, then deterministic
post-validation demotes any pick that names a non-existent column to ``unresolved`` — never
inventing a column (the spike's key safety property).

Owns ``state.mappings`` and, on a grounded run, re-binds the staging source models to the
proposed source tables (WP9 §6). Inert when ungrounded (no ``state.source_schemas``): no LLM
call, no state change — so an ungrounded run stays byte-identical and keyless.

Graph note (WP9 §4, as-built): the spec's diagram places the mapper before code generation,
but the validator validates the code generator's artifacts (``_check_artifact_columns``), so
code generation cannot move after the validator. The mapper therefore runs on the *validated*
path (validator --pass--> source_mapper --> human_checkpoint) and performs the staging re-bind
itself, rather than code generation consuming the mapping. Same outcome, one fewer node.

LLM vs deterministic split mirrors ``data_contract``:
- **Deterministic (keyless-tested):** concept work-list assembly, post-validation, the
  confidence category (§7), gap/unresolved flags, staging re-bind.
- **Injectable :class:`MappingProposer`:** the forced-tool call (Sonnet-tier).
"""
import json
import logging
import re
from typing import Any, Protocol, cast

from vault_agent.agents.base import BaseAgent
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import (
    ColumnProfile,
    FlagKind,
    MappingCategory,
    Proposal,
    ProposedMapping,
    SourceColumn,
    VaultAgentState,
)

logger = logging.getLogger(__name__)

_TOOL_NAME = "emit_mapping"
_MAX_TOKENS = 8192
# A business_key column profiling at least this unique and this non-null is a plausible key.
_KEY_UNIQUENESS = 0.95
_KEY_NULL_TOLERANCE = 0.05
_STOP_TOKENS = {"THE", "A", "AN", "OF", "ID", "NR", "NO", "DOC"}


def _tokens(text: str) -> set[str]:
    return {t for t in normalize_identifier(text).split("_") if len(t) >= 2} - _STOP_TOKENS


def _tool_schema() -> dict[str, Any]:
    """One decision per concept (concepts are data → keyed under additionalProperties)."""
    entry = {
        "type": "object",
        "properties": {
            "decision": {
                "type": "string",
                "enum": ["map", "gap", "unresolved"],
                "description": "map = source found; gap = no in-scope source; unresolved = unsure",
            },
            "table": {"type": "string"},
            "column": {"type": "string"},
            "confidence": {"type": "number", "description": "0..1 calibrated confidence"},
            "evidence": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["decision"],
    }
    return {
        "type": "object",
        "properties": {"mappings": {"type": "object", "additionalProperties": entry}},
        "required": ["mappings"],
    }


class MappingProposer(Protocol):
    """Turns the concepts + schema + profiling payload into per-concept decisions."""

    async def propose(self, *, system_prompt: str, user_content: str) -> dict[str, Any]: ...


class AnthropicMappingProposer:
    """Default proposer backed by the shared forced-tool-use call path (Sonnet-tier)."""

    def __init__(self, model: str | None = None) -> None:
        from vault_agent.config import get_settings
        from vault_agent.llm import ForcedToolCaller

        self._caller = ForcedToolCaller(model or get_settings().primary_model)

    async def propose(self, *, system_prompt: str, user_content: str) -> dict[str, Any]:
        payload = await self._caller.call(
            tool_name=_TOOL_NAME,
            tool_description="Emit one source-mapping decision per business concept.",
            input_schema=_tool_schema(),
            system_prompt=system_prompt,
            user_content=user_content,
            max_tokens=_MAX_TOKENS,
        )
        return cast(dict[str, Any], payload.get("mappings", {}))


class _Concept:
    """One unit of work: a model construct's concept, entity, and kind (never the answer)."""

    __slots__ = ("concept", "entity", "kind")

    def __init__(self, concept: str, entity: str | None, kind: str) -> None:
        self.concept = concept
        self.entity = entity
        self.kind = kind


class SourceMapperAgent(BaseAgent):
    """Drafts a business↔source mapping per model concept; re-binds staging (WP9)."""

    prompt_path = "source_mapper.md"

    def __init__(self, proposer: MappingProposer | None = None) -> None:
        self._proposer = proposer

    def _get_proposer(self) -> MappingProposer:
        if self._proposer is None:
            self._proposer = AnthropicMappingProposer()
        return self._proposer

    @staticmethod
    def _concepts(state: VaultAgentState) -> list[_Concept]:
        """Concept work-list from the validated model: hub keys + satellite attributes.

        Deterministic order (hubs then satellites); duplicate concept labels collapse to the
        first so the same label is asked once."""
        seen: set[str] = set()
        concepts: list[_Concept] = []

        def add(concept: str, entity: str | None, kind: str) -> None:
            key = normalize_identifier(concept)
            if concept.strip() and key not in seen:
                seen.add(key)
                concepts.append(_Concept(concept, entity, kind))

        for hub in state.dv_model.hubs:
            add(hub.business_key, hub.source_entity, "business_key")
        for sat in state.dv_model.satellites:
            for attr in sat.attributes:
                add(attr, sat.parent, "attribute")
        return concepts

    def _payload(self, state: VaultAgentState, concepts: list[_Concept]) -> str:
        schema: list[dict[str, Any]] = []
        for table in state.source_schemas:
            for col in table.column_refs:
                entry: dict[str, Any] = {"table": table.table, "column": col.name}
                if col.type:
                    entry["type"] = col.type
                if col.comment:
                    entry["comment"] = " ".join(col.comment.split())
                blurb = self._profile_blurb(state, table.table, col.name)
                if blurb:
                    entry["profiling"] = blurb
                schema.append(entry)
        payload = {
            "concepts": [
                {"concept": c.concept, "entity": c.entity, "kind": c.kind} for c in concepts
            ],
            "schema": schema,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _profile_blurb(state: VaultAgentState, table: str, column: str) -> str:
        profile = state.profiling.get(table, {}).get(column)
        if profile is None:
            return ""
        return (
            f"uniqueness={profile.uniqueness_ratio:g} null={profile.null_ratio:g} "
            f"distinct={profile.distinct_count} e.g.={profile.example_values[:2]}"
        )

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        # Ungrounded: nothing to map against — inert (byte-identical, no LLM call).
        if not state.source_schemas:
            return state
        concepts = self._concepts(state)
        if not concepts:
            return state

        logger.info("mapping %d concept(s) against %d source table(s)",
                    len(concepts), len(state.source_schemas))
        system_prompt = self.load_prompt()
        raw = await self._get_proposer().propose(
            system_prompt=system_prompt, user_content=self._payload(state, concepts)
        )
        state.mappings = self._post_validate(state, concepts, raw)
        self._rebind_staging(state)
        state.decisions.append(
            {
                "agent": "source_mapper",
                "proposals": len(state.mappings.proposals),
                "gaps": len(state.mappings.gaps),
                "unresolved": len(state.mappings.unresolved),
            }
        )
        return state

    def _post_validate(
        self, state: VaultAgentState, concepts: list[_Concept], raw: dict[str, Any]
    ) -> ProposedMapping:
        """Turn the proposer's per-concept decisions into a validated ProposedMapping.

        A ``map`` to a non-existent column is demoted to ``unresolved`` — never invented. A
        ``gap`` is a first-class output (ADR-0008 #3). Multi-candidate keys the proposer left
        ``unresolved`` keep their candidate evidence for WP10."""
        index = self._column_index(state)  # (table_norm, col_norm) -> (real table, real col)
        by_norm = {
            normalize_identifier(k): v for k, v in raw.items() if isinstance(v, dict)
        }
        proposals: list[Proposal] = []
        gaps: list[str] = []
        unresolved: list[str] = []
        for c in concepts:
            entry = by_norm.get(normalize_identifier(c.concept))
            decision = str(entry.get("decision", "unresolved")) if entry else "unresolved"
            evidence = [str(e) for e in entry.get("evidence", [])] if entry else []
            if decision == "gap":
                gaps.append(c.concept)
                state.flag(
                    "source_mapper",
                    f"concept {c.concept!r} has no in-scope source (derived/enriched); it "
                    f"belongs to the Business Vault / marts, not the Raw Vault",
                    kind=FlagKind.MAPPING_GAP,
                    asset=c.concept,
                )
                continue
            key = (
                normalize_identifier(str(entry.get("table", ""))) if entry else "",
                normalize_identifier(str(entry.get("column", ""))) if entry else "",
            )
            if decision != "map" or key not in index:
                # WP9.1 F1b: deterministic FK-demotion. When the proposer defers a business
                # key it saw in >= 2 tables, but all but one candidate are FK references to
                # the remaining anchor entity, resolve to the anchor (belt-and-braces; the
                # prompt handles it first). No comments / genuinely cross-system -> unresolved.
                anchor = (
                    self._fk_demote(evidence, state)
                    if c.kind == "business_key" and decision == "unresolved"
                    else None
                )
                if anchor is not None:
                    table, column, demoted = anchor
                    proposals.append(
                        self._make_proposal(
                            state, c, table, column, 0.7,
                            evidence + [f"fk-demotion: {', '.join(demoted)}"],
                        )
                    )
                    continue
                unresolved.append(c.concept)
                detail = "; candidates: " + ", ".join(evidence) if (evidence and c.kind ==
                         "business_key") else ""
                state.flag(
                    "source_mapper",
                    f"concept {c.concept!r} could not be resolved to a single source column"
                    f"{detail} — a human ratifies it (a multi-source key is deferred to WP10)",
                    kind=FlagKind.MAPPING_UNRESOLVED,
                    asset=c.concept,
                )
                continue
            table, column = index[key]
            confidence = entry.get("confidence", 0.5) if entry else 0.5
            proposals.append(
                self._make_proposal(state, c, table, column, confidence, evidence or ["llm"])
            )
        return ProposedMapping(proposals=proposals, gaps=gaps, unresolved=unresolved)

    def _make_proposal(
        self, state: VaultAgentState, c: _Concept, table: str, column: str,
        confidence: Any, evidence: list[str],
    ) -> Proposal:
        profile = state.profiling.get(table, {}).get(column)
        column_ref = self._column_ref(state, table, column)
        conf = max(0.0, min(1.0, float(confidence)
                            if isinstance(confidence, (int, float)) else 0.5))
        return Proposal(
            concept=c.concept, entity=c.entity, table=table, column=column, confidence=conf,
            evidence=evidence,
            category=self._category(c.concept, column, column_ref, profile, c.kind),
        )

    def _fk_demote(
        self, evidence: list[str], state: VaultAgentState
    ) -> tuple[str, str, list[str]] | None:
        """Resolve a deferred business key to its entity-anchor table (WP9.1 F1b).

        Extracts ``TABLE.COLUMN`` candidates the proposer named in its evidence; if all but
        one are FK references (comment marks FK + names the anchor's table) to the remaining
        anchor candidate, returns ``(anchor table, anchor col, demoted 'T.C' labels)``. A
        single distinct anchor is required; otherwise ``None`` (stays unresolved)."""
        index = self._column_index(state)
        candidates: list[tuple[str, str]] = []
        for line in evidence:
            for match in re.finditer(r"([A-Za-z_]\w*)\.([A-Za-z_]\w*)", line):
                pair = (normalize_identifier(match.group(1)), normalize_identifier(match.group(2)))
                real = index.get(pair)
                if real is not None and real not in candidates:
                    candidates.append(real)
        if len(candidates) < 2 or len({t for t, _ in candidates}) < 2:
            return None
        anchors: list[tuple[str, str]] = []
        for anchor in candidates:
            others = [c for c in candidates if c[0] != anchor[0]]
            if others and all(self._is_fk_to(state, other, anchor[0]) for other in others):
                anchors.append(anchor)
        if len({a[0] for a in anchors}) != 1:
            return None
        anchor = anchors[0]
        demoted = [f"{t}.{col}" for t, col in candidates if t != anchor[0]]
        return anchor[0], anchor[1], demoted

    def _is_fk_to(
        self, state: VaultAgentState, candidate: tuple[str, str], anchor_table: str
    ) -> bool:
        column_ref = self._column_ref(state, candidate[0], candidate[1])
        comment = (column_ref.comment or "").lower() if column_ref else ""
        if "fk" not in comment and "foreign key" not in comment:
            return False
        tokens = {normalize_identifier(t) for t in re.findall(r"\w+", comment)}
        return normalize_identifier(anchor_table) in tokens

    @staticmethod
    def _column_index(state: VaultAgentState) -> dict[tuple[str, str], tuple[str, str]]:
        idx: dict[tuple[str, str], tuple[str, str]] = {}
        for table in state.source_schemas:
            for name in table.column_names:
                idx[(normalize_identifier(table.table), normalize_identifier(name))] = (
                    table.table,
                    name,
                )
        return idx

    @staticmethod
    def _column_ref(state: VaultAgentState, table: str, column: str) -> SourceColumn | None:
        for t in state.source_schemas:
            if t.table == table:
                for ref in t.column_refs:
                    if ref.name == column:
                        return ref
        return None

    @staticmethod
    def _category(
        concept: str,
        column: str,
        column_ref: SourceColumn | None,
        profile: ColumnProfile | None,
        kind: str,
    ) -> MappingCategory:
        """Deterministic confidence tier (§7): a category the review queue can gate on,
        more robust than a self-reported number. Order: exact-name > comment-grounded >
        profiled-key > llm-semantic."""
        if normalize_identifier(concept) == normalize_identifier(column):
            return "exact_name"
        if column_ref and column_ref.comment and (_tokens(concept) & _tokens(column_ref.comment)):
            return "comment_grounded"
        if (
            kind == "business_key"
            and profile is not None
            and profile.uniqueness_ratio >= _KEY_UNIQUENESS
            and profile.null_ratio <= _KEY_NULL_TOLERANCE
        ):
            return "profiled_key"
        return "llm_semantic"

    def _rebind_staging(self, state: VaultAgentState) -> None:
        rebind_staging(state)


def source_overrides(state: VaultAgentState) -> dict[str, str]:
    """Map each hub's staging base (normalised) to the source table its key resolved to (§6)."""
    by_concept = {normalize_identifier(p.concept): p.table for p in state.mappings.proposals}
    overrides: dict[str, str] = {}
    for hub in state.dv_model.hubs:
        table = by_concept.get(normalize_identifier(hub.business_key))
        if table:
            base = hub.name
            for prefix in ("hub_", "link_", "sat_"):
                if base.startswith(prefix):
                    base = base[len(prefix):]
                    break
            overrides[normalize_identifier(base)] = table
    return overrides


def rebind_staging(state: VaultAgentState) -> None:
    """Re-generate staging with the ratified/proposed source-table bindings (WP9 §6).

    Idempotent and deterministic: a mapped hub-key binds its staging model to the real source
    table, overriding the WP7 inference and clearing its SOURCE_BINDING flag. A no-op when no
    hub key resolved (so an ungrounded/unmapped run stays byte-identical). Reused by the
    source_mapper (initial pass) and by the HITL resume (after a human edits a binding)."""
    overrides = source_overrides(state)
    if not overrides:
        return
    from vault_agent.agents.staging_generator import build_staging

    result = build_staging(
        state.dv_model,
        state.source_schemas,
        contracts=state.artifacts.contracts,
        source_overrides=overrides,
    )
    # Apply the FULL result (WP9.1 F2) — mirror code_generator so metadata and scaffolding
    # don't keep the pre-rebind bindings. models + scaffolding + the staging metadata block.
    state.artifacts.staging_models = result.models
    state.artifacts.scaffolding = result.scaffolding
    if state.artifacts.automatedv_yaml:
        state.artifacts.automatedv_yaml["staging"] = result.metadata
    # Drop the now-satisfied SOURCE_BINDING flags for overridden specs; keep the rest.
    state.flags = [f for f in state.flags if f.kind != FlagKind.SOURCE_BINDING] + result.flags
