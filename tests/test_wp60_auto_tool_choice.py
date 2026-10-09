"""WP60 — a tool-call mode for models that refuse forced tool use (spec §3). Committed before
the change, failing."""
from __future__ import annotations

import pytest

from tests.test_llm import _SLEEPS, _Message, _no_sleep, _StubClient, _tool_block
from vault_agent.config import Settings
from vault_agent.llm import ForcedToolCaller, LLMCallError

_TOOL = "emit_things"


async def _call(caller: ForcedToolCaller) -> dict:  # type: ignore[type-arg]
    return await caller.call(
        system_prompt="system", tool_name=_TOOL, tool_description="emit",
        input_schema={"type": "object"}, user_content="user", max_tokens=64,
    )


async def test_forced_mode_is_the_default_and_unchanged() -> None:
    client = _StubClient([_Message(content=[_tool_block({"ok": True})])])
    caller = ForcedToolCaller("test-model", client=client, sleep=_no_sleep, forced=True)
    assert await _call(caller) == {"ok": True}
    (kwargs,) = client.messages.calls
    assert kwargs["tool_choice"] == {"type": "tool", "name": _TOOL}
    assert "strict" not in kwargs["tools"][0]
    assert kwargs["messages"] == [{"role": "user", "content": "user"}]


async def test_auto_mode_asks_instead_of_forcing() -> None:
    client = _StubClient([_Message(content=[_tool_block({"ok": True})])])
    caller = ForcedToolCaller("test-model", client=client, sleep=_no_sleep, forced=False)
    assert await _call(caller) == {"ok": True}
    (kwargs,) = client.messages.calls
    assert kwargs["tool_choice"] == {"type": "auto"}
    # Amended with the change: `strict` needs the structured-outputs schema subset the agents'
    # schemas do not meet (400 on 2026-10-09); the tool definition stays as in forced mode.
    assert "strict" not in kwargs["tools"][0]
    content = kwargs["messages"][0]["content"]
    assert content.startswith("user") and content.rstrip().endswith("do not reply in text.")
    assert f"`{_TOOL}`" in content
    assert kwargs["system"][0]["text"] == "system"


async def test_in_auto_mode_a_text_only_answer_is_retried() -> None:
    _SLEEPS.clear()
    client = _StubClient([_Message(content=[]), _Message(content=[_tool_block({"ok": 1})])])
    caller = ForcedToolCaller("test-model", client=client, sleep=_no_sleep, rng=lambda: 1.0,
                              forced=False)
    assert await _call(caller) == {"ok": 1}
    assert len(client.messages.calls) == 2
    assert _SLEEPS == [2.0]


async def test_in_auto_mode_text_on_every_attempt_exhausts_the_budget() -> None:
    _SLEEPS.clear()
    client = _StubClient([_Message(content=[]) for _ in range(6)])
    caller = ForcedToolCaller("test-model", client=client, sleep=_no_sleep, rng=lambda: 1.0,
                              forced=False)
    with pytest.raises(LLMCallError, match="attempts"):
        await _call(caller)


def test_the_setting_defaults_to_forced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")  # Settings validates the route
    monkeypatch.delenv("FORCED_TOOL_CHOICE", raising=False)
    assert Settings(_env_file=None).forced_tool_choice is True  # type: ignore[call-arg]
    monkeypatch.setenv("FORCED_TOOL_CHOICE", "false")
    assert Settings(_env_file=None).forced_tool_choice is False  # type: ignore[call-arg]
