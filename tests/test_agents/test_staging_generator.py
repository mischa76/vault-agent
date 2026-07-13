"""Unit tests for the staging-layer generator (deterministic, no API key).

The fixture mirrors the bank end-to-end PoC (demo/bank_postgres) so the generated staging
models can be asserted against the hand-authored ones the Postgres run verified: same
hash keys, same hashdiffs, same APPLIED_DTS derivation on the eff_sat parent.
"""
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.staging_generator import (
    PROJECT_NAME,
    build_staging,
    collect_staging_specs,
)
from vault_agent.rules.dv2_rules import AUTOMATE_DV_VERSION
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    Link,
    Satellite,
    SourceTable,
    VaultAgentState,
)


def _bank_model() -> DVModel:
    """The bank end-to-end PoC shape: 2 hubs, 1 link with driving key, 2 sats, 1 eff_sat."""
    return DVModel(
        hubs=[
            Hub(name="hub_customer", business_key="national customer ID",
                source_entity="customer", description="a customer"),
            Hub(name="hub_account", business_key="account number",
                source_entity="account", description="an account"),
        ],
        links=[
            Link(name="link_account_customer",
                 connected_hubs=["hub_account", "hub_customer"],
                 description="ownership", driving_key=["hub_account"]),
        ],
        satellites=[
            Satellite(name="sat_customer_details", parent="hub_customer",
                      attributes=["customer name", "date of birth"],
                      description="customer payload"),
            Satellite(name="sat_account_details", parent="hub_account",
                      attributes=["balance", "status"], description="account payload"),
            Satellite(name="sat_account_customer_eff", parent="link_account_customer",
                      attributes=["effective from", "effective to"],
                      description="ownership validity", sat_type="effectivity"),
        ],
    )


def test_collects_one_staging_model_per_source() -> None:
    specs = collect_staging_specs(_bank_model())
    assert set(specs) == {"stg_customer", "stg_account", "stg_account_customer"}


def test_hub_staging_matches_the_verified_demo_shape() -> None:
    specs = collect_staging_specs(_bank_model())
    customer = specs["stg_customer"]

    assert customer.hashed == [
        ("CUSTOMER_HK", "NATIONAL_CUSTOMER_ID"),
        ("CUSTOMER_DETAILS_HASHDIFF", customer.hashed[1][1]),
    ]
    hashdiff = customer.hashed[1][1]
    assert getattr(hashdiff, "columns", None) == ["CUSTOMER_NAME", "DATE_OF_BIRTH"]
    assert customer.source_columns == [
        "NATIONAL_CUSTOMER_ID", "CUSTOMER_NAME", "DATE_OF_BIRTH",
        "LOAD_DATETIME", "RECORD_SOURCE",
    ]


def test_link_staging_hashes_both_hubs_and_the_link() -> None:
    specs = collect_staging_specs(_bank_model())
    link = specs["stg_account_customer"]

    names = [name for name, _ in link.hashed]
    assert names == ["ACCOUNT_HK", "CUSTOMER_HK", "LINK_ACCOUNT_CUSTOMER_HK"]
    # The link HK is a multi-column hash over the BKs in connected_hubs order.
    assert link.hashed[2][1] == ["ACCOUNT_NUMBER", "NATIONAL_CUSTOMER_ID"]


def test_eff_sat_parent_gets_the_applied_dts_derived_column() -> None:
    specs = collect_staging_specs(_bank_model())
    link = specs["stg_account_customer"]

    # src_eff is a DEDICATED derived column carrying the start date (the Postgres
    # "specified more than once" fix — rules.EFFECTIVITY_APPLIED_COLUMN).
    assert link.derived == {"APPLIED_DTS": "EFFECTIVE_FROM"}
    assert "EFFECTIVE_FROM" in link.source_columns
    assert "EFFECTIVE_TO" in link.source_columns


def test_rendered_stage_model_calls_automate_dv_stage() -> None:
    result = build_staging(_bank_model(), source_schemas=[])
    sql = result.models["stg_customer"]

    assert "{{ config(materialized='view') }}" in sql
    assert "automate_dv.stage(include_source_columns=true" in sql
    assert "source_model: 'raw_customer'" in sql
    assert "CUSTOMER_HK: 'NATIONAL_CUSTOMER_ID'" in sql
    assert "is_hashdiff: true" in sql
    assert "derived_columns=none," in sql

    link_sql = result.models["stg_account_customer"]
    assert "APPLIED_DTS: 'EFFECTIVE_FROM'" in link_sql
    assert "derived_columns=metadata_dict['derived_columns']," in link_sql


def test_unmatched_binding_is_inferred_and_flagged() -> None:
    result = build_staging(_bank_model(), source_schemas=[])

    assert {f.kind for f in result.flags} == {FlagKind.SOURCE_BINDING}
    assert {f.asset for f in result.flags} == {
        "stg_customer", "stg_account", "stg_account_customer",
    }
    assert all(f.severity == "advisory" for f in result.flags)


def test_declared_source_table_binds_verbatim_without_a_flag() -> None:
    # No schema/database declared -> bare relation names, exactly as before WP7 §7.2
    # (a dbt source without a schema property would default its schema to the source
    # NAME, silently breaking the verified bare-name/seed pattern — so no location
    # declared means no source() binding).
    schemas = [
        SourceTable(table="raw_customer", columns=["NATIONAL_CUSTOMER_ID"]),
        SourceTable(table="ACCOUNT", columns=["ACCOUNT_NUMBER"]),  # matches by base name
    ]
    result = build_staging(_bank_model(), source_schemas=schemas)

    assert "source_model: 'raw_customer'" in result.models["stg_customer"]
    assert "source_model: 'ACCOUNT'" in result.models["stg_account"]
    # Only the link staging is unmatched and flagged.
    assert {f.asset for f in result.flags} == {"stg_account_customer"}


def test_grounded_run_with_locations_binds_staging_through_source_refs() -> None:
    """WP7 §7.2: declared schema/database -> source() mapping form + real sources.yml."""
    schemas = [
        SourceTable(table="raw_customer", columns=["NATIONAL_CUSTOMER_ID"],
                    schema_name="core", database="bank"),
        SourceTable(table="raw_account", columns=["ACCOUNT_NUMBER"],
                    schema_name="core", database="bank"),
    ]
    result = build_staging(_bank_model(), source_schemas=schemas)

    sql = result.models["stg_customer"]
    assert "source_model:\n  raw: 'raw_customer'" in sql
    assert "source_model: 'raw_customer'" not in sql
    sources = result.scaffolding["models/staging/sources.yml"]
    assert "  - name: raw\n    database: bank\n    schema: core\n    tables:" in sources
    assert "      - name: raw_customer" in sources
    assert "      - name: raw_account" in sources
    # The unmatched link staging stays a bare-name reference, documented + flagged.
    assert "source_model: 'raw_account_customer'" in result.models["stg_account_customer"]
    assert "#   - raw_account_customer (feeds stg_account_customer)" in sources
    assert {f.asset for f in result.flags} == {"stg_account_customer"}
    # Metadata mirrors the mapping form so downstream consumers see the real binding.
    assert result.metadata["stg_customer"]["source_model"] == {"raw": "raw_customer"}


def test_mixed_schemas_get_one_source_block_each_deterministically() -> None:
    """WP7 §7.2: one block per distinct (database, schema), named raw, raw_2, ... in
    staging-spec insertion order (hubs first: customer before account here)."""
    schemas = [
        SourceTable(table="raw_account", columns=["ACCOUNT_NUMBER"], schema_name="ops"),
        SourceTable(table="raw_customer", columns=["NATIONAL_CUSTOMER_ID"],
                    schema_name="core"),
    ]
    result = build_staging(_bank_model(), source_schemas=schemas)

    # stg_customer is collected first -> its schema 'core' claims the name 'raw'.
    assert "source_model:\n  raw: 'raw_customer'" in result.models["stg_customer"]
    assert "source_model:\n  raw_2: 'raw_account'" in result.models["stg_account"]
    sources = result.scaffolding["models/staging/sources.yml"]
    assert sources.index("- name: raw\n") < sources.index("- name: raw_2\n")
    assert "    schema: core" in sources and "    schema: ops" in sources


def test_scaffolding_makes_a_runnable_project() -> None:
    result = build_staging(_bank_model(), source_schemas=[])

    assert set(result.scaffolding) == {
        "dbt_project.yml", "packages.yml", "models/staging/sources.yml", "README.md",
    }
    project = result.scaffolding["dbt_project.yml"]
    assert f"name: '{PROJECT_NAME}'" in project
    assert "+quote_columns: false" in project
    assert "+materialized: view" in project and "+materialized: incremental" in project
    assert AUTOMATE_DV_VERSION in result.scaffolding["packages.yml"]
    sources = result.scaffolding["models/staging/sources.yml"]
    assert "- name: raw_customer" in sources
    assert "NATIONAL_CUSTOMER_ID" in sources


def test_transactional_link_payload_passes_through_unhashed() -> None:
    model = _bank_model()
    model.links.append(
        Link(name="link_transaction", connected_hubs=["hub_account", "hub_customer"],
             description="a transaction", link_type="transactional",
             payload=["amount", "currency"], event_timestamp="booked at"),
    )
    specs = collect_staging_specs(model)
    txn = specs["stg_transaction"]

    names = [name for name, _ in txn.hashed]
    assert names == ["ACCOUNT_HK", "CUSTOMER_HK", "LINK_TRANSACTION_HK"]
    for col in ("AMOUNT", "CURRENCY", "BOOKED_AT"):
        assert col in txn.source_columns


def test_ma_sat_with_source_table_gets_its_own_staging_spec() -> None:
    """WP7 §7.1: finer-grain multi-active rows staged from their own declared relation —
    parent HK (hashed from the parent's BK), own hashdiff, cdk + attrs; bound verbatim."""
    model = _bank_model()
    model.satellites.append(
        Satellite(name="sat_customer_address", parent="hub_customer",
                  attributes=["street", "city"], description="addresses",
                  sat_type="multi_active", child_dependent_key=["address type"],
                  source_table="raw_customer_address"),
    )
    result = build_staging(model, source_schemas=[])
    spec = collect_staging_specs(model)["stg_customer_address"]

    assert spec.source_model == "raw_customer_address"
    assert spec.bound is True
    names = [name for name, _ in spec.hashed]
    assert names == ["CUSTOMER_HK", "CUSTOMER_ADDRESS_HASHDIFF"]
    assert spec.hashed[0][1] == "NATIONAL_CUSTOMER_ID"  # parent BK exists in the relation
    assert getattr(spec.hashed[1][1], "columns", None) == ["STREET", "CITY"]
    assert spec.source_columns == [
        "NATIONAL_CUSTOMER_ID", "STREET", "CITY", "ADDRESS_TYPE",
        "LOAD_DATETIME", "RECORD_SOURCE",
    ]
    # The parent's staging is untouched by the finer-grain payload.
    parent = collect_staging_specs(model)["stg_customer"]
    assert "STREET" not in parent.source_columns
    # Declared binding: rendered verbatim, never flagged.
    assert "source_model: 'raw_customer_address'" in result.models["stg_customer_address"]
    assert "stg_customer_address" not in {f.asset for f in result.flags}


def test_ma_sat_without_source_table_shares_the_parent_staging() -> None:
    model = _bank_model()
    model.satellites.append(
        Satellite(name="sat_customer_address", parent="hub_customer",
                  attributes=["street", "city"], description="addresses",
                  sat_type="multi_active", child_dependent_key=["address type"]),
    )
    specs = collect_staging_specs(model)

    assert "stg_customer_address" not in specs
    assert "STREET" in specs["stg_customer"].source_columns


def test_skipped_constructs_get_no_staging() -> None:
    model = DVModel(
        hubs=[Hub(name="hub_customer", business_key="id", source_entity="customer",
                  description="c")],
        links=[Link(name="link_ghost", connected_hubs=["hub_customer", "hub_missing"],
                    description="dangling")],
        satellites=[Satellite(name="sat_orphan", parent="link_ghost",
                              attributes=["x"], description="orphan")],
    )
    specs = collect_staging_specs(model)
    assert set(specs) == {"stg_customer"}


async def test_agent_wires_staging_into_artifacts_and_metadata() -> None:
    state = VaultAgentState(dv_model=_bank_model())
    result = await CodeGeneratorAgent().run(state)

    assert set(result.artifacts.staging_models) == {
        "stg_customer", "stg_account", "stg_account_customer",
    }
    assert set(result.artifacts.scaffolding) == {
        "dbt_project.yml", "packages.yml", "models/staging/sources.yml", "README.md",
    }
    staging_meta = result.artifacts.automatedv_yaml["staging"]
    assert staging_meta["stg_account_customer"]["derived_columns"] == {
        "APPLIED_DTS": "EFFECTIVE_FROM"
    }
    assert result.decisions[-1]["staging_models"] == 3
    # Ungrounded run: the three inferred bindings are advisory flags, nothing else.
    assert {f.kind for f in result.flags} == {FlagKind.SOURCE_BINDING}


def _contract(name: str, fields: list[dict]) -> dict:
    """A minimal contract dict in the DataContract.to_dict() shape (WP7 §7.3)."""
    return {"spec-version": "1.0.0", "name": name, "namespace": "source",
            "schema": [
                {"name": f["name"],
                 "constraints": {"data_type": f.get("data_type", "unknown")},
                 "semantics": f.get("semantics", [])}
                for f in fields
            ]}


def test_contract_types_pin_seed_column_types_per_the_mapping_table() -> None:
    """WP7 §7.3: string→varchar, integer→bigint, number→numeric, boolean→boolean,
    string+format=date→date, …date-time→timestamp, union takes the non-null member,
    unknown is omitted; LOAD_DATETIME/RECORD_SOURCE always timestamp/varchar."""
    contracts = [_contract("raw_customer", [
        {"name": "national customer ID", "data_type": "string"},
        {"name": "customer count", "data_type": "integer"},
        {"name": "balance", "data_type": "number"},
        {"name": "is active", "data_type": "boolean"},
        {"name": "date of birth", "data_type": "string",
         "semantics": [{"kind": "format", "value": "date"}]},
        {"name": "updated at", "data_type": "string",
         "semantics": [{"kind": "format", "value": "date-time"}]},
        {"name": "customer name", "data_type": ["null", "string"]},
        {"name": "mystery", "data_type": "unknown"},
        {"name": "ambiguous", "data_type": ["null", "string", "integer"]},
    ])]
    result = build_staging(_bank_model(), source_schemas=[], contracts=contracts)

    project = result.scaffolding["dbt_project.yml"]
    assert "    raw_customer:\n      +column_types:" in project
    for line in (
        "        NATIONAL_CUSTOMER_ID: varchar",
        "        CUSTOMER_COUNT: bigint",
        "        BALANCE: numeric",
        "        IS_ACTIVE: boolean",
        "        DATE_OF_BIRTH: date",
        "        UPDATED_AT: timestamp",
        "        CUSTOMER_NAME: varchar",  # union ["null", "string"] → non-null member
        "        LOAD_DATETIME: timestamp",
        "        RECORD_SOURCE: varchar",
    ):
        assert line in project, line
    assert "MYSTERY" not in project  # unknown → omitted (dbt inference, as today)
    assert "AMBIGUOUS" not in project  # multi-type union → omitted, never guessed


def test_unmatched_contracts_leave_dbt_project_unchanged() -> None:
    """Ungrounded entity contracts ('customer') never match a raw_* staging source, so
    passing them changes nothing — part of the WP7 byte-identity guarantee."""
    contracts = [_contract("customer", [{"name": "customer name", "data_type": "string"}])]
    with_contracts = build_staging(_bank_model(), source_schemas=[], contracts=contracts)
    without = build_staging(_bank_model(), source_schemas=[])

    assert with_contracts.scaffolding == without.scaffolding
    assert with_contracts.models == without.models


async def test_agent_passes_contracts_from_state_to_the_staging_pass() -> None:
    """The graph runs data_contract before code_generator (ADR-0005/0006), so the drafted
    contracts sit in state.artifacts when the staging pass needs them (WP7 §7.3)."""
    state = VaultAgentState(dv_model=_bank_model())
    state.artifacts.contracts = [
        _contract("raw_customer", [{"name": "customer name", "data_type": "string"}])
    ]
    result = await CodeGeneratorAgent().run(state)

    project = result.artifacts.scaffolding["dbt_project.yml"]
    assert "    raw_customer:\n      +column_types:" in project
    assert "        CUSTOMER_NAME: varchar" in project
