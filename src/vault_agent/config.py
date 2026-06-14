"""Configuration loaded from environment variables.

``Settings`` requires ``ANTHROPIC_API_KEY`` with no default. To keep ``import
vault_agent.config`` safe without the key set (construction/tests never need it), the
settings object is built lazily via :func:`get_settings`, not at import time. The first
call constructs and caches it; the cache means repeated calls don't re-read the
environment. Constructing a real LLM extractor without the key then raises a clear,
attributable ``ValidationError`` at that call site, instead of crashing the import.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # LLM
    anthropic_api_key: str
    primary_model: str = "claude-sonnet-4-6"
    heavy_model: str = "claude-opus-4-8"

    # Tracing
    langsmith_api_key: str | None = None
    langsmith_tracing: bool = False
    langsmith_project: str = "vault-agent-dev"

    # Logging
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide ``Settings``, constructing it on first use."""
    return Settings()  # type: ignore[call-arg]
