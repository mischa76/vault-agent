"""Unit tests for the Data Contract agent.

The deterministic core is exercised with a stubbed enricher, so these run in CI without an
Anthropic API key. They cover the acceptance criteria in
``docs/architecture/data-contract-agent-spec.md``: schema-valid specs, JSON↔YAML round-trip,
business-key → primaryKey/not-null propagation, hard/soft failure modes, dbt tests that
correspond 1:1 to enforceable constraints, and gaps flagged (never guessed).
"""
import json
from typing import Any

import yaml

from vault_agent.agents.data_contract import ContractEnricher, DataContractAgent
from vault_agent.models.contract import DataContract
from vault_agent.state import (
    Artifacts,
    BusinessKeyCandidate,
    SourceTable,
    VaultAgentState,
)


class _StubEnricher:
    """Returns canned enrichment keyed by asset name (no API key)."""

    def __init__(self, assets: dict[str, Any] | None = None) -> None:
        self._assets = assets or {}

    async def enrich(self, *, system_prompt: str, assets_json: str) -> dict[str, Any]:
        self.system_prompt = system_prompt
        self.assets_json = assets_json
        return self._assets


def _grounded_state() -> VaultAgentState:
    return VaultAgentState(
        source_schemas=[
            SourceTable(
                table="customer",
                columns=["national_customer_id", "customer_name", "status"],
            ),
        ],
        business_keys=[
            BusinessKeyCandidate(
                entity="customer", field="national customer ID", score=0.9,
                rationale="natural key",
            ),
        ],
    )


def _agent(assets: dict[str, Any] | None = None) -> DataContractAgent:
    enricher: ContractEnricher = _StubEnricher(assets)
    return DataContractAgent(enricher=enricher)


async def test_one_contract_per_source_table_schema_valid() -> None:
    result = await _agent().run(_grounded_state())

    assert len(result.artifacts.contracts) == 1
    raw = result.artifacts.contracts[0]
    # Round-trips through the model with the book's hyphenated/aliased keys.
    contract = DataContract.model_validate(raw)
    assert contract.name == "customer"
    assert contract.namespace == "source"
    assert contract.dataAssetResourceName == "datastore://source/customer"
    assert {f.name for f in contract.fields} == {
        "national_customer_id", "customer_name", "status",
    }


async def test_business_key_becomes_primary_key_not_null() -> None:
    result = await _agent().run(_grounded_state())
    contract = DataContract.model_validate(result.artifacts.contracts[0])

    pk = next(f for f in contract.fields if f.name == "national_customer_id")
    assert pk.constraints.primaryKey is True
    assert pk.constraints.is_nullable is False
    assert pk.failure_mode == "hard"  # schema-level breach blocks

    other = next(f for f in contract.fields if f.name == "customer_name")
    assert other.constraints.primaryKey is False
    assert other.constraints.is_nullable is True  # never widened, but not narrowed either


async def test_json_yaml_round_trip_lossless() -> None:
    result = await _agent().run(_grounded_state())
    raw = result.artifacts.contracts[0]

    assert json.loads(json.dumps(raw)) == raw
    assert yaml.safe_load(yaml.safe_dump(raw)) == raw
    assert "spec-version" in raw and "schema" in raw  # aliased keys present


async def test_dbt_tests_match_enforceable_constraints() -> None:
    enrichment = {
        "customer": {
            "doc": "The customer master asset.",
            "fields": {
                "status": {"data_type": "string", "enum": ["active", "closed"]},
                "customer_name": {"data_type": "string"},
            },
        }
    }
    result = await _agent(enrichment).run(_grounded_state())

    assert "customer" in result.artifacts.dbt_tests
    doc = yaml.safe_load(result.artifacts.dbt_tests["customer"])
    assert doc["version"] == 2
    model = doc["models"][0]
    assert model["name"] == "stg_customer"
    cols = {c["name"]: c["tests"] for c in model["columns"]}
    # Primary key → unique + not_null; enum → accepted_values; plain field → no tests.
    assert cols["NATIONAL_CUSTOMER_ID"] == ["unique", "not_null"]
    assert {"accepted_values": {"values": ["active", "closed"]}} in cols["STATUS"]
    assert "CUSTOMER_NAME" not in cols


async def test_enrichment_merged_into_contract() -> None:
    enrichment = {
        "customer": {
            "doc": "The customer master asset.",
            "fields": {
                "customer_name": {
                    "description": "Full legal name.",
                    "data_type": "string",
                    "examples": ["Acme AG"],
                    "semantics": [{"kind": "charLength", "value": 200}],
                },
            },
        }
    }
    result = await _agent(enrichment).run(_grounded_state())
    contract = DataContract.model_validate(result.artifacts.contracts[0])

    assert contract.doc == "The customer master asset."
    name_field = next(f for f in contract.fields if f.name == "customer_name")
    assert name_field.description == "Full legal name."
    assert name_field.constraints.data_type == "string"
    assert name_field.examples == ["Acme AG"]
    assert name_field.semantics[0].kind == "charLength"
    assert name_field.semantics[0].failure_mode == "soft"  # semantics default to soft


async def test_owner_is_flagged_placeholder_never_invented() -> None:
    result = await _agent().run(_grounded_state())
    contract = DataContract.model_validate(result.artifacts.contracts[0])

    assert contract.owner.name == "TODO: assign"
    assert contract.owner.email is None
    assert any("placeholder owner" in e.message for e in result.flags)


async def test_unknown_type_is_flagged_not_guessed() -> None:
    # No enrichment at all → every type stays 'unknown' and is flagged.
    result = await _agent().run(_grounded_state())
    contract = DataContract.model_validate(result.artifacts.contracts[0])

    assert all(f.constraints.data_type == "unknown" for f in contract.fields)
    assert any("undetermined type" in e.message for e in result.flags)


async def test_falls_back_to_business_entities_without_schema() -> None:
    state = VaultAgentState(
        business_keys=[
            BusinessKeyCandidate(entity="account", field="account number", score=0.8,
                                 rationale="key"),
        ],
    )
    result = await _agent().run(state)

    assert len(result.artifacts.contracts) == 1
    contract = DataContract.model_validate(result.artifacts.contracts[0])
    assert contract.name == "account"
    pk = contract.fields[0]
    assert pk.name == "account number"
    assert pk.constraints.primaryKey is True
    # Without a declared schema, types were inferred from prose → flagged for review.
    assert any("no source schema" in e.message for e in result.flags)


async def test_no_inputs_records_error_and_no_contracts() -> None:
    result = await _agent().run(VaultAgentState())

    assert result.artifacts.contracts == []
    assert result.artifacts.dbt_tests == {}
    assert any("nothing to contract" in e.message for e in result.flags)


async def test_decision_logged() -> None:
    result = await _agent().run(_grounded_state())
    assert result.decisions[-1] == {
        "agent": "data_contract", "contracts": 1, "dbt_test_files": 1, "grounded": True,
    }


async def test_grounding_section_passed_to_enricher() -> None:
    enricher = _StubEnricher()
    await DataContractAgent(enricher=enricher).run(_grounded_state())
    # Declared columns are rendered into the system prompt (ADR-0004 grounding).
    assert "national_customer_id" in enricher.system_prompt


class _RecordingEnricher:
    """Records each call's payload and answers per-asset (mirrors the real batched call)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def enrich(self, *, system_prompt: str, assets_json: str) -> dict[str, Any]:
        payload = json.loads(assets_json)
        self.calls.append(payload)
        # A well-behaved enricher answers only for the asset(s) it was given.
        return {name: {"doc": f"doc for {name}", "fields": {}} for name in payload}


async def test_enrichment_is_batched_one_asset_per_call() -> None:
    """The truncation fix: each asset is enriched in its own bounded call (not one combined
    call that would cap the whole schema at max_tokens), so a wide schema still completes."""
    state = VaultAgentState(
        source_schemas=[
            SourceTable(table="customer", columns=["national_customer_id", "customer_name"]),
            SourceTable(table="account", columns=["account_number", "balance"]),
            SourceTable(table="contract", columns=["contract_number", "premium"]),
        ],
        business_keys=[
            BusinessKeyCandidate(entity="customer", field="national customer ID",
                                 score=0.9, rationale="key"),
        ],
    )
    enricher = _RecordingEnricher()
    result = await DataContractAgent(enricher=enricher).run(state)

    # One call per source table, each carrying exactly that one asset.
    assert len(enricher.calls) == 3
    assert [set(call) for call in enricher.calls] == [
        {"customer"}, {"account"}, {"contract"},
    ]
    # Every asset was still contracted and enriched from its own call.
    assert len(result.artifacts.contracts) == 3
    docs = {c["name"]: c["doc"] for c in result.artifacts.contracts}
    assert docs == {
        "customer": "doc for customer",
        "account": "doc for account",
        "contract": "doc for contract",
    }


class _EchoTypeEnricher:
    """Enriches every field it is handed with a concrete type — so a field left 'unknown'
    proves that chunk was never sent (chunk-coverage check)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def enrich(self, *, system_prompt: str, assets_json: str) -> dict[str, Any]:
        payload = json.loads(assets_json)
        self.calls.append(payload)
        return {
            name: {"doc": f"doc {name}", "fields": {c: {"data_type": "string"} for c in cols}}
            for name, cols in payload.items()
        }


async def test_wide_table_is_chunked_and_fully_enriched() -> None:
    """A 256-attribute source table enriches over several bounded calls (each <=
    _FIELDS_PER_CALL fields) with every field covered — a single call would overflow the
    output budget and raise LLMCallError (WP3)."""
    import math

    from vault_agent.agents.data_contract import _FIELDS_PER_CALL

    cols = [f"col_{i}" for i in range(256)]
    state = VaultAgentState(source_schemas=[SourceTable(table="wide", columns=cols)])
    enricher = _EchoTypeEnricher()
    result = await DataContractAgent(enricher=enricher).run(state)

    # Split into ceil(256 / _FIELDS_PER_CALL) calls, all for the one asset, none over budget.
    assert len(enricher.calls) == math.ceil(256 / _FIELDS_PER_CALL)
    assert all(set(call) == {"wide"} for call in enricher.calls)
    assert all(len(call["wide"]) <= _FIELDS_PER_CALL for call in enricher.calls)

    # All 256 fields are present and every one was enriched (chunk coverage: none left over).
    contract = DataContract.model_validate(result.artifacts.contracts[0])
    assert len(contract.fields) == 256
    assert all(f.constraints.data_type == "string" for f in contract.fields)


def test_write_outputs_persists_contracts(tmp_path: Any) -> None:
    from vault_agent.cli import write_outputs

    state = VaultAgentState(
        artifacts=Artifacts(
            contracts=[{"name": "customer", "namespace": "source"}],
            dbt_tests={"customer": "version: 2\n"},
        )
    )
    counts = write_outputs(state, tmp_path)

    assert counts["contracts"] == 1
    assert (tmp_path / "contracts" / "customer.contract.yml").exists()
    assert (tmp_path / "contracts" / "customer.tests.yml").read_text() == "version: 2\n"
