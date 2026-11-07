"""WP120 — a catalogue read from the landing zone (C47 stage 1, C48): the type rules know
PostgreSQL's spellings beside SQL Server's, and the naming profile's technical columns a landing
table carries are no source columns of the model. Committed red before the change. Keyless."""
from __future__ import annotations

import pytest

from vault_agent.rules import dv2_rules
from vault_agent.rules.dv2_rules import (
    json_type_for_sql,
    null_safe_type,
    unread_payload,
    zero_key_incapable_type,
)
from vault_agent.rules.naming import NamingProfile
from vault_agent.state import DVModel, Hub, HubSource, SourceColumn, SourceTable, VaultAgentState

# What WP96 measured a PostgreSQL catalogue to spell (log 2026-10-30), plus the long forms a
# hand-written file may use.
PG_JSON = {
    "integer": "integer", "bigint": "integer", "smallint": "integer",
    "boolean": "boolean",
    "numeric(19, 4)": "number", "numeric": "number", "double precision": "number", "real": "number",
    "varchar(60)": "string", "character varying(60)": "string", "character(3)": "string",
    "char(3)": "string", "text": "string", "uuid": "string", "xml": "string", "bytea": "string",
    "date": "string", "timestamp without time zone": "string", "timestamp with time zone": "string",
    "time without time zone": "string", "timestamp": "string", "jsonb": "string", "json": "string",
}


# ── C47 stage 1: PostgreSQL spellings in the type rules ──────────────────────────────────
@pytest.mark.parametrize(("declared", "expected"), sorted(PG_JSON.items()))
def test_t1_postgres_spellings_have_their_json_type(declared: str, expected: str) -> None:
    assert json_type_for_sql(declared) == expected
    assert json_type_for_sql(declared.upper()) == expected


def test_t1_sql_server_spellings_are_unchanged() -> None:
    # every key the WP63 table held on 2026-11-07, with the answer it gave
    before = {
        **{t: "integer" for t in ("int", "bigint", "smallint", "tinyint")}, "bit": "boolean",
        **{t: "number" for t in ("decimal", "numeric", "money", "smallmoney", "float", "real")},
        **{t: "string" for t in (
            "char", "nchar", "varchar", "nvarchar", "text", "ntext", "uniqueidentifier", "xml",
            "date", "time", "datetime", "datetime2", "smalldatetime", "datetimeoffset", "binary",
            "varbinary", "image", "hierarchyid", "geography", "geometry",
        )},
    }
    assert {t: json_type_for_sql(t) for t in before} == before
    assert json_type_for_sql("nvarchar(50)") == "string" and json_type_for_sql("Name") is None
    assert json_type_for_sql("") is None


def test_t2_zero_key_sets_read_postgres_spellings() -> None:
    for declared in ("character varying(60)", "character(3)", "varchar(60)", "integer", "bigint"):
        assert null_safe_type(declared), declared
    for declared in ("timestamp without time zone", "uuid", "boolean", "numeric(19, 4)",
                     "double precision", "bytea", "date"):
        assert zero_key_incapable_type(declared), declared
        assert not null_safe_type(declared), declared
    assert not zero_key_incapable_type("geography") and not null_safe_type("geography")


# ── C48: the technical columns of a landing table ─────────────────────────────────────────
def _landing(*extra: str, key: str = "BusinessEntityID") -> SourceTable:
    return SourceTable(
        table="BusinessEntity", schema_name="Person",
        columns=[SourceColumn(name=key, type="integer"),
                 SourceColumn(name="ModifiedDate", type="timestamp without time zone"),
                 *(SourceColumn(name=c, type="text") for c in extra)],
        primary_key=[key],
    )


def _hub() -> Hub:
    return Hub(name="hub_business_entity", business_key="BusinessEntityID",
               source_entity="BusinessEntity", description="x",
               business_key_columns=["BusinessEntityID"],
               sources=[HubSource(source_table="BusinessEntity",
                                  business_key_column="BusinessEntityID")])


def test_t3_the_state_holds_no_technical_column_and_says_which_it_dropped() -> None:
    state = VaultAgentState(
        source_schemas=[_landing("load_datetime", "Record_Source", "APPLIED_DTS")],
        carried_schemas=[_landing("LOAD_DATETIME")],
    )
    assert state.source_schemas[0].column_names == ["BusinessEntityID", "ModifiedDate"]
    assert state.carried_schemas[0].column_names == ["BusinessEntityID", "ModifiedDate"]
    assert state.technical_source_columns == {
        "Person.BusinessEntity": ["load_datetime", "Record_Source", "APPLIED_DTS"],
    }
    again = VaultAgentState.model_validate(state.model_dump())
    assert again.source_schemas == state.source_schemas
    assert again.technical_source_columns == state.technical_source_columns


def test_t3_the_profile_decides_which_names_are_technical() -> None:
    naming = NamingProfile(load_datetime="LDTS", record_source="RSRC")
    state = VaultAgentState(source_schemas=[_landing("ldts", "rsrc", "load_datetime")],
                            naming=naming)
    assert state.source_schemas[0].column_names == [
        "BusinessEntityID", "ModifiedDate", "load_datetime",
    ]


def test_t3_a_technical_name_in_a_declared_key_is_kept() -> None:
    state = VaultAgentState(source_schemas=[_landing(key="RECORD_SOURCE")])
    assert state.source_schemas[0].column_names[0] == "RECORD_SOURCE"
    assert state.technical_source_columns == {}


def test_t4_the_payload_gate_no_longer_asks_for_load_columns() -> None:
    # the reproduction of 2026-11-07: without the drop, unread_payload answered
    # ['ModifiedDate', 'load_datetime', 'record_source'] and E_HUB_PAYLOAD_UNREAD fired on them
    raw = _landing("load_datetime", "record_source")
    model = DVModel(hubs=[_hub()], links=[], satellites=[])
    assert unread_payload(_hub(), raw, model, [raw]) == [
        "ModifiedDate", "load_datetime", "record_source",
    ]
    table = VaultAgentState(source_schemas=[raw]).source_schemas[0]
    assert unread_payload(_hub(), table, model, [table]) == ["ModifiedDate"]


def test_t5_a_schema_without_technical_columns_is_untouched() -> None:
    table = _landing()
    state = VaultAgentState(source_schemas=[table])
    assert state.source_schemas == [table] and state.technical_source_columns == {}
    assert dv2_rules is not None
