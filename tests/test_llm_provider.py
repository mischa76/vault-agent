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
