"""Unit tests for the Business Key Identifier agent.

The LLM call is stubbed via the ``BusinessKeyExtractor`` protocol so these tests run in
CI without an Anthropic API key (``asyncio_mode = auto`` runs the async tests directly).
"""
from typing import Any

from vault_agent.agents.business_key_identifier import BusinessKeyIdentifierAgent
from vault_agent.rules.dv2_rules import BUSINESS_KEY_CRITERIA
from vault_agent.state import BusinessKeyCandidate, ParsedRequirement, VaultAgentState


class StubExtractor:
    """Returns a canned payload and records how it was called."""

    def __init__(self, payload: list[dict[str, Any]]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    async def identify(
        self, *, system_prompt: str, requirements_json: str
    ) -> list[dict[str, Any]]:
        self.calls.append((system_prompt, requirements_json))
        return self.payload


def _state_with_requirements() -> VaultAgentState:
    return VaultAgentState(
        requirements=[
            ParsedRequirement(
                id="REQ-007",
                text="A customer must be identified by a national customer ID.",
                category="business-rule",
                obj="customer",
            ),
            ParsedRequirement(
                id="REQ-004",
                text="Each account must have a unique account number issued by the bank.",
                category="business-rule",
                obj="account",
            ),
        ]
    )


def _valid_payload() -> list[dict[str, Any]]:
    return [
        {
            "entity": "customer",
            "field": "national customer ID",
            "score": 0.95,
            "rationale": "REQ-007 states the customer is identified by it; stable and unique.",
        },
        {
            "entity": "account",
            "field": "account number",
            "score": 0.9,
            "rationale": "REQ-004 calls it unique and bank-issued.",
        },
    ]


async def test_proposes_business_keys_from_requirements() -> None:
    stub = StubExtractor(_valid_payload())
    agent = BusinessKeyIdentifierAgent(extractor=stub)
    state = _state_with_requirements()

    result = await agent.run(state)

    assert len(result.business_keys) == 2
    assert all(isinstance(c, BusinessKeyCandidate) for c in result.business_keys)
    assert result.business_keys[0].entity == "customer"
    assert result.business_keys[0].field == "national customer ID"
    assert not result.errors

    # The agent injected the DV2 criteria into the prompt and passed the requirements.
    assert len(stub.calls) == 1
    system_prompt, requirements_json = stub.calls[0]
    assert BUSINESS_KEY_CRITERIA[0] in system_prompt
    assert "national customer ID" in requirements_json

    assert result.decisions[-1]["agent"] == "business_key_identifier"
    assert result.decisions[-1]["candidates_proposed"] == 2


async def test_invalid_candidate_is_skipped_and_logged() -> None:
    payload = _valid_payload() + [{"entity": "account", "field": "balance"}]  # no score/rationale
    stub = StubExtractor(payload)
    agent = BusinessKeyIdentifierAgent(extractor=stub)

    result = await agent.run(_state_with_requirements())

    assert len(result.business_keys) == 2
    assert len(result.errors) == 1
    assert "dropped invalid candidate" in result.errors[0]


async def test_out_of_range_score_is_dropped() -> None:
    payload = [
        {
            "entity": "customer",
            "field": "national customer ID",
            "score": 1.5,
            "rationale": "over-confident model output",
        }
    ]
    stub = StubExtractor(payload)
    agent = BusinessKeyIdentifierAgent(extractor=stub)

    result = await agent.run(_state_with_requirements())

    assert result.business_keys == []
    assert len(result.errors) == 1
    assert "out-of-range score" in result.errors[0]


async def test_no_requirements_short_circuits_without_calling_llm() -> None:
    stub = StubExtractor(_valid_payload())
    agent = BusinessKeyIdentifierAgent(extractor=stub)
    state = VaultAgentState()  # no requirements

    result = await agent.run(state)

    assert result.business_keys == []
    assert len(result.errors) == 1
    assert "no requirements" in result.errors[0]
    assert stub.calls == []  # the LLM must not be called
