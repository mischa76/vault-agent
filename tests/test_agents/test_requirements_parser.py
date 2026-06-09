"""Unit tests for the Requirements Parser agent.

The LLM call is stubbed via the ``RequirementExtractor`` protocol so these tests run in
CI without an Anthropic API key (``asyncio_mode = auto`` runs the async tests directly).
"""
from pathlib import Path
from typing import Any

from vault_agent.agents.requirements_parser import RequirementsParserAgent
from vault_agent.state import ParsedRequirement, VaultAgentState

EXAMPLE_DOC = (
    Path(__file__).parents[2] / "examples" / "inputs" / "bank_account_requirements.md"
)


class StubExtractor:
    """Returns a canned payload and records how it was called."""

    def __init__(self, payload: list[dict[str, Any]]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    async def extract(
        self, *, system_prompt: str, document: str
    ) -> list[dict[str, Any]]:
        self.calls.append((system_prompt, document))
        return self.payload


def _valid_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": "REQ-001",
            "text": "A customer can open one or more accounts.",
            "category": "functional",
            "actor": "customer",
            "action": "open",
            "obj": "account",
        },
        {
            "id": "REQ-002",
            "text": "All balance changes must be auditable.",
            "category": "constraint",
        },
    ]


async def test_parses_requirements_from_example_document() -> None:
    stub = StubExtractor(_valid_payload())
    agent = RequirementsParserAgent(extractor=stub)
    state = VaultAgentState(input_documents=[str(EXAMPLE_DOC)])

    result = await agent.run(state)

    assert len(result.requirements) == 2
    assert all(isinstance(r, ParsedRequirement) for r in result.requirements)
    assert result.requirements[0].id == "REQ-001"
    assert result.requirements[0].actor == "customer"
    assert result.requirements[1].actor is None
    assert not result.errors

    # The real document was read from disk and handed to the LLM, alongside the prompt.
    assert len(stub.calls) == 1
    system_prompt, document = stub.calls[0]
    assert "Requirements Parser" in system_prompt
    assert "national customer ID" in document

    # An audit trail entry is recorded.
    assert result.decisions[-1]["agent"] == "requirements_parser"
    assert result.decisions[-1]["requirements_extracted"] == 2


async def test_invalid_records_are_skipped_and_logged() -> None:
    payload = _valid_payload() + [{"id": "REQ-003", "text": "missing category"}]
    stub = StubExtractor(payload)
    agent = RequirementsParserAgent(extractor=stub)
    state = VaultAgentState(input_documents=[str(EXAMPLE_DOC)])

    result = await agent.run(state)

    assert len(result.requirements) == 2
    assert len(result.errors) == 1
    assert "dropped invalid record" in result.errors[0]


async def test_missing_input_file_is_reported() -> None:
    stub = StubExtractor(_valid_payload())
    agent = RequirementsParserAgent(extractor=stub)
    state = VaultAgentState(input_documents=["does/not/exist.md"])

    result = await agent.run(state)

    assert result.requirements == []
    assert len(result.errors) == 1
    assert "not found" in result.errors[0]
    # Extractor must not be called when there is no document to parse.
    assert stub.calls == []
