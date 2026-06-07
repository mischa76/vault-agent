"""Configuration loaded from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # LLM
    anthropic_api_key: str
    primary_model: str = "claude-sonnet-4-6"
    heavy_model: str = "claude-opus-4-6"

    # Tracing
    langsmith_api_key: str | None = None
    langsmith_tracing: bool = False
    langsmith_project: str = "vault-agent-dev"

    # Logging
    log_level: str = "INFO"


settings = Settings()  # type: ignore[call-arg]
