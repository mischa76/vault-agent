"""Data Contract agent (ADR-0005).

Generates a **draft data contract** for each source-to-staging data asset, plus the dbt
schema tests that let the prevention layer enforce it inside the existing dbt pipeline.
The agent bootstraps the producer/consumer negotiation — it does *not* finalize ownership
or declare a contract "agreed"; that is a human-in-the-loop decision.

Owns ``state.artifacts.contracts`` and ``state.artifacts.dbt_tests``.

LLM vs deterministic split (see the design spec / ADR-0005):

- **Deterministic** (runs in CI without an API key): which assets/fields to contract,
  propagating business keys to ``primaryKey: true`` / ``is_nullable: false``, assigning
  hard/soft failure modes, the placeholder owner, dbt-test emission, and serialization.
- **LLM-driven** (the injectable :class:`ContractEnricher`): the ``doc`` text, per-field
  descriptions/examples, type inference from prose, and value-level semantic constraints.

The enricher is injectable so the deterministic core is fully unit-tested without a key,
consistent with the other agents. Gaps are **flagged for human review** (via
``state.errors``), never guessed: a placeholder owner, a missing source schema, or a field
whose type could not be determined each surface a flag.
"""
import json
from typing import Any, Protocol, cast

from vault_agent.agents.base import BaseAgent
from vault_agent.grounding import render_schema_prompt_section
from vault_agent.models.contract import (
    ContractField,
    ContractOwner,
    DataContract,
    FieldConstraints,
    SemanticConstraint,
)
from vault_agent.rules.dv2_rules import STAGING_PREFIX, normalize_identifier
from vault_agent.state import VaultAgentState

_TOOL_NAME = "emit_contract_enrichment"
_MAX_TOKENS = 4096
_NAMESPACE = "source"


def _tool_schema() -> dict[str, Any]:
    """Schema for the LLM enrichment: per-asset ``doc`` + per-field prose-derived detail.

    Asset and field names are data, so both nest under ``additionalProperties`` rather than
    being fixed keys. Nullability and primary-key status are deliberately absent — those are
    propagated deterministically from the business keys, never asked of the LLM."""
    semantic_schema = {
        "type": "object",
        "properties": {
            "kind": {"type": "string"},
            "value": {"type": ["string", "number", "boolean", "null"]},
            "failure_mode": {"type": "string", "enum": ["hard", "soft"]},
        },
        "required": ["kind"],
    }
    field_schema = {
        "type": "object",
        "properties": {
            "description": {"type": "string"},
            "data_type": {
                "description": (
                    "A JSON Schema base type (string/number/integer/object/array/boolean/"
                    "null), a union list like ['null', 'string'] for an optional field, or "
                    "'unknown' if it genuinely cannot be determined — never guess."
                ),
            },
            "examples": {"type": "array", "items": {"type": "string"}},
            "enum": {"type": "array", "items": {"type": "string"}},
            "semantics": {"type": "array", "items": semantic_schema},
        },
    }
    asset_schema = {
        "type": "object",
        "properties": {
            "doc": {"type": "string"},
            "fields": {"type": "object", "additionalProperties": field_schema},
        },
    }
    return {
        "type": "object",
        "properties": {"assets": {"type": "object", "additionalProperties": asset_schema}},
        "required": ["assets"],
    }


class ContractEnricher(Protocol):
    """Turns the asset/field skeleton into prose-derived enrichment, keyed by asset name.

    Implemented for real by :class:`AnthropicContractEnricher`; stubbed in tests.
    """

    async def enrich(
        self, *, system_prompt: str, assets_json: str
    ) -> dict[str, Any]: ...


class AnthropicContractEnricher:
    """Default enricher backed by the Anthropic Messages API (forced tool-use)."""

    def __init__(self, model: str | None = None) -> None:
        # Imported lazily so importing this module never requires an API key.
        from anthropic import AsyncAnthropic

        from vault_agent.config import get_settings

        settings = get_settings()
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = model or settings.primary_model

    async def enrich(self, *, system_prompt: str, assets_json: str) -> dict[str, Any]:
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            tools=[
                {
                    "name": _TOOL_NAME,
                    "description": "Emit prose-derived enrichment for the data assets.",
                    "input_schema": _tool_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
            messages=[{"role": "user", "content": assets_json}],
        )
        for block in message.content:
            if block.type == "tool_use" and block.name == _TOOL_NAME:
                payload = cast(dict[str, Any], block.input)
                return cast(dict[str, Any], payload.get("assets", {}))
        return {}


class DataContractAgent(BaseAgent):
    """Drafts a JSON-Schema-based data contract (+ dbt tests) per source-to-staging asset."""

    prompt_path = "data_contract.md"  # type: ignore[assignment]

    def __init__(self, enricher: ContractEnricher | None = None) -> None:
        self._enricher = enricher

    def _get_enricher(self) -> ContractEnricher:
        if self._enricher is None:
            self._enricher = AnthropicContractEnricher()
        return self._enricher

    def _build_system_prompt(self, state: VaultAgentState) -> str:
        template = self.load_prompt()
        return f"{template}{render_schema_prompt_section(state.source_schemas)}"

    @staticmethod
    def _assets(state: VaultAgentState) -> list[tuple[str, list[str]]]:
        """The (asset_name, field_labels) units to contract.

        Prefer the declared source schema — one contract per source table. With no schema,
        fall back to the business entities (one contract per entity, fields = its proposed
        business keys), and flag that types were inferred from prose rather than a schema."""
        if state.source_schemas:
            return [(t.table, list(t.columns)) for t in state.source_schemas]
        by_entity: dict[str, list[str]] = {}
        for bk in state.business_keys:
            fields = by_entity.setdefault(bk.entity, [])
            if bk.field not in fields:
                fields.append(bk.field)
        return list(by_entity.items())

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        assets = self._assets(state)
        if not assets:
            state.errors.append(
                "data_contract: no source schemas and no business keys; nothing to "
                "contract (run the requirements/business-key agents, or declare a schema)"
            )
            return state

        grounded = bool(state.source_schemas)
        system_prompt = self._build_system_prompt(state)
        assets_json = json.dumps({name: cols for name, cols in assets}, indent=2)
        enricher = self._get_enricher()
        enrichment = await enricher.enrich(
            system_prompt=system_prompt, assets_json=assets_json
        )

        # Business-key fields drive primaryKey / not-null. Matched normalised so a business
        # label ("national customer ID") propagates to a NATIONAL_CUSTOMER_ID column.
        bk_fields = {normalize_identifier(bk.field) for bk in state.business_keys}

        contracts: list[dict[str, Any]] = []
        dbt_tests: dict[str, str] = {}
        for name, cols in assets:
            asset_enrichment = enrichment.get(name, {}) if isinstance(enrichment, dict) else {}
            contract = self._build_contract(
                name, cols, bk_fields, asset_enrichment, grounded=grounded, state=state
            )
            contracts.append(contract.to_dict())
            tests_yaml = self._render_dbt_tests(name, contract)
            if tests_yaml:
                dbt_tests[name] = tests_yaml

        state.artifacts.contracts = contracts
        state.artifacts.dbt_tests = dbt_tests
        state.decisions.append(
            {
                "agent": "data_contract",
                "contracts": len(contracts),
                "dbt_test_files": len(dbt_tests),
                "grounded": grounded,
            }
        )
        return state

    def _build_contract(
        self,
        name: str,
        cols: list[str],
        bk_fields: set[str],
        enrichment: dict[str, Any],
        *,
        grounded: bool,
        state: VaultAgentState,
    ) -> DataContract:
        # Field enrichment keyed by normalised label, so the LLM may key by either the
        # business label or the physical column and still match.
        raw_fields = enrichment.get("fields", {}) if isinstance(enrichment, dict) else {}
        field_enrichment = {
            normalize_identifier(label): detail
            for label, detail in raw_fields.items()
            if isinstance(detail, dict)
        }

        fields: list[ContractField] = []
        for label in cols:
            norm = normalize_identifier(label)
            detail = field_enrichment.get(norm, {})
            is_pk = norm in bk_fields
            data_type = detail.get("data_type", "unknown")
            constraints = FieldConstraints(
                primaryKey=is_pk,
                data_type=data_type,
                enum=list(detail.get("enum", [])),
                # A business key is the natural identifier: required and stable. Otherwise
                # default to nullable — never widen beyond what we can justify.
                is_nullable=not is_pk,
            )
            fields.append(
                ContractField(
                    name=label,
                    description=str(detail.get("description", "")),
                    examples=[str(e) for e in detail.get("examples", [])],
                    constraints=constraints,
                    semantics=self._parse_semantics(detail.get("semantics", [])),
                )
            )
            if data_type == "unknown":
                state.errors.append(
                    f"data_contract: field {name}.{label!r} has an undetermined type; "
                    f"review required before the contract is agreed"
                )

        owner = ContractOwner.placeholder()
        doc = str(enrichment.get("doc", "")) or (
            f"Draft data contract for the '{name}' source-to-staging asset."
        )
        contract = DataContract(
            name=name,
            namespace=_NAMESPACE,
            dataAssetResourceName=f"datastore://{_NAMESPACE}/{name}",
            doc=doc,
            owner=owner,
        )
        # Assigned rather than passed to the constructor: ``fields`` serialises under the
        # alias ``schema``, which the pydantic-mypy plugin keys the init kwarg on.
        contract.fields = fields

        # Always flag the placeholder owner — the agent never invents a real one.
        state.errors.append(
            f"data_contract: contract {name!r} has a placeholder owner; assign a real "
            f"owner at the human-in-the-loop checkpoint"
        )
        if not grounded:
            state.errors.append(
                f"data_contract: no source schema for {name!r}; field types/constraints "
                f"were inferred from prose — review against the real source"
            )
        return contract

    @staticmethod
    def _parse_semantics(raw: Any) -> list[SemanticConstraint]:
        """Build value-level constraints from enrichment, dropping malformed entries."""
        out: list[SemanticConstraint] = []
        if not isinstance(raw, list):
            return out
        for item in raw:
            if not isinstance(item, dict) or "kind" not in item:
                continue
            out.append(
                SemanticConstraint(
                    kind=str(item["kind"]),
                    value=item.get("value"),
                    failure_mode=item.get("failure_mode", "soft"),
                )
            )
        return out

    @staticmethod
    def _render_dbt_tests(name: str, contract: DataContract) -> str:
        """Emit a dbt properties-file (schema-test) YAML for the asset's staging model.

        Deterministic, derived 1:1 from the enforceable schema constraints: primary keys →
        ``unique`` + ``not_null``; not-null fields → ``not_null``; enums →
        ``accepted_values``. Column names are normalised to match the staging columns the
        code generator emits. Returns '' when nothing is enforceable, so the agent omits an
        empty file."""
        import yaml

        columns: list[dict[str, Any]] = []
        for field in contract.fields:
            tests: list[Any] = []
            if field.constraints.primaryKey:
                tests.extend(["unique", "not_null"])
            elif not field.constraints.is_nullable:
                tests.append("not_null")
            if field.constraints.enum:
                tests.append(
                    {"accepted_values": {"values": list(field.constraints.enum)}}
                )
            if tests:
                columns.append({"name": normalize_identifier(field.name), "tests": tests})

        if not columns:
            return ""
        doc = {
            "version": 2,
            "models": [{"name": STAGING_PREFIX + name, "columns": columns}],
        }
        return cast(str, yaml.safe_dump(doc, sort_keys=False))
