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

from vault_agent.llm import ForcedToolCaller, LLMCallError, TraceEvent

_TOOL = "emit_things"


def _tool_block(payload: dict[str, Any] | None = None, name: str = _TOOL) -> Any:
    return anthropic.types.ToolUseBlock(
        type="tool_use", id="toolu_test", name=name, input=payload or {}
    )


def _text_block() -> Any:
    return anthropic.types.TextBlock(type="text", text="no tool call here")


@dataclass
class _Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class _Message:
    content: list[Any]
    stop_reason: str = "tool_use"
    usage: _Usage | None = None


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


async def test_system_prompt_is_sent_as_a_cache_controlled_block() -> None:
    # WP3 prompt caching: the block form with an ephemeral cache_control marker, per the
    # Messages API docs. Below the model's minimum cacheable length the API silently
    # skips caching, so the block is always sent unconditionally.
    caller, client = _caller([_Message(content=[_tool_block()])])

    await _call(caller)

    assert client.messages.calls[0]["system"] == [
        {"type": "text", "text": "system", "cache_control": {"type": "ephemeral"}}
    ]


# --- WP13: usage capture (token/cost transparency) ---------------------------------------


def _recording_caller(
    outcomes: list[Any],
) -> tuple[ForcedToolCaller, _StubClient, list[tuple[str, int, int, int]]]:
    client = _StubClient(outcomes)
    _SLEEPS.clear()
    recorded: list[tuple[str, int, int, int]] = []

    def record(model: str, inp: int, out: int, cache: int) -> None:
        recorded.append((model, inp, out, cache))

    caller = ForcedToolCaller(
        "test-model", client=client, sleep=_no_sleep, usage_recorder=record
    )
    return caller, client, recorded


async def test_usage_recorder_receives_response_usage() -> None:
    usage = _Usage(input_tokens=1200, output_tokens=340, cache_read_input_tokens=900)
    caller, _, recorded = _recording_caller([_Message(content=[_tool_block()], usage=usage)])

    await _call(caller)

    assert recorded == [("test-model", 1200, 340, 900)]


async def test_usage_recorder_defaults_missing_fields_to_zero() -> None:
    # A response without a usage object (a stub, or a partial SDK shape) must not crash the
    # call path — usage capture is observational.
    caller, _, recorded = _recording_caller([_Message(content=[_tool_block()], usage=None)])

    await _call(caller)

    assert recorded == [("test-model", 0, 0, 0)]


async def test_usage_recorded_even_on_truncation() -> None:
    # A truncated response is still billed; its tokens must count toward the totals before
    # the LLMCallError surfaces.
    usage = _Usage(input_tokens=500, output_tokens=4096)
    caller, _, recorded = _recording_caller(
        [_Message(content=[_tool_block()], stop_reason="max_tokens", usage=usage)]
    )

    with pytest.raises(LLMCallError, match="truncated"):
        await _call(caller)
    assert recorded == [("test-model", 500, 4096, 0)]


async def test_no_recorder_is_a_no_op() -> None:
    # The default (no instance recorder, no module recorder) records nothing and behaves
    # exactly as before.
    from vault_agent import llm

    assert llm._default_usage_recorder is None
    caller, client = _caller([_Message(content=[_tool_block({"ok": 1})], usage=_Usage(1, 2, 3))])

    assert await _call(caller) == {"ok": 1}


async def test_module_level_recorder_captures_agent_constructed_callers() -> None:
    # eval.run registers a module-level recorder because the agents build their own callers.
    from vault_agent import llm

    recorded: list[tuple[str, int, int, int]] = []
    llm.set_usage_recorder(lambda *args: recorded.append(args))
    try:
        caller, _ = _caller([_Message(content=[_tool_block()], usage=_Usage(10, 20, 5))])
        await _call(caller)
    finally:
        llm.set_usage_recorder(None)

    assert recorded == [("test-model", 10, 20, 5)]
    assert llm._default_usage_recorder is None  # cleared


# --- WP15: trace capture (content transcript) ---------------------------------------------


def _tracing_caller(outcomes: list[Any]) -> tuple[ForcedToolCaller, list[TraceEvent]]:
    client = _StubClient(outcomes)
    _SLEEPS.clear()
    events: list[TraceEvent] = []
    caller = ForcedToolCaller(
        "test-model", client=client, sleep=_no_sleep, trace_recorder=events.append
    )
    return caller, events


async def test_trace_records_payload_stop_reason_and_usage_on_success() -> None:
    payload = {"hubs": [{"name": "hub_customer"}]}
    caller, events = _tracing_caller(
        [_Message(content=[_tool_block(payload)], usage=_Usage(1200, 340, 900))]
    )

    await _call(caller)

    assert len(events) == 1
    event = events[0]
    assert event.kind == "llm_call"
    assert event.tool_name == _TOOL and event.model == "test-model" and event.attempt == 0
    assert event.payload == payload
    assert event.stop_reason == "tool_use"
    assert (event.input_tokens, event.output_tokens, event.cache_read_tokens) == (1200, 340, 900)
    # llm.py always fills both; dedup is a writer concern.
    assert event.system_prompt == "system" and event.system_prompt_sha
    assert event.user_content == "user" and event.max_tokens == 64


async def test_truncation_traces_the_call_then_the_error() -> None:
    # Usage semantics (WP13): a truncated response is a completed, billed API response — it is
    # traced as a call *and* as the terminal error it causes.
    caller, events = _tracing_caller([_Message(content=[], stop_reason="max_tokens")])

    with pytest.raises(LLMCallError):
        await _call(caller)

    assert [event.kind for event in events] == ["llm_call", "llm_error"]
    assert "truncated at max_tokens=64" in (events[1].error or "")


async def test_missing_tool_block_traces_an_error() -> None:
    caller, events = _tracing_caller([_Message(content=[_text_block()])])

    with pytest.raises(LLMCallError):
        await _call(caller)

    assert [event.kind for event in events] == ["llm_call", "llm_error"]
    assert "no tool_use block" in (events[1].error or "")


async def test_exhausted_retries_trace_one_error_and_no_calls() -> None:
    # A retryable attempt that *will* be retried is not an event — only the terminal outcome.
    caller, events = _tracing_caller([_status_error(429)] * 4)

    with pytest.raises(LLMCallError):
        await _call(caller)

    assert [event.kind for event in events] == ["llm_error"]
    assert "failed after 4 attempts" in (events[0].error or "")


async def test_retried_call_traces_only_the_completed_response() -> None:
    caller, events = _tracing_caller([_status_error(429), _Message(content=[_tool_block()])])

    await _call(caller)

    assert [event.kind for event in events] == ["llm_call"]
    assert events[0].attempt == 1  # the attempt that actually landed


async def test_non_retryable_status_traces_the_terminal_error() -> None:
    # The failure mode that cost WP14.1 a completed repeat (exhausted credit balance is a
    # non-retryable 400): the transcript must show why the run stopped.
    caller, events = _tracing_caller([_status_error(400)])

    with pytest.raises(anthropic.APIStatusError):
        await _call(caller)

    assert [event.kind for event in events] == ["llm_error"]
    assert "APIStatusError" in (events[0].error or "")


async def test_raising_trace_recorder_never_disturbs_the_call() -> None:
    def boom(event: TraceEvent) -> None:
        raise RuntimeError("recorder is broken")

    client = _StubClient([_Message(content=[_tool_block({"ok": 1})])])
    caller = ForcedToolCaller("test-model", client=client, sleep=_no_sleep, trace_recorder=boom)

    assert await _call(caller) == {"ok": 1}  # observational channel, never fatal


async def test_module_level_trace_recorder_and_instance_override() -> None:
    from vault_agent import llm

    module_events: list[TraceEvent] = []
    instance_events: list[TraceEvent] = []
    llm.set_trace_recorder(module_events.append)
    try:
        caller, _ = _caller([_Message(content=[_tool_block()])])
        await _call(caller)  # no instance recorder -> module default
        override = ForcedToolCaller(
            "test-model",
            client=_StubClient([_Message(content=[_tool_block()])]),
            sleep=_no_sleep,
            trace_recorder=instance_events.append,
        )
        await _call(override)
    finally:
        llm.set_trace_recorder(None)

    assert len(module_events) == 1 and len(instance_events) == 1  # override wins, no duplicate
    assert llm._default_trace_recorder is None  # cleared
