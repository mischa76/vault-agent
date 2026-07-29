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
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, cast

import anthropic

logger = logging.getLogger(__name__)

# Transient statuses worth retrying: timeout, rate limit, server errors, overloaded.
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 529})
_MAX_RETRIES = 3
_BASE_DELAY_SECONDS = 2.0
# Upper bound on ANY single wait, including a server-supplied Retry-After (WP27 §2.2): a
# hostile or mistaken header must not be able to hang a run for an hour.
_MAX_RETRY_DELAY_SECONDS = 60.0

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


# How often a unit of work may be halved before the truncation is re-raised: 4 levels =
# up to 16 segments, far past any observed need. A deeper recursion means the per-segment
# answer is not shrinking, so size is not the cause — surface it instead of paying on.
MAX_SPLIT_DEPTH = 4


async def call_with_truncation_split[T, R](
    call: Callable[[T], Awaitable[R]],
    unit: T,
    split: Callable[[T], tuple[T, T] | None],
    *,
    max_depth: int = MAX_SPLIT_DEPTH,
) -> list[R]:
    """Run ``call`` on ``unit``, halving it via ``split`` only when the answer is truncated.

    The shared half of a pattern that recurs whenever an agent's OUTPUT scales with the
    size of the landscape: the whole unit is tried first, so anything that already fits
    makes exactly one call with unchanged content and the segmentation stays invisible
    until needed. A truncated response (``LLMCallError.truncated``) means the answer
    outgrew the output budget — raising ``max_tokens`` buys headroom but not a bound, and
    at 100 source tables even 8192 was not enough, so splitting the input is the only
    lever that actually shrinks an answer.

    ``split`` returns the two halves or ``None`` when the unit is indivisible; either an
    indivisible unit or ``max_depth`` re-raises. Callers merge the returned per-segment
    results themselves — deduping and key collisions are domain knowledge (requirement ids,
    business-key identity), not something this helper can decide.

    Anything other than a truncation propagates untouched: a missing tool block or an
    exhausted retry budget is not a size problem and must not be answered by splitting."""

    async def attempt(current: T, depth: int) -> list[R]:
        try:
            return [await call(current)]
        except LLMCallError as exc:
            halves = split(current) if exc.truncated else None
            if halves is None or depth >= max_depth:
                raise
            logger.info("response truncated; splitting the unit of work at depth %d", depth)
            results: list[R] = []
            for half in halves:
                results.extend(await attempt(half, depth + 1))
            return results

    return await attempt(unit, 0)


class ForcedToolCaller:
    """Calls the Anthropic Messages API forcing one tool; returns the tool's input.

    ``client``, ``sleep`` and ``rng`` are injectable for tests; by default a real
    ``AsyncAnthropic`` client is built from the settings (lazily, at construction)."""

    def __init__(
        self,
        model: str,
        client: Any | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        usage_recorder: UsageRecorder | None = None,
        trace_recorder: TraceRecorder | None = None,
        rng: Callable[[], float] | None = None,
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
        self._rng = rng or random.random

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
                # The delay is decided from the failure that caused THIS retry, so a
                # server-supplied Retry-After wins over our guess (WP27 §2.2).
                delay, source = self._retry_delay(attempt, last_exc)
                logger.info(
                    "%s: retry %d/%d for %s in %.1fs (%s)",
                    self._model, attempt, _MAX_RETRIES, tool_name, delay, source,
                )
                await self._sleep(delay)
            try:
                # STREAMING (WP22 / ADR-0010), one path — there is deliberately no
                # streaming/non-streaming conditional, because a second path is a second
                # thing that can rot. The request kwargs are byte-identical to the previous
                # non-streaming call, so prompt caching and every fixture pin are
                # untouched; only the transport changed. get_final_message() returns the
                # accumulated Message — same content blocks, stop_reason and usage (incl.
                # cache_read_input_tokens, verified against the installed SDK's accumulator)
                # — so truncation detection, _tool_payload, usage capture and the WP15 trace
                # events all read exactly what they read before.
                #
                # Both failure surfaces stay inside this try: the initial request is awaited
                # by __aenter__ (an APIStatusError there still carries status_code, which the
                # retry matrix keys on), and a mid-stream failure surfaces from
                # get_final_message().
                async with self._client.messages.stream(
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
                ) as stream:
                    message = await stream.get_final_message()
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

    def _retry_delay(self, attempt: int, exc: Exception | None) -> tuple[float, str]:
        """How long to wait before ``attempt``, and which policy decided it (WP27 §2.2).

        A server-supplied ``Retry-After`` wins: answering a ``Retry-After: 30`` with our
        2/4/8 s ladder fails the whole call after ~14 s of waiting that was guaranteed to be
        too short. Both header spellings the API may send are read — ``retry-after-ms``
        first, like the SDK's own client does — and anything non-numeric (the RFC also
        permits an HTTP date) falls through to the exponential path rather than being
        guessed at. Every wait, header or not, is capped at ``_MAX_RETRY_DELAY_SECONDS``.

        Without a usable header: exponential base delay plus **equal jitter**
        (``d/2 + random()*d/2``). Equal rather than full jitter (``random()*d``) because the
        failure this exists for is a rate-limit collision — parallel runs (eval ``--repeat``,
        ablation arms) must stop retrying in lockstep, but a retry that lands almost
        immediately is exactly what a 429 is asking us not to do. Equal jitter decorrelates
        while keeping at least half the backoff."""
        header = self._retry_after_seconds(exc)
        if header is not None:
            return min(header, _MAX_RETRY_DELAY_SECONDS), "server Retry-After"
        base = _BASE_DELAY_SECONDS * 2 ** (attempt - 1)
        jittered = base / 2 + self._rng() * base / 2
        return min(jittered, _MAX_RETRY_DELAY_SECONDS), "exponential backoff + jitter"

    @staticmethod
    def _retry_after_seconds(exc: Exception | None) -> float | None:
        """``Retry-After`` from a failed response, in seconds, or None when unusable.

        Read defensively against the SDK surface (verified on anthropic 0.107.0:
        ``APIStatusError.response`` is an ``httpx.Response``, so headers are a
        case-insensitive mapping) — a stub client in tests carries no response at all, and a
        future SDK may reshape this. Anything unreadable simply means "no header"."""
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        if headers is None:
            return None
        try:
            milliseconds = headers.get("retry-after-ms")
            if milliseconds is not None:
                return max(0.0, float(milliseconds) / 1000)
            seconds = headers.get("retry-after")
            if seconds is not None:
                return max(0.0, float(seconds))
        except (TypeError, ValueError, AttributeError):
            return None  # e.g. an HTTP-date Retry-After: fall back to the exponential path
        return None

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
        try:
            recorder(
                self._model,
                int(getattr(usage, "input_tokens", 0) or 0),
                int(getattr(usage, "output_tokens", 0) or 0),
                int(getattr(usage, "cache_read_input_tokens", 0) or 0),
            )
        except Exception:  # noqa: BLE001 - observational channel, never fatal (as emit_trace)
            # The response is already generated and BILLED at this point; letting a broken
            # accounting sink discard it would be the most expensive possible failure mode.
            logger.warning("usage recorder failed for a %s call", self._model, exc_info=True)
