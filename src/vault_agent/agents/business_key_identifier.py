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
from vault_agent.rules.dv2_rules import BUSINESS_KEY_CRITERIA
from vault_agent.state import BusinessKeyCandidate, FlagKind, VaultAgentState

logger = logging.getLogger(__name__)

_TOOL_NAME = "emit_business_keys"
_MAX_TOKENS = 4096


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
        requirements_json = json.dumps(
            [req.model_dump() for req in state.requirements], indent=2
        )
        logger.debug("requirements payload: %d chars", len(requirements_json))
        extractor = self._get_extractor()
        raw_records = await extractor.identify(
            system_prompt=system_prompt, requirements_json=requirements_json
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
