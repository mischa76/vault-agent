"""Business Key Identifier agent.

Reads the structured requirements in ``VaultAgentState.requirements`` and proposes Data
Vault business key candidates — the natural identifiers a hub will be built around —
writing them to ``VaultAgentState.business_keys``.

The DV2 business-key heuristics are NOT hard-coded in the prompt (see CLAUDE.md): they
live in ``vault_agent.rules.dv2_rules`` and are injected into the system prompt at
runtime, so the rule set keeps a single source of truth.

Structured output uses forced Anthropic tool-use with a schema derived from
``BusinessKeyCandidate``; the client is constructed lazily so tests run without a key.
"""
import json
import logging
from typing import Any, Protocol

from pydantic import ValidationError

from vault_agent.agents.base import BaseAgent
from vault_agent.grounding import render_schema_prompt_section
from vault_agent.llm import call_with_truncation_split
from vault_agent.rules.dv2_rules import BUSINESS_KEY_CRITERIA, normalize_identifier
from vault_agent.state import (
    BusinessKeyCandidate,
    FlagKind,
    ParsedRequirement,
    VaultAgentState,
)

logger = logging.getLogger(__name__)

_TOOL_NAME = "emit_business_keys"
_MAX_TOKENS = 8192


def split_requirements(
    requirements: list[ParsedRequirement],
) -> tuple[list[ParsedRequirement], list[ParsedRequirement]] | None:
    """Halve the requirement list; ``None`` when a single requirement is left.

    The unit of work here is a list, not prose, so the split is exact — no boundary
    search, and nothing can be severed. Order is preserved within each half so the
    candidates come back in a stable order."""
    if len(requirements) < 2:
        return None
    midpoint = len(requirements) // 2
    return requirements[:midpoint], requirements[midpoint:]


def merge_candidates(
    segments: list[list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], int]:
    """Concatenate per-segment candidates, dropping repeats of the same (entity, field).

    Two segments can propose the same key when the entity is described in both halves of
    the requirement list; the first proposal wins (order-preserving and deterministic —
    picking "the better score" would need a tie-break the model cannot justify). A no-op
    for a single segment, so an unsplit run round-trips byte-identically. Returns the
    merged records and the number dropped."""
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    dropped = 0
    for records in segments:
        for record in records:
            key = (
                normalize_identifier(str(record.get("entity", ""))),
                normalize_identifier(str(record.get("field", ""))),
            )
            if key in seen:
                dropped += 1
                continue
            seen.add(key)
            merged.append(record)
    return merged, dropped


def _tool_schema() -> dict[str, Any]:
    """Wrap the BusinessKeyCandidate JSON schema as an array-valued tool input."""
    item_schema = BusinessKeyCandidate.model_json_schema()
    return {
        "type": "object",
        "properties": {
            "business_keys": {
                "type": "array",
                "items": item_schema,
                "description": "One entry per proposed business key candidate.",
            }
        },
        "required": ["business_keys"],
    }


class BusinessKeyExtractor(Protocol):
    """Turns the requirements into a list of raw business key records.

    Implemented for real by :class:`AnthropicBusinessKeyExtractor`; stubbed in tests.
    """

    async def identify(
        self, *, system_prompt: str, requirements_json: str
    ) -> list[dict[str, Any]]: ...


class AnthropicBusinessKeyExtractor:
    """Default extractor backed by the shared forced-tool-use call path."""

    def __init__(self, model: str | None = None) -> None:
        # Imported lazily so importing this module never requires an API key.
        from vault_agent.config import get_settings
        from vault_agent.llm import ForcedToolCaller

        self._caller = ForcedToolCaller(model or get_settings().primary_model)

    async def identify(
        self, *, system_prompt: str, requirements_json: str
    ) -> list[dict[str, Any]]:
        payload = await self._caller.call(
            tool_name=_TOOL_NAME,
            tool_description="Emit the business key candidates for the requirements.",
            input_schema=_tool_schema(),
            system_prompt=system_prompt,
            user_content=requirements_json,
            max_tokens=_MAX_TOKENS,
        )
        return list(payload.get("business_keys", []))


class BusinessKeyIdentifierAgent(BaseAgent):
    """Proposes ranked business key candidates from the parsed requirements."""

    prompt_path = "business_key_identifier.md"

    def __init__(self, extractor: BusinessKeyExtractor | None = None) -> None:
        self._extractor = extractor

    def _get_extractor(self) -> BusinessKeyExtractor:
        if self._extractor is None:
            self._extractor = AnthropicBusinessKeyExtractor()
        return self._extractor

    def _build_system_prompt(self, state: VaultAgentState) -> str:
        """Load the prompt template, inject the DV2 business-key criteria, and (when a source
        schema is declared) the known source columns to ground candidates (ADR-0004)."""
        template = self.load_prompt()
        criteria = "\n".join(f"- {criterion}" for criterion in BUSINESS_KEY_CRITERIA)
        schema_section = render_schema_prompt_section(state.source_schemas)
        return f"{template}\n\n## Business key criteria to apply\n\n{criteria}\n{schema_section}"

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        logger.info(
            "identifying business keys from %d requirement(s)", len(state.requirements)
        )
        if not state.requirements:
            state.flag(
                "business_key_identifier",
                "no requirements in state; run the requirements parser first",
                severity="error",
                kind=FlagKind.MISSING_INPUT,
            )
            return state

        system_prompt = self._build_system_prompt(state)
        extractor = self._get_extractor()

        async def identify(chunk: list[ParsedRequirement]) -> list[dict[str, Any]]:
            payload = json.dumps([req.model_dump() for req in chunk], indent=2)
            logger.debug("requirements payload: %d chars", len(payload))
            return await extractor.identify(
                system_prompt=system_prompt, requirements_json=payload
            )

        # Same truncation-driven segmentation as the requirements parser: this agent's
        # output scales with the number of business entities, so a large landscape
        # overflows the budget even though each individual record is small. The whole
        # list is tried first, so a normal run is one call with unchanged content.
        segments = await call_with_truncation_split(
            identify, list(state.requirements), split_requirements
        )
        raw_records, dropped = merge_candidates(segments)
        if len(segments) > 1:
            logger.info(
                "business keys identified over %d segment(s), %d duplicate(s) dropped",
                len(segments),
                dropped,
            )
            state.flag(
                "business_key_identifier",
                f"the {len(state.requirements)} requirement(s) did not fit one model "
                f"response; business keys were identified over {len(segments)} segment(s) "
                f"of the requirement list — a key spanning segments may be proposed from "
                f"partial context, so review the candidate set",
                kind=FlagKind.INPUT_SEGMENTED,
            )

        candidates: list[BusinessKeyCandidate] = []
        for record in raw_records:
            try:
                candidate = BusinessKeyCandidate.model_validate(record)
            except ValidationError as exc:
                state.flag(
                    "business_key_identifier",
                    f"dropped invalid candidate: {exc.error_count()} error(s)",
                    kind=FlagKind.DROPPED_RECORD,
                )
                continue
            if not 0.0 <= candidate.score <= 1.0:
                state.flag(
                    "business_key_identifier",
                    f"dropped candidate {candidate.entity}.{candidate.field!r} with "
                    f"out-of-range score {candidate.score}",
                    kind=FlagKind.DROPPED_RECORD,
                    asset=f"{candidate.entity}.{candidate.field}",
                )
                continue
            candidates.append(candidate)

        state.business_keys = candidates
        state.decisions.append(
            {
                "agent": "business_key_identifier",
                "requirements_considered": len(state.requirements),
                "candidates_proposed": len(candidates),
            }
        )
        return state
