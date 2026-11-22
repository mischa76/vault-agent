"""Unit tests for the Business Key Identifier agent.

The LLM call is stubbed via the ``BusinessKeyExtractor`` protocol so these tests run in
CI without an Anthropic API key (``asyncio_mode = auto`` runs the async tests directly).
"""
import json
from typing import Any

from vault_agent.agents.business_key_identifier import (
    BusinessKeyIdentifierAgent,
    merge_candidates,
    split_requirements,
)
from vault_agent.llm import LLMCallError
from vault_agent.rules.dv2_rules import BUSINESS_KEY_CRITERIA
from vault_agent.state import (
    BusinessKeyCandidate,
    FlagKind,
    ParsedRequirement,
    SourceTable,
    VaultAgentState,
)


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
    assert not result.flags

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
    assert len(result.flags) == 1
    assert "dropped invalid candidate" in result.flags[0].message


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
    assert len(result.flags) == 1
    assert "out-of-range score" in result.flags[0].message


async def test_no_requirements_short_circuits_without_calling_llm() -> None:
    stub = StubExtractor(_valid_payload())
    agent = BusinessKeyIdentifierAgent(extractor=stub)
    state = VaultAgentState()  # no requirements

    result = await agent.run(state)

    assert result.business_keys == []
    assert len(result.flags) == 1
    assert "no requirements" in result.flags[0].message
    assert stub.calls == []  # the LLM must not be called


async def test_no_source_schema_keeps_prompt_ungrounded() -> None:
    # Regression guard: with no declared schema the system prompt carries no schema section.
    stub = StubExtractor(_valid_payload())
    agent = BusinessKeyIdentifierAgent(extractor=stub)

    await agent.run(_state_with_requirements())

    system_prompt, _ = stub.calls[0]
    assert "Known source columns" not in system_prompt


async def test_source_schema_is_injected_into_prompt() -> None:
    # Phase 2 grounding (ADR-0004): declared columns are rendered into the system prompt.
    stub = StubExtractor(_valid_payload())
    agent = BusinessKeyIdentifierAgent(extractor=stub)
    state = _state_with_requirements()
    state.source_schemas = [
        SourceTable(table="customer", columns=["national_customer_id", "customer_name"]),
    ]

    await agent.run(state)

    system_prompt, _ = stub.calls[0]
    assert "Known source columns" in system_prompt
    assert "national_customer_id" in system_prompt
    assert "**customer**" in system_prompt


# --- adaptive segmentation ----------------------------------------------------------
# This agent's output scales with the number of business entities, so a large landscape
# overflows the budget even though each record is small: scale_100 died here with
# "emit_business_keys: response truncated at max_tokens=4096" on 2026-07-27, one agent
# past the requirements parser that had just been fixed for the same class of failure.


def _requirements(count: int) -> list[ParsedRequirement]:
    return [
        ParsedRequirement(id=f"REQ-{i:03d}", text=f"entity {i} has a key", category="business-rule")
        for i in range(count)
    ]


class TruncatingExtractor:
    """Truncates while the payload holds more than ``fits_under`` requirements."""

    def __init__(self, fits_under: int) -> None:
        self.fits_under = fits_under
        self.payloads: list[str] = []

    async def identify(
        self, *, system_prompt: str, requirements_json: str
    ) -> list[dict[str, Any]]:
        self.payloads.append(requirements_json)
        records = json.loads(requirements_json)
        if len(records) > self.fits_under:
            raise LLMCallError("truncated at max_tokens", truncated=True)
        return [
            {
                "entity": r["text"].split()[1],  # "entity <n> has a key"
                "field": "id",
                "score": 0.9,
                "rationale": "synthetic",
            }
            for r in records
        ]


def test_split_requirements_halves_and_stops_at_one() -> None:
    reqs = _requirements(5)
    halves = split_requirements(reqs)
    assert halves is not None
    head, tail = halves
    assert len(head) == 2 and len(tail) == 3  # order preserved, nothing lost
    assert head + tail == reqs
    assert split_requirements(reqs[:1]) is None


def test_merge_candidates_drops_repeats_of_the_same_key() -> None:
    seg_a = [
        {"entity": "customer", "field": "national customer ID", "score": 0.9, "rationale": "a"}
    ]
    seg_b = [
        # same key, normalised differently — the first proposal wins
        {"entity": "CUSTOMER", "field": "NATIONAL_CUSTOMER_ID", "score": 0.4, "rationale": "b"},
        {"entity": "account", "field": "account number", "score": 0.8, "rationale": "c"},
    ]
    merged, dropped = merge_candidates([seg_a, seg_b])
    assert [r["entity"] for r in merged] == ["customer", "account"]
    assert merged[0]["rationale"] == "a"  # first wins
    assert dropped == 1


def test_merge_candidates_is_identity_for_one_segment() -> None:
    records = [{"entity": "customer", "field": "id", "score": 0.9, "rationale": "r"}]
    merged, dropped = merge_candidates([records])
    assert merged == records and dropped == 0


async def test_unsegmented_run_makes_one_call_and_no_flag() -> None:
    """Regression guard: a payload that already fits is byte-identical to pre-fix behaviour."""
    stub = StubExtractor([{"entity": "customer", "field": "id", "score": 0.9, "rationale": "r"}])
    agent = BusinessKeyIdentifierAgent(extractor=stub)

    result = await agent.run(_state_with_requirements())

    assert len(stub.calls) == 1
    assert not [f for f in result.flags if f.kind == FlagKind.INPUT_SEGMENTED]
    assert len(result.business_keys) == 1


async def test_truncated_response_splits_the_requirement_list() -> None:
    extractor = TruncatingExtractor(fits_under=3)
    agent = BusinessKeyIdentifierAgent(extractor=extractor)
    state = VaultAgentState(requirements=_requirements(6))

    result = await agent.run(state)

    # one failed whole-list attempt, then the two halves of 3 succeed
    assert len(extractor.payloads) == 3
    assert [len(json.loads(p)) for p in extractor.payloads] == [6, 3, 3]
    assert len(result.business_keys) == 6  # every requirement contributed a candidate
    [flag] = [f for f in result.flags if f.kind == FlagKind.INPUT_SEGMENTED]
    assert flag.severity == "advisory"
    assert "2 segment(s)" in flag.message
