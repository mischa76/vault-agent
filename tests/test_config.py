"""Config regression guards.

These assert the model identifiers are well-formed without calling the network — a
cheap guard against a recurrence of the invalid-heavy-model bug (H-2), where
``heavy_model`` was set to a non-existent ``claude-…`` string and every real modeler
run 404'd. We set a dummy ``ANTHROPIC_API_KEY`` so ``Settings()`` constructs even when
no ``.env`` is present (e.g. in CI).
"""
import importlib
import re

import pytest
from pydantic import ValidationError

from vault_agent.config import Settings, get_settings

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


def test_importing_config_needs_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # L-3: importing the module must not construct Settings, so a missing key can't crash
    # the import. Reloading re-runs the module body under the cleared environment.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import vault_agent.config as cfg

    importlib.reload(cfg)  # must not raise


def test_settings_without_key_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # The failure is explicit and attributable (pydantic names the missing field),
    # not a vague import-time crash. ``_env_file=None`` bypasses any local ``.env``.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    assert "anthropic_api_key" in str(exc_info.value).lower()


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-a-real-key")
    get_settings.cache_clear()
    try:
        assert get_settings() is get_settings()
    finally:
        get_settings.cache_clear()
