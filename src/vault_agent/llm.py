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
import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast

import anthropic

logger = logging.getLogger(__name__)

# Transient statuses worth retrying: timeout, rate limit, server errors, overloaded.
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 529})
_MAX_RETRIES = 3
_BASE_DELAY_SECONDS = 2.0


class LLMCallError(RuntimeError):
    """A forced tool call failed in a way the pipeline must not silently absorb.

    Raised for truncated responses (the tool payload would be incomplete), responses
    without the forced tool block, and transient API failures that persist past the
    retry budget. Callers must NOT treat this as "the model found nothing" — that case
    is a *successful* call with an empty payload."""


class ForcedToolCaller:
    """Calls the Anthropic Messages API forcing one tool; returns the tool's input.

    ``client`` and ``sleep`` are injectable for tests; by default a real
    ``AsyncAnthropic`` client is built from the settings (lazily, at construction)."""

    def __init__(
        self,
        model: str,
        client: Any | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if client is None:
            # Imported here so module import never requires an API key.
            from vault_agent.config import get_settings

            settings = get_settings()
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._client = client
        self._model = model
        self._sleep = sleep or asyncio.sleep

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
                    raise
                last_exc = exc
                continue

            # A truncated response means an incomplete (or absent) tool payload; falling
            # through would be indistinguishable from "the model found nothing" and
            # would burn a modeling retry on garbage.
            if message.stop_reason == "max_tokens":
                raise LLMCallError(
                    f"{tool_name}: response truncated at max_tokens={max_tokens}; "
                    f"the tool payload is incomplete (raise the limit or shrink the input)"
                )
            for block in message.content:
                if isinstance(block, anthropic.types.ToolUseBlock) and block.name == tool_name:
                    return cast(dict[str, Any], block.input)
            raise LLMCallError(
                f"{tool_name}: no tool_use block in the response "
                f"(stop_reason={message.stop_reason!r})"
            )

        raise LLMCallError(
            f"{tool_name}: API call failed after {_MAX_RETRIES + 1} attempts: {last_exc}"
        ) from last_exc
