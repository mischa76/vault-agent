"""Unit tests for the shared forced-tool-use call path (ForcedToolCaller).

Run without an API key: the Anthropic client is injected as a stub. Covers the three
hardening behaviours the per-agent extractors delegate here: truncation surfaces as an
error (never a silent empty payload), a missing tool block surfaces as an error, and
transient API failures are retried with backoff while non-retryable ones propagate.
"""
from dataclasses import dataclass
from typing import Any

import anthropic
import httpx
import pytest

from vault_agent.llm import ForcedToolCaller, LLMCallError

_TOOL = "emit_things"


def _tool_block(payload: dict[str, Any] | None = None, name: str = _TOOL) -> Any:
    return anthropic.types.ToolUseBlock(
        type="tool_use", id="toolu_test", name=name, input=payload or {}
    )


def _text_block() -> Any:
    return anthropic.types.TextBlock(type="text", text="no tool call here")


@dataclass
class _Message:
    content: list[Any]
    stop_reason: str = "tool_use"


class _StubMessages:
    def __init__(self, outcomes: list[Any]) -> None:
        # Each outcome is either an Exception to raise or a _Message to return.
        self._outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _Message:
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome  # type: ignore[no-any-return]


class _StubClient:
    def __init__(self, outcomes: list[Any]) -> None:
        self.messages = _StubMessages(outcomes)


def _status_error(status_code: int) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, request=request)
    return anthropic.APIStatusError("boom", response=response, body=None)


_SLEEPS: list[float] = []


async def _no_sleep(seconds: float) -> None:
    _SLEEPS.append(seconds)


def _caller(outcomes: list[Any]) -> tuple[ForcedToolCaller, _StubClient]:
    client = _StubClient(outcomes)
    _SLEEPS.clear()
    return ForcedToolCaller("test-model", client=client, sleep=_no_sleep), client


async def _call(caller: ForcedToolCaller) -> dict[str, Any]:
    return await caller.call(
        tool_name=_TOOL,
        tool_description="emit",
        input_schema={"type": "object"},
        system_prompt="system",
        user_content="user",
        max_tokens=64,
    )


async def test_returns_tool_input_on_success() -> None:
    payload = {"things": [1, 2]}
    caller, client = _caller([_Message(content=[_tool_block(payload)])])

    assert await _call(caller) == payload
    assert client.messages.calls[0]["tool_choice"] == {"type": "tool", "name": _TOOL}


async def test_truncation_raises_instead_of_returning_empty() -> None:
    caller, _ = _caller([_Message(content=[], stop_reason="max_tokens")])

    with pytest.raises(LLMCallError, match="truncated at max_tokens=64"):
        await _call(caller)


async def test_missing_tool_block_raises() -> None:
    caller, _ = _caller([_Message(content=[_text_block()])])

    with pytest.raises(LLMCallError, match="no tool_use block"):
        await _call(caller)


async def test_retries_transient_status_then_succeeds() -> None:
    payload = {"ok": True}
    caller, client = _caller(
        [
            _status_error(429),
            _status_error(529),
            _Message(content=[_tool_block(payload)]),
        ]
    )

    assert await _call(caller) == payload
    assert len(client.messages.calls) == 3
    assert _SLEEPS == [2.0, 4.0]  # exponential backoff between attempts


async def test_retries_connection_error_then_succeeds() -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    caller, client = _caller(
        [
            anthropic.APIConnectionError(request=request),
            _Message(content=[_tool_block()]),
        ]
    )

    assert await _call(caller) == {}
    assert len(client.messages.calls) == 2


async def test_exhausted_retries_raise_llm_call_error() -> None:
    caller, client = _caller([_status_error(429)] * 4)

    with pytest.raises(LLMCallError, match="failed after 4 attempts"):
        await _call(caller)
    assert len(client.messages.calls) == 4


async def test_non_retryable_status_propagates_unchanged() -> None:
    caller, client = _caller([_status_error(400)])

    with pytest.raises(anthropic.APIStatusError):
        await _call(caller)
    assert len(client.messages.calls) == 1  # no retry on a caller error
