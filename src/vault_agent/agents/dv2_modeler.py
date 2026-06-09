"""DV2.0 Modeler agent.

Turns the parsed requirements and proposed business keys into a logical Data Vault model
(hubs, links, satellites) in ``VaultAgentState.dv_model``. This is the pipeline's central
modelling decision, so it also emits a draft ADR fragment into ``VaultAgentState.adrs``.

The DV2 modelling rules are NOT hard-coded in the prompt (see CLAUDE.md): they live in
``vault_agent.rules.dv2_rules`` and are injected into the system prompt at runtime.

Structured output uses forced Anthropic tool-use with a schema derived from the Hub / Link
/ Satellite models; the client is constructed lazily so tests run without a key. After
validation a structural pass drops constructs that dangle (links referencing missing hubs,
satellites referencing a missing parent).
"""
import json
from typing import Any, Protocol, cast

from pydantic import ValidationError

from vault_agent.agents.base import BaseAgent
from vault_agent.rules.dv2_rules import DV_MODELING_RULES
from vault_agent.state import DVModel, Hub, Link, Satellite, VaultAgentState

_TOOL_NAME = "emit_dv_model"
_MAX_TOKENS = 8192


def _tool_schema() -> dict[str, Any]:
    """Wrap the Hub / Link / Satellite schemas as the tool input."""
    return {
        "type": "object",
        "properties": {
            "hubs": {
                "type": "array",
                "items": Hub.model_json_schema(),
                "description": "One hub per business concept, anchored on a business key.",
            },
            "links": {
                "type": "array",
                "items": Link.model_json_schema(),
                "description": "One link per relationship between business objects.",
            },
            "satellites": {
                "type": "array",
                "items": Satellite.model_json_schema(),
                "description": "Descriptive attributes grouped by parent hub or link.",
            },
        },
        "required": ["hubs", "links", "satellites"],
    }


class DVModelExtractor(Protocol):
    """Turns requirements + business keys into a raw DV model payload.

    Implemented for real by :class:`AnthropicDVModelExtractor`; stubbed in tests.
    """

    async def model(self, *, system_prompt: str, payload_json: str) -> dict[str, Any]: ...


class AnthropicDVModelExtractor:
    """Default extractor backed by the Anthropic Messages API (forced tool-use)."""

    def __init__(self, model: str | None = None) -> None:
        # Imported lazily so importing this module never requires an API key.
        from anthropic import AsyncAnthropic

        from vault_agent.config import settings

        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        # The modeller is the hardest reasoning step; allow the heavy model via config.
        self._model = model or settings.heavy_model

    async def model(self, *, system_prompt: str, payload_json: str) -> dict[str, Any]:
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            tools=[
                {
                    "name": _TOOL_NAME,
                    "description": "Emit the logical Data Vault model for the inputs.",
                    "input_schema": _tool_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
            messages=[{"role": "user", "content": payload_json}],
        )
        for block in message.content:
            if block.type == "tool_use" and block.name == _TOOL_NAME:
                return cast(dict[str, Any], block.input)
        return {}


class Dv2ModelerAgent(BaseAgent):
    """Derives a logical Data Vault model from requirements and business keys."""

    prompt_path = "dv2_modeler.md"  # type: ignore[assignment]

    def __init__(self, extractor: DVModelExtractor | None = None) -> None:
        self._extractor = extractor

    def _get_extractor(self) -> DVModelExtractor:
        if self._extractor is None:
            self._extractor = AnthropicDVModelExtractor()
        return self._extractor

    def _build_system_prompt(self) -> str:
        """Load the prompt template and inject the DV2 modelling rules."""
        template = self.load_prompt()
        rules = "\n".join(f"- {rule}" for rule in DV_MODELING_RULES)
        return f"{template}\n\n## Data Vault modelling rules to apply\n\n{rules}\n"

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        if not state.business_keys:
            state.errors.append(
                "dv2_modeler: no business keys in state; run the business key "
                "identifier first"
            )
            return state

        system_prompt = self._build_system_prompt()
        payload_json = json.dumps(
            {
                "requirements": [req.model_dump() for req in state.requirements],
                "business_keys": [bk.model_dump() for bk in state.business_keys],
            },
            indent=2,
        )
        extractor = self._get_extractor()
        raw = await extractor.model(system_prompt=system_prompt, payload_json=payload_json)

        model = self._validate_model(raw, state)
        state.dv_model = model
        state.decisions.append(
            {
                "agent": "dv2_modeler",
                "hubs": len(model.hubs),
                "links": len(model.links),
                "satellites": len(model.satellites),
            }
        )
        state.adrs.append(self._draft_adr_fragment(model))
        return state

    def _validate_model(self, raw: dict[str, Any], state: VaultAgentState) -> DVModel:
        """Validate the raw payload into typed constructs and drop dangling ones."""
        hubs = self._validate_items(raw.get("hubs", []), Hub, "hub", state)
        links = self._validate_items(raw.get("links", []), Link, "link", state)
        satellites = self._validate_items(raw.get("satellites", []), Satellite, "satellite", state)

        hub_names = {hub.name for hub in hubs}

        kept_links: list[Link] = []
        for link in links:
            missing = [name for name in link.connected_hubs if name not in hub_names]
            if len(link.connected_hubs) < 2 or missing:
                state.errors.append(
                    f"dv2_modeler: dropped link {link.name!r} — must connect >=2 known "
                    f"hubs (missing: {missing or 'none'}, count: {len(link.connected_hubs)})"
                )
                continue
            kept_links.append(link)

        valid_parents = hub_names | {link.name for link in kept_links}
        kept_satellites: list[Satellite] = []
        for sat in satellites:
            if sat.parent not in valid_parents:
                state.errors.append(
                    f"dv2_modeler: dropped satellite {sat.name!r} — parent "
                    f"{sat.parent!r} is not a known hub or link"
                )
                continue
            kept_satellites.append(sat)

        return DVModel(hubs=hubs, links=kept_links, satellites=kept_satellites)

    @staticmethod
    def _validate_items(
        records: list[dict[str, Any]],
        model_cls: type[Hub] | type[Link] | type[Satellite],
        label: str,
        state: VaultAgentState,
    ) -> list[Any]:
        items: list[Any] = []
        for record in records:
            try:
                items.append(model_cls.model_validate(record))
            except ValidationError as exc:
                state.errors.append(
                    f"dv2_modeler: dropped invalid {label}: {exc.error_count()} error(s)"
                )
        return items

    @staticmethod
    def _draft_adr_fragment(model: DVModel) -> str:
        return (
            "## Draft ADR: Data Vault model derived from requirements\n"
            f"- Hubs ({len(model.hubs)}): {', '.join(h.name for h in model.hubs) or '—'}\n"
            f"- Links ({len(model.links)}): {', '.join(lk.name for lk in model.links) or '—'}\n"
            f"- Satellites ({len(model.satellites)}): "
            f"{', '.join(s.name for s in model.satellites) or '—'}\n"
            "Per-construct rationale and requirement traceability are captured in "
            "`requirement_ids` on each construct in `state.dv_model`."
        )
