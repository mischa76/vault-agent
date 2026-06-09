"""Requirements Parser agent.

Reads the raw requirements documents listed in ``VaultAgentState.input_documents`` and
extracts an atomic, IREB-aligned list of ``ParsedRequirement`` records into
``VaultAgentState.requirements``.

Structured output is obtained via Anthropic tool-use: the model is forced to call the
``emit_requirements`` tool whose input schema is derived from ``ParsedRequirement`` itself,
so the returned payload validates back into the pydantic model with no ad-hoc parsing.

The Anthropic client is only constructed lazily (and ``config.settings`` only imported
then), so unit tests can inject a stub extractor and run without an API key.
"""
from pathlib import Path
from typing import Any, Protocol, cast

from pydantic import ValidationError

from vault_agent.agents.base import BaseAgent
from vault_agent.state import ParsedRequirement, VaultAgentState

_TOOL_NAME = "emit_requirements"
_MAX_TOKENS = 4096


def _tool_schema() -> dict[str, Any]:
    """Wrap the ParsedRequirement JSON schema as an array-valued tool input."""
    item_schema = ParsedRequirement.model_json_schema()
    return {
        "type": "object",
        "properties": {
            "requirements": {
                "type": "array",
                "items": item_schema,
                "description": "One entry per atomic requirement found in the document.",
            }
        },
        "required": ["requirements"],
    }


class RequirementExtractor(Protocol):
    """Turns a single document into a list of raw requirement records.

    Implemented for real by :class:`AnthropicRequirementExtractor`; stubbed in tests.
    """

    async def extract(
        self, *, system_prompt: str, document: str
    ) -> list[dict[str, Any]]: ...


class AnthropicRequirementExtractor:
    """Default extractor backed by the Anthropic Messages API (forced tool-use)."""

    def __init__(self, model: str | None = None) -> None:
        # Imported lazily so importing this module never requires an API key.
        from anthropic import AsyncAnthropic

        from vault_agent.config import settings

        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = model or settings.primary_model

    async def extract(
        self, *, system_prompt: str, document: str
    ) -> list[dict[str, Any]]:
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            tools=[
                {
                    "name": _TOOL_NAME,
                    "description": "Emit the structured requirements extracted from the document.",
                    "input_schema": _tool_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
            messages=[{"role": "user", "content": document}],
        )
        for block in message.content:
            if block.type == "tool_use" and block.name == _TOOL_NAME:
                payload = cast(dict[str, Any], block.input)
                records = payload.get("requirements", [])
                return list(records)
        return []


class RequirementsParserAgent(BaseAgent):
    """Extracts structured requirements from the input documents."""

    prompt_path = "requirements_parser.md"  # type: ignore[assignment]

    def __init__(self, extractor: RequirementExtractor | None = None) -> None:
        self._extractor = extractor

    def _get_extractor(self) -> RequirementExtractor:
        if self._extractor is None:
            self._extractor = AnthropicRequirementExtractor()
        return self._extractor

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        system_prompt = self.load_prompt()
        extractor = self._get_extractor()

        requirements: list[ParsedRequirement] = []
        for doc_path in state.input_documents:
            document = self._read_document(doc_path, state)
            if document is None:
                continue
            raw_records = await extractor.extract(
                system_prompt=system_prompt, document=document
            )
            for record in raw_records:
                try:
                    requirements.append(ParsedRequirement.model_validate(record))
                except ValidationError as exc:
                    state.errors.append(
                        f"requirements_parser: dropped invalid record from "
                        f"{doc_path!r}: {exc.error_count()} error(s)"
                    )

        state.requirements = requirements
        state.decisions.append(
            {
                "agent": "requirements_parser",
                "documents": list(state.input_documents),
                "requirements_extracted": len(requirements),
            }
        )
        return state

    @staticmethod
    def _read_document(doc_path: str, state: VaultAgentState) -> str | None:
        path = Path(doc_path)
        if not path.is_file():
            state.errors.append(
                f"requirements_parser: input document not found: {doc_path!r}"
            )
            return None
        return path.read_text(encoding="utf-8")
