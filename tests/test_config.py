"""Config regression guards.

These assert the model identifiers are well-formed without calling the network — a
cheap guard against a recurrence of the invalid-heavy-model bug (H-2), where
``heavy_model`` was set to a non-existent ``claude-…`` string and every real modeler
run 404'd. We set a dummy ``ANTHROPIC_API_KEY`` so ``Settings()`` constructs even when
no ``.env`` is present (e.g. in CI).
"""
import re

import pytest

from vault_agent.config import Settings

_CLAUDE_MODEL = re.compile(r"^claude-[a-z0-9.-]+$")


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-a-real-key")
    return Settings()  # type: ignore[call-arg]


def test_primary_model_is_a_valid_claude_identifier(settings: Settings) -> None:
    assert settings.primary_model
    assert _CLAUDE_MODEL.match(settings.primary_model), settings.primary_model


def test_heavy_model_is_a_valid_claude_identifier(settings: Settings) -> None:
    assert settings.heavy_model
    assert _CLAUDE_MODEL.match(settings.heavy_model), settings.heavy_model
