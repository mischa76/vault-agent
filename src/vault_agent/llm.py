"""Shared Anthropic forced-tool-use call path for the LLM agents.

One place for the concerns every extractor shares: constructing the client lazily (so
importing an agent module never requires an API key), forcing the single tool call,
verifying the response actually contains the tool block, surfacing truncation
(``stop_reason == "max_tokens"``) instead of silently returning an empty payload, and
retrying transient API failures (429/5xx/timeouts) with exponential backoff.

The per-agent extractor classes stay — they own their tool name, schema, and payload
unwrapping — but delegate the call itself to :class:`ForcedToolCaller`, so a fix here
hardens every LLM call in the pipeline at once.
"""
import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, cast

import anthropic

logger = logging.getLogger(__name__)

# Transient statuses worth retrying: timeout, rate limit, server errors, overloaded.
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 529})
_MAX_RETRIES = 3
_BASE_DELAY_SECONDS = 2.0

# Token/cost capture (WP13 §3): a callback fired once per completed API response with
# ``(model, input_tokens, output_tokens, cache_read_tokens)`` from ``response.usage``.
# Purely observational — in-memory, no behaviour change when unset. The agents construct
# their own callers, so a *module-level* default lets a harness (eval.run) capture usage
# across every agent without threading a recorder through each constructor; per-instance
# injection (the ``usage_recorder`` ctor arg) is for tests.
UsageRecorder = Callable[[str, int, int, int], None]

_default_usage_recorder: UsageRecorder | None = None


def set_usage_recorder(recorder: UsageRecorder | None) -> None:
    """Register (or clear with ``None``) the process-wide default usage recorder."""
    global _default_usage_recorder
    _default_usage_recorder = recorder


# Trace capture (WP15): the *content* channel next to WP13's usage (count) channel. Every
# completed API response and every terminal call failure is offered to a recorder, so a run
# leaves a grep-able transcript behind instead of having to be re-run with ad-hoc prints.
# Same seam shape as the usage recorder: a module-level default (the CLI/eval harness sets it,
# library code never does) plus a per-instance ctor arg for tests.
@dataclass(frozen=True)
class TraceEvent:
    """One observable moment in the pipeline's LLM interaction.

    ``llm_call`` is a completed API response (including a truncated one — matching the usage
    semantics), ``llm_error`` a terminal failure (truncation, missing tool block, exhausted
    retries; a retryable attempt that *will* be retried is not an event), ``backstop`` a
    deterministic repair of LLM output firing (WP16 §2.3).

    ``system_prompt`` is always filled — deduplication by ``system_prompt_sha`` is purely a
    writer concern (:mod:`vault_agent.trace`), so a recorder that wants the full text has it."""

    kind: Literal["llm_call", "llm_error", "backstop"]
    tool_name: str = ""
    model: str = ""
    attempt: int = 0
    system_prompt_sha: str = ""
    system_prompt: str = ""
    user_content: str = ""
    max_tokens: int = 0
    payload: dict[str, Any] | None = None
    stop_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    error: str | None = None
    # WP16 backstop events: which repair fired, and on what.
    backstop_id: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


TraceRecorder = Callable[[TraceEvent], None]

_default_trace_recorder: TraceRecorder | None = None


def set_trace_recorder(recorder: TraceRecorder | None) -> None:
    """Register (or clear with ``None``) the process-wide default trace recorder."""
    global _default_trace_recorder
    _default_trace_recorder = recorder


def emit_trace(event: TraceEvent, recorder: TraceRecorder | None = None) -> None:
    """Offer ``event`` to ``recorder`` (else the module default); never disturb the caller.

    Tracing is observational: a broken recorder must not take a pipeline down, so any recorder
    exception is swallowed with a warning. No recorder set → a cheap no-op, which is what the
    keyless test suite and every un-instrumented run see."""
    sink = recorder or _default_trace_recorder
    if sink is None:
        return
    try:
        sink(event)
    except Exception:  # noqa: BLE001 - observational channel, never fatal
        logger.warning("trace recorder failed for a %s event", event.kind, exc_info=True)


def prompt_sha(system_prompt: str) -> str:
    """Short stable digest of a system prompt (the writer's dedup key)."""
    return hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:16]


class LLMCallError(RuntimeError):
    """A forced tool call failed in a way the pipeline must not silently absorb.

    Raised for truncated responses (the tool payload would be incomplete), responses
    without the forced tool block, and transient API failures that persist past the
    retry budget. Callers must NOT treat this as "the model found nothing" — that case
    is a *successful* call with an empty payload.

    ``truncated`` marks the first of those causes, so a caller that can react to it (the
    requirements parser splits its document and retries) branches on the attribute rather
    than matching the message text."""

    def __init__(self, *args: object, truncated: bool = False) -> None:
        super().__init__(*args)
        self.truncated = truncated


class ForcedToolCaller:
    """Calls the Anthropic Messages API forcing one tool; returns the tool's input.

    ``client`` and ``sleep`` are injectable for tests; by default a real
    ``AsyncAnthropic`` client is built from the settings (lazily, at construction)."""

    def __init__(
        self,
        model: str,
        client: Any | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        usage_recorder: UsageRecorder | None = None,
        trace_recorder: TraceRecorder | None = None,
    ) -> None:
        if client is None:
            # Imported here so module import never requires an API key.
            from vault_agent.config import get_settings

            settings = get_settings()
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._client = client
        self._model = model
        self._sleep = sleep or asyncio.sleep
        self._usage_recorder = usage_recorder
        self._trace_recorder = trace_recorder

    async def call(
        self,
        *,
        tool_name: str,
        tool_description: str,
        input_schema: dict[str, Any],
        system_prompt: str,
        user_content: str,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Force ``tool_name`` and return its input payload as a dict.

        Retries transient failures with exponential backoff; raises
        :class:`LLMCallError` on truncation, a missing tool block, or when the retry
        budget is exhausted. Non-retryable API errors (4xx) propagate unchanged."""
        logger.debug(
            "%s: forced call of tool %r (system=%d chars, user=%d chars)",
            self._model,
            tool_name,
            len(system_prompt),
            len(user_content),
        )
        # Shared identity of every event this call emits (WP15): the writer dedups the system
        # prompt by sha, so the modeler's byte-identical retries stay readable and small.
        sha = prompt_sha(system_prompt)

        def event(kind: Literal["llm_call", "llm_error"], attempt: int, **extra: Any) -> None:
            emit_trace(
                TraceEvent(
                    kind=kind,
                    tool_name=tool_name,
                    model=self._model,
                    attempt=attempt,
                    system_prompt_sha=sha,
                    system_prompt=system_prompt,
                    user_content=user_content,
                    max_tokens=max_tokens,
                    **extra,
                ),
                self._trace_recorder,
            )

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            if attempt:
                await self._sleep(_BASE_DELAY_SECONDS * 2 ** (attempt - 1))
            try:
                message = await self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    # Prompt caching (WP3): the system prompt is byte-identical across
                    # modeling retries (and across documents within a run), so mark it as
                    # a cache breakpoint. The tools array precedes system in the cached
                    # prefix automatically. Below the model's minimum cacheable length
                    # the block is silently not cached — no conditional needed.
                    system=[
                        {
                            "type": "text",
                            "text": system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tools=[
                        {
                            "name": tool_name,
                            "description": tool_description,
                            "input_schema": input_schema,
                        }
                    ],
                    tool_choice={"type": "tool", "name": tool_name},
                    messages=[{"role": "user", "content": user_content}],
                )
            except anthropic.APIConnectionError as exc:  # includes APITimeoutError
                last_exc = exc
                continue
            except anthropic.APIStatusError as exc:
                if exc.status_code not in _RETRYABLE_STATUS:
                    # A propagating 4xx (exhausted credit balance, bad request) is a terminal
                    # outcome of this call — trace it before it leaves. Beyond the WP15 §2.1
                    # list, but the same rule: the transcript must show why a run stopped.
                    event("llm_error", attempt, error=f"{type(exc).__name__}: {exc}")
                    raise
                last_exc = exc
                continue

            # Record usage the moment a response lands — before the truncation check, so a
            # truncated (but billed) call still counts toward the cost totals.
            self._record_usage(message)
            payload = self._tool_payload(message, tool_name)
            usage = getattr(message, "usage", None)
            event(
                "llm_call",
                attempt,
                payload=payload,
                stop_reason=message.stop_reason,
                input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
                cache_read_tokens=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
            )

            # A truncated response means an incomplete (or absent) tool payload; falling
            # through would be indistinguishable from "the model found nothing" and
            # would burn a modeling retry on garbage.
            if message.stop_reason == "max_tokens":
                error = (
                    f"{tool_name}: response truncated at max_tokens={max_tokens}; "
                    f"the tool payload is incomplete (raise the limit or shrink the input)"
                )
                event("llm_error", attempt, error=error, stop_reason=message.stop_reason)
                raise LLMCallError(error, truncated=True)
            if payload is not None:
                return payload
            error = (
                f"{tool_name}: no tool_use block in the response "
                f"(stop_reason={message.stop_reason!r})"
            )
            event("llm_error", attempt, error=error, stop_reason=message.stop_reason)
            raise LLMCallError(error)

        error = f"{tool_name}: API call failed after {_MAX_RETRIES + 1} attempts: {last_exc}"
        event("llm_error", _MAX_RETRIES, error=error)
        raise LLMCallError(error) from last_exc

    @staticmethod
    def _tool_payload(message: Any, tool_name: str) -> dict[str, Any] | None:
        """The forced tool's input from a response, or ``None`` when the block is absent."""
        for block in message.content:
            if isinstance(block, anthropic.types.ToolUseBlock) and block.name == tool_name:
                return cast(dict[str, Any], block.input)
        return None

    def _record_usage(self, message: Any) -> None:
        """Fire the usage recorder (instance override, else module default) if one is set.

        Reads ``message.usage`` defensively — a stub or a future SDK may omit fields — and
        never lets a recorder error disturb the call path (usage capture is observational)."""
        recorder = self._usage_recorder or _default_usage_recorder
        if recorder is None:
            return
        usage = getattr(message, "usage", None)
        recorder(
            self._model,
            int(getattr(usage, "input_tokens", 0) or 0),
            int(getattr(usage, "output_tokens", 0) or 0),
            int(getattr(usage, "cache_read_input_tokens", 0) or 0),
        )
