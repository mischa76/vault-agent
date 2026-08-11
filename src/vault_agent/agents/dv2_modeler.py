"""DV2.0 Modeler agent.

Turns the parsed requirements and proposed business keys into a logical Data Vault model
(hubs, links, satellites) in ``VaultAgentState.dv_model``. This is the pipeline's central
modelling decision. It does not write to ``VaultAgentState.adrs`` — the ADR Author is the
sole writer, rendering the finalized ADR from ``state.dv_model`` (which already carries each
construct's rationale and ``requirement_ids``). Emitting a draft fragment per pass would
leave stale fragments behind on an exhausted-retry run that never reaches the ADR Author.

The DV2 modelling rules are NOT hard-coded in the prompt (see CLAUDE.md): they live in
``vault_agent.rules.dv2_rules`` and are injected into the system prompt at runtime.

Structured output uses forced Anthropic tool-use with a schema derived from the Hub / Link
/ Satellite models; the client is constructed lazily so tests run without a key. After
validation a structural pass drops constructs that dangle (links referencing missing hubs,
satellites referencing a missing parent).
"""
import json
import logging
from typing import Any, Protocol

from pydantic import ValidationError

from vault_agent.agents.base import BaseAgent
from vault_agent.agents.entity_resolver import render_resolution_prompt_section
from vault_agent.existing_model import render_extension_prompt_section
from vault_agent.grounding import render_schema_prompt_section
from vault_agent.llm import TraceEvent, emit_trace
from vault_agent.rules.dv2_rules import active_modeling_rules, attributes_without_cdk
from vault_agent.state import DVModel, FlagKind, Hub, Link, Satellite, VaultAgentState

logger = logging.getLogger(__name__)

_TOOL_NAME = "emit_dv_model"

# The modeler emits ONE coherent model, so the truncation-split that carries the
# requirements parser and the business-key identifier (llm.call_with_truncation_split)
# does NOT apply here: merging two half-models is a modelling problem, not a dedup one —
# a link can span the halves, a hub proposed in both must be reconciled, a satellite's
# parent can sit on the other side. The only lever left is the budget.
#
# Measured (2026-07-28, replaying the truncated scale_100 call): 30 source tables need
# 7,225 output tokens, 100 need 13,889 in an isolated replay and 14,981 in-pipeline —
# sub-linear (3.3x tables -> ~1.9x tokens), extrapolating to ~26k at 300 tables.
#
# 16384 was a STOPGAP bounded by the transport, not by the model (91% utilisation at 100
# tables). WP22 removed that bound by making ForcedToolCaller stream (ADR-0010), so the
# ceiling is now the model's: claude-opus-4-8 allows 128,000 output tokens (verified
# 2026-07-29 against the live Models API, not from memory). For the record, the
# non-streaming limit was never "roughly 16k" — the installed SDK raises when
# 3600 * max_tokens / 128_000 > 600, i.e. above 21,333 tokens.
#
# 32768 is chosen deliberately rather than taking the model maximum: it clears the
# 300-table extrapolation with ~26% headroom while keeping a runaway generation's cost
# bounded (a full 128k burn is ~4x this one). The cap is not a spend — output tokens are
# billed as generated — so the only thing a lower cap costs is a failed run, and the only
# thing a higher cap costs is how long a runaway takes to fail.
#
# Exit condition (ADR-0010): if a real landscape ever exceeds this, the answer is staged
# modelling / domain partitioning, NOT another budget bump — a single coherent model that
# needs more than 32k output tokens is past what one call should carry.
_MAX_TOKENS = 32768


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
    """Default extractor backed by the shared forced-tool-use call path."""

    def __init__(self, model: str | None = None) -> None:
        # Imported lazily so importing this module never requires an API key.
        from vault_agent.config import get_settings
        from vault_agent.llm import ForcedToolCaller

        # The modeller is the hardest reasoning step; allow the heavy model via config.
        self._caller = ForcedToolCaller(model or get_settings().heavy_model)

    async def model(self, *, system_prompt: str, payload_json: str) -> dict[str, Any]:
        return await self._caller.call(
            tool_name=_TOOL_NAME,
            tool_description="Emit the logical Data Vault model for the inputs.",
            input_schema=_tool_schema(),
            system_prompt=system_prompt,
            user_content=payload_json,
            max_tokens=_MAX_TOKENS,
        )


class Dv2ModelerAgent(BaseAgent):
    """Derives a logical Data Vault model from requirements and business keys."""

    prompt_path = "dv2_modeler.md"

    def __init__(self, extractor: DVModelExtractor | None = None) -> None:
        self._extractor = extractor

    def _get_extractor(self) -> DVModelExtractor:
        if self._extractor is None:
            self._extractor = AnthropicDVModelExtractor()
        return self._extractor

    def _build_system_prompt(self, state: VaultAgentState) -> str:
        """Load the prompt template, inject the DV2 modelling rules, and (when a source
        schema is declared) the known source columns to ground attributes (ADR-0004)."""
        template = self.load_prompt()
        # WP16: the registry is the single source of the steering lines; active_modeling_rules()
        # honours the ablation seam (empty in production, so the prompt is byte-identical).
        rules = "\n".join(f"- {rule.text}" for rule in active_modeling_rules())
        schema_section = render_schema_prompt_section(state.source_schemas)
        extension_section = render_extension_prompt_section(state.existing_model)
        # WP29: only RATIFIED entity resolutions steer, and the renderer returns '' when there
        # are none — so greenfield, ungrounded and first runs keep a byte-identical prompt.
        resolution_section = render_resolution_prompt_section(state.resolutions)
        return (
            f"{template}\n\n## Data Vault modelling rules to apply\n\n{rules}\n"
            f"{schema_section}{extension_section}{resolution_section}"
        )

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        if not state.business_keys:
            state.flag(
                "dv2_modeler",
                "no business keys in state; run the business key identifier first",
                severity="error",
                kind=FlagKind.MISSING_INPUT,
            )
            return state

        # Count this modeling pass for the validation retry guard (route_after_validation).
        state.modeling_attempts += 1
        logger.info(
            "modeling attempt %d: %d requirement(s), %d business key(s)",
            state.modeling_attempts,
            len(state.requirements),
            len(state.business_keys),
        )
        system_prompt = self._build_system_prompt(state)
        payload: dict[str, Any] = {
            "requirements": [req.model_dump() for req in state.requirements],
            "business_keys": [bk.model_dump() for bk in state.business_keys],
        }
        # On a retry the validator has populated issues; feed the *blocking* ones back
        # so the model converges instead of repeating the same mistakes. Warnings are
        # advisory for humans, not steering input — sending them dilutes the correction
        # signal and costs tokens (WP3). Only the fields the model needs are sent.
        errors = [
            issue for issue in state.validation_report.issues if issue.severity == "error"
        ]
        if errors:
            payload["previous_validation_issues"] = [
                {"code": issue.code, "construct": issue.construct, "message": issue.message}
                for issue in errors
            ]
        payload_json = json.dumps(payload, indent=2)
        logger.debug("modeling payload: %d chars", len(payload_json))
        extractor = self._get_extractor()
        raw = await extractor.model(system_prompt=system_prompt, payload_json=payload_json)

        model = self._validate_model(raw, state)
        delta_counts = (len(model.hubs), len(model.links), len(model.satellites))
        if state.existing_model is not None:
            # WP23 §2.9: brownfield mode. The model just produced is a DELTA against the
            # existing vault; merging happens here (the modeler owns dv_model, and graph.py
            # stays orchestration-only) so everything downstream — code generation,
            # validation, mapping, the ADR — sees one complete model, as in greenfield.
            from vault_agent.agents.model_merger import merge_models
            from vault_agent.link_proposal import apply_ratified_link_proposals

            # WP34: a RATIFIED link proposal joins the delta here — before the merge, so it
            # goes through merge_models and every validator gate exactly as a modeler-emitted
            # link does. No privileged route into the model (§3.6). Inert when nothing is
            # ratified, which is every greenfield run and every extension run whose
            # checkpoint said no.
            model = apply_ratified_link_proposals(model, state.existing_model, state)
            model = merge_models(state.existing_model, model, state)
        state.dv_model = model
        logger.info(
            "modeled %d hub(s), %d link(s), %d satellite(s)",
            len(model.hubs),
            len(model.links),
            len(model.satellites),
        )
        decision: dict[str, Any] = {
            "agent": "dv2_modeler",
            "hubs": len(model.hubs),
            "links": len(model.links),
            "satellites": len(model.satellites),
        }
        if state.existing_model is not None:
            # The delta is what this pass actually decided; the totals above include the
            # existing vault, so recording only those would make an extension run look like
            # it re-modelled everything.
            decision["delta"] = {
                "hubs": delta_counts[0],
                "links": delta_counts[1],
                "satellites": delta_counts[2],
            }
        state.decisions.append(decision)
        return state

    def _validate_model(self, raw: dict[str, Any], state: VaultAgentState) -> DVModel:
        """Validate the raw payload into typed constructs and drop dangling ones."""
        hubs = self._validate_items(raw.get("hubs", []), Hub, "hub", state)
        links = self._validate_items(raw.get("links", []), Link, "link", state)
        satellites = self._validate_items(raw.get("satellites", []), Satellite, "satellite", state)

        hub_names = {hub.name for hub in hubs}

        kept_links: list[Link] = []
        for link in links:
            missing = [ref.hub for ref in link.hub_refs if ref.hub not in hub_names]
            if len(link.hub_refs) < 2 or missing:
                state.flag(
                    "dv2_modeler",
                    f"dropped link {link.name!r} — must connect >=2 known hubs "
                    f"(missing: {missing or 'none'}, count: {len(link.hub_refs)})",
                    kind=FlagKind.DROPPED_RECORD,
                    asset=link.name,
                )
                continue
            kept_links.append(link)

        valid_parents = hub_names | {link.name for link in kept_links}
        kept_satellites: list[Satellite] = []
        for sat in satellites:
            if sat.parent not in valid_parents:
                state.flag(
                    "dv2_modeler",
                    f"dropped satellite {sat.name!r} — parent {sat.parent!r} is not a "
                    f"known hub or link",
                    kind=FlagKind.DROPPED_RECORD,
                    asset=sat.name,
                )
                continue
            # A child_dependent_key also listed among the attributes would duplicate a
            # satellite column (E_SAT_DUP_ATTR). Drop the redundant payload copy — the CDK
            # column is emitted via src_cdk regardless — so a multi-active sat the LLM
            # over-populated still validates. Genuine attr-vs-attr dups are left to the gate.
            deduped = attributes_without_cdk(sat.attributes, sat.child_dependent_key)
            if deduped != sat.attributes:
                removed = [a for a in sat.attributes if a not in deduped]
                logger.info(
                    "satellite %r: dropped %d attribute(s) duplicating the "
                    "child_dependent_key: %s",
                    sat.name, len(removed), removed,
                )
                # WP16 §2.3: a backstop fire is the evidence that the `cdk_not_payload`
                # steering line is still needed. Counted only when it actually repairs
                # something — a clean model emits nothing.
                emit_trace(
                    TraceEvent(
                        kind="backstop",
                        backstop_id="attributes_without_cdk",
                        detail={
                            "rule": "cdk_not_payload",
                            "satellite": sat.name,
                            "dropped": removed,
                        },
                    )
                )
                sat.attributes = deduped
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
                # Attribute the drop when the record still carries a usable name (WP21 §2.6):
                # every other DROPPED_RECORD flag names its construct, and a reviewer cannot
                # act on "one hub was invalid" without knowing which one. A record too broken
                # to carry a name stays unattributed rather than inventing one.
                raw_name = record.get("name") if isinstance(record, dict) else None
                asset = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else None
                state.flag(
                    "dv2_modeler",
                    f"dropped invalid {label}: {exc.error_count()} error(s)",
                    kind=FlagKind.DROPPED_RECORD,
                    asset=asset,
                )
        return items
