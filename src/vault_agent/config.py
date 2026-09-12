"""Configuration loaded from environment variables.

``Settings`` is built lazily via :func:`get_settings`, not at import time, so that
``import vault_agent.config`` never needs a credential (construction/tests never do). The
first call constructs and caches it. Constructing a real LLM client without the required
credential then raises a clear, attributable ``ValidationError`` at that call site.

The LLM **provider** is a setting (``LLM_PROVIDER``), because the route decides where the
requirements text and schema metadata are processed — the data-residency question in
``docs/architecture/deployment-residency.md``. Three routes, one client surface:

- ``anthropic``: the first-party API. Needs ``ANTHROPIC_API_KEY``. US/global inference.
- ``bedrock``: Amazon Bedrock through the SDK's Messages-API client
  (``AsyncAnthropicBedrockMantle``). Needs ``AWS_REGION`` (e.g. ``eu-central-2`` — Zurich —
  or ``eu-central-1``); credentials come from the standard AWS chain (env, profile, role),
  optionally ``AWS_PROFILE``. Requires the ``bedrock`` extra.
- ``vertex``: Google Vertex AI (``AsyncAnthropicVertex``). Needs ``GCP_PROJECT_ID`` and
  ``GCP_REGION`` (``europe-west1``, ``eu`` or ``global``); auth is Application Default
  Credentials. Requires the ``vertex`` extra.

Model identifiers are passed to the provider **as configured** — no mapping is derived
here. Provider IDs differ in shape (first-party ``claude-sonnet-4-6``; Bedrock carries an
``anthropic.`` prefix, on the legacy route also a region profile such as ``eu.``; Vertex
uses bare or ``@``-versioned IDs) and change per release, so the operator sets
``PRIMARY_MODEL``/``HEAVY_MODEL`` to what the chosen provider lists. Inventing a mapping
would be exactly the "plausible name that does not exist" this project's craft rules warn
about.
"""
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["anthropic", "bedrock", "vertex"]


class Settings(BaseSettings):
    # extra="ignore": a user's .env may carry variables for other tools or entries for
    # settings that no longer exist (e.g. the removed LOG_LEVEL) — stale or foreign keys
    # must never crash startup. Newer pydantic-settings versions default to "forbid".
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # LLM route (data residency) — see the module docstring.
    llm_provider: LLMProvider = "anthropic"
    anthropic_api_key: str | None = None
    aws_region: str | None = None
    aws_profile: str | None = None
    gcp_project_id: str | None = None
    gcp_region: str | None = None

    primary_model: str = "claude-sonnet-4-6"
    heavy_model: str = "claude-opus-4-8"

    # Tracing / evals (consumed by the WP6 eval harness: eval/run.py,
    # eval/langsmith_upload.py)
    langsmith_api_key: str | None = None
    langsmith_tracing: bool = False
    langsmith_project: str = "vault-agent-dev"

    def route(self) -> dict[str, str]:
        """The route as facts — for the trace header and the console. Never a secret."""
        facts: dict[str, str] = {"provider": self.llm_provider}
        if self.llm_provider == "bedrock":
            facts["region"] = self.aws_region or ""
            if self.aws_profile:
                facts["profile"] = self.aws_profile
        elif self.llm_provider == "vertex":
            facts["project"] = self.gcp_project_id or ""
            facts["region"] = self.gcp_region or ""
        return facts

    def route_description(self) -> str:
        """One line for the run summary: ``bedrock eu-central-2 (profile dwh)``."""
        r = self.route()
        if r["provider"] == "bedrock":
            tail = f" (profile {r['profile']})" if "profile" in r else ""
            return f"bedrock {r['region']}{tail}"
        if r["provider"] == "vertex":
            return f"vertex {r['project']} {r['region']}"
        return "anthropic (first-party API)"

    @model_validator(mode="after")
    def _route_has_its_credentials(self) -> "Settings":
        """Fail at construction, naming the missing field for the chosen route."""
        missing: list[str] = []
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            missing.append("anthropic_api_key (ANTHROPIC_API_KEY)")
        if self.llm_provider == "bedrock" and not self.aws_region:
            missing.append("aws_region (AWS_REGION)")
        if self.llm_provider == "vertex":
            if not self.gcp_project_id:
                missing.append("gcp_project_id (GCP_PROJECT_ID)")
            if not self.gcp_region:
                missing.append("gcp_region (GCP_REGION)")
        if missing:
            raise ValueError(
                f"llm_provider={self.llm_provider!r} requires {', '.join(missing)}"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide ``Settings``, constructing it on first use."""
    return Settings()
