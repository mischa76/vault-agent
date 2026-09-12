"""The residency switch: one setting picks the route, the client factory is the only place
that knows the three SDK clients, and a wrong or incomplete route fails at construction
with the missing field named (`docs/architecture/deployment-residency.md`).

Keyless by construction: the provider classes are replaced by recording fakes, so no
credential chain (AWS, GCP) is touched and the optional extras need not be installed."""
from __future__ import annotations

from typing import Any

import anthropic
import pytest
from pydantic import ValidationError

from vault_agent import llm
from vault_agent.config import Settings
from vault_agent.llm import LLMCallError, make_client


class _Recorder:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def _settings(**env: str) -> Settings:
    return Settings(_env_file=None, **env)  # type: ignore[call-arg]


# --- construction-time validation -----------------------------------------------------

def test_default_route_is_anthropic_and_needs_the_key() -> None:
    s = _settings(anthropic_api_key="sk-ant-test")
    assert s.llm_provider == "anthropic"
    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        _settings()


def test_bedrock_needs_a_region_but_no_anthropic_key() -> None:
    s = _settings(llm_provider="bedrock", aws_region="eu-central-2")
    assert s.anthropic_api_key is None
    with pytest.raises(ValidationError, match="AWS_REGION"):
        _settings(llm_provider="bedrock")


def test_vertex_needs_project_and_region() -> None:
    _settings(llm_provider="vertex", gcp_project_id="p", gcp_region="europe-west1")
    with pytest.raises(ValidationError) as exc:
        _settings(llm_provider="vertex", gcp_region="eu")
    assert "GCP_PROJECT_ID" in str(exc.value)


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(llm_provider="azure", anthropic_api_key="x")  # type: ignore[arg-type]


# --- the factory ----------------------------------------------------------------------

def test_factory_builds_the_first_party_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(anthropic, "AsyncAnthropic", _Recorder)
    client = make_client(_settings(anthropic_api_key="sk-ant-test"))
    assert isinstance(client, _Recorder) and client.kwargs == {"api_key": "sk-ant-test"}


def test_factory_builds_bedrock_with_region_and_optional_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(anthropic, "AsyncAnthropicBedrockMantle", _Recorder)
    c = make_client(_settings(llm_provider="bedrock", aws_region="eu-central-2"))
    assert c.kwargs == {"aws_region": "eu-central-2"}
    c2 = make_client(
        _settings(llm_provider="bedrock", aws_region="eu-central-1", aws_profile="dwh")
    )
    assert c2.kwargs == {"aws_region": "eu-central-1", "aws_profile": "dwh"}


def test_factory_builds_vertex_with_project_and_region(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(anthropic, "AsyncAnthropicVertex", _Recorder)
    c = make_client(_settings(llm_provider="vertex", gcp_project_id="p-1", gcp_region="eu"))
    assert c.kwargs == {"project_id": "p-1", "region": "eu"}


def test_missing_provider_extra_is_an_attributable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(**_: Any) -> Any:
        raise ImportError("No module named 'boto3'")

    monkeypatch.setattr(anthropic, "AsyncAnthropicBedrockMantle", boom)
    with pytest.raises(LLMCallError, match="uv sync --extra bedrock"):
        make_client(_settings(llm_provider="bedrock", aws_region="eu-central-2"))


def test_caller_uses_the_factory_when_no_client_is_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Any] = []

    def fake_factory(settings: Any) -> str:
        seen.append(settings.llm_provider)
        return "client"

    monkeypatch.setattr(llm, "make_client", fake_factory)
    monkeypatch.setattr(
        "vault_agent.config.get_settings",
        lambda: _settings(llm_provider="vertex", gcp_project_id="p", gcp_region="eu"),
    )
    caller = llm.ForcedToolCaller("m")
    assert caller._client == "client" and seen == ["vertex"]


def test_installed_sdk_has_the_clients_the_factory_names() -> None:
    """Guard against SDK drift: the factory calls these by name."""
    for name in ("AsyncAnthropic", "AsyncAnthropicBedrockMantle", "AsyncAnthropicVertex"):
        assert hasattr(anthropic, name), name


# --- the route in console and trace ---------------------------------------------------

def test_route_facts_and_description_per_provider() -> None:
    a = _settings(anthropic_api_key="k")
    assert a.route() == {"provider": "anthropic"}
    assert a.route_description().startswith("anthropic")
    b = _settings(llm_provider="bedrock", aws_region="eu-central-2", aws_profile="dwh")
    assert b.route() == {"provider": "bedrock", "region": "eu-central-2", "profile": "dwh"}
    assert b.route_description() == "bedrock eu-central-2 (profile dwh)"
    v = _settings(llm_provider="vertex", gcp_project_id="p-1", gcp_region="eu")
    assert v.route() == {"provider": "vertex", "project": "p-1", "region": "eu"}
    assert v.route_description() == "vertex p-1 eu"
    assert "k" not in str(a.route())  # never a secret


def test_route_never_leaks_the_api_key() -> None:
    s = _settings(anthropic_api_key="sk-ant-secret-value")
    assert "secret" not in s.route_description() and "secret" not in str(s.route())


async def test_every_call_event_names_the_client_class() -> None:
    from tests.test_llm import _TOOL, _Message, _StubClient, _tool_block
    from vault_agent.llm import ForcedToolCaller, TraceEvent

    events: list[TraceEvent] = []
    caller = ForcedToolCaller(
        "m", client=_StubClient([_Message(content=[_tool_block()])]), trace_recorder=events.append
    )
    await caller.call(
        tool_name=_TOOL, tool_description="d", input_schema={"type": "object"},
        system_prompt="s", user_content="u", max_tokens=8,
    )
    assert [e.kind for e in events] == ["llm_call"]
    assert events[0].client == "_StubClient"


def test_trace_starts_with_the_route_header(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    import json

    from vault_agent import cli

    monkeypatch.setattr(
        "vault_agent.config.get_settings",
        lambda: _settings(llm_provider="bedrock", aws_region="eu-central-2"),
    )
    with cli._tracing(tmp_path, "thread-1", enabled=True):
        pass
    text = cli._trace_path(tmp_path, "thread-1").read_text()
    lines = [json.loads(line) for line in text.splitlines()]
    assert lines[0]["kind"] == "llm_route"
    assert lines[0]["payload"] == {"provider": "bedrock", "region": "eu-central-2"}


def test_trace_header_says_unknown_when_settings_do_not_construct(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    import json

    from vault_agent import cli

    def boom() -> Any:
        raise ValueError("no credentials")

    monkeypatch.setattr("vault_agent.config.get_settings", boom)
    with cli._tracing(tmp_path, "thread-2", enabled=True):
        pass
    first = json.loads(cli._trace_path(tmp_path, "thread-2").read_text().splitlines()[0])
    assert first == {**first, "kind": "llm_route", "payload": {"provider": "unknown"}}


def test_summary_prints_the_route(monkeypatch: pytest.MonkeyPatch) -> None:
    from rich.console import Console

    from vault_agent import cli
    from vault_agent.state import VaultAgentState

    monkeypatch.setattr(
        "vault_agent.config.get_settings",
        lambda: _settings(llm_provider="vertex", gcp_project_id="p-1", gcp_region="eu"),
    )
    console = Console(record=True, width=120)
    cli._print_summary(console, VaultAgentState())
    assert "llm route:     vertex p-1 eu" in console.export_text()
