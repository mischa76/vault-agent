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
from typing import Any, Protocol, cast

from pydantic import ValidationError

from vault_agent.agents.base import BaseAgent
from vault_agent.rules.dv2_rules import BUSINESS_KEY_CRITERIA
from vault_agent.state import BusinessKeyCandidate, VaultAgentState

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
    """Default extractor backed by the Anthropic Messages API (forced tool-use)."""

    def __init__(self, model: str | None = None) -> None:
        # Imported lazily so importing this module never requires an API key.
        from anthropic import AsyncAnthropic

        from vault_agent.config import get_settings

        settings = get_settings()
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = model or settings.primary_model

    async def identify(
        self, *, system_prompt: str, requirements_json: str
    ) -> list[dict[str, Any]]:
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            tools=[
                {
                    "name": _TOOL_NAME,
                    "description": "Emit the business key candidates for the requirements.",
                    "input_schema": _tool_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
            messages=[{"role": "user", "content": requirements_json}],
        )
        for block in message.content:
            if block.type == "tool_use" and block.name == _TOOL_NAME:
                payload = cast(dict[str, Any], block.input)
                records = payload.get("business_keys", [])
                return list(records)
        return []


class BusinessKeyIdentifierAgent(BaseAgent):
    """Proposes ranked business key candidates from the parsed requirements."""

    prompt_path = "business_key_identifier.md"  # type: ignore[assignment]

    def __init__(self, extractor: BusinessKeyExtractor | None = None) -> None:
        self._extractor = extractor

    def _get_extractor(self) -> BusinessKeyExtractor:
        if self._extractor is None:
            self._extractor = AnthropicBusinessKeyExtractor()
        return self._extractor

    def _build_system_prompt(self) -> str:
        """Load the prompt template and inject the DV2 business-key criteria."""
        template = self.load_prompt()
        criteria = "\n".join(f"- {criterion}" for criterion in BUSINESS_KEY_CRITERIA)
        return f"{template}\n\n## Business key criteria to apply\n\n{criteria}\n"

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        if not state.requirements:
            state.errors.append(
                "business_key_identifier: no requirements in state; run the "
                "requirements parser first"
            )
            return state

        system_prompt = self._build_system_prompt()
        requirements_json = json.dumps(
            [req.model_dump() for req in state.requirements], indent=2
        )
        extractor = self._get_extractor()
        raw_records = await extractor.identify(
            system_prompt=system_prompt, requirements_json=requirements_json
        )

        candidates: list[BusinessKeyCandidate] = []
        for record in raw_records:
            try:
                candidate = BusinessKeyCandidate.model_validate(record)
            except ValidationError as exc:
                state.errors.append(
                    f"business_key_identifier: dropped invalid candidate: "
                    f"{exc.error_count()} error(s)"
                )
                continue
            if not 0.0 <= candidate.score <= 1.0:
                state.errors.append(
                    f"business_key_identifier: dropped candidate "
                    f"{candidate.entity}.{candidate.field!r} with out-of-range "
                    f"score {candidate.score}"
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
