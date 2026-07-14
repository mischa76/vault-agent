"""Keyless tests for the opacity-masking transform (WP9 §10.7)."""
from eval.mapping import (
    AmbiguousEntry,
    GapEntry,
    GoldenCandidate,
    GoldenMapping,
    GoldenMappingEntry,
)
from eval.opacity_probe import mask_case
from vault_agent.state import ColumnProfile, SourceColumn, SourceTable


def _inputs():
    schema = [
        SourceTable(table="VICTOR_PARTNER", columns=[
            SourceColumn(name="PARTN_NR", type="varchar(10)", comment="the partner id"),
            SourceColumn(name="KD_NR", type="varchar(6)", comment="branch code"),
        ]),
        SourceTable(table="CRM_ACCOUNT", columns=[
            SourceColumn(name="ExternalCustomerNo", type="varchar(10)", comment="external no"),
        ]),
    ]
    golden = GoldenMapping(
        mappings=[GoldenMappingEntry(concept="partner number", source_table="VICTOR_PARTNER",
                                     source_column="PARTN_NR", kind="business_key")],
        ambiguous=[AmbiguousEntry(concept="customer reference", candidates=[
            GoldenCandidate(table="VICTOR_PARTNER", column="PARTN_NR"),
            GoldenCandidate(table="CRM_ACCOUNT", column="ExternalCustomerNo"),
        ])],
        gaps=[GapEntry(concept="claims ratio", reason="derived")],
    )
    profiling = {"VICTOR_PARTNER": {
        "PARTN_NR": ColumnProfile(name="PARTN_NR", uniqueness_ratio=0.99, null_ratio=0.01,
                                  distinct_count=100, example_values=["P0001"]),
    }}
    return schema, golden, profiling


def test_columns_masked_comments_stripped_types_kept() -> None:
    schema, golden, profiling = _inputs()
    masked_schema, _, _ = mask_case(schema, golden, profiling)
    names = [c.name for t in masked_schema for c in t.column_refs]
    assert names == ["COL_0001", "COL_0002", "COL_0003"]  # deterministic, schema order
    for t in masked_schema:
        for c in t.column_refs:
            assert c.comment is None  # comments dropped
    # Types are retained (a real precondition-(c) failure keeps structure, loses meaning).
    assert masked_schema[0].column_refs[0].type == "varchar(10)"
    # Table names are kept (only column names are opaque).
    assert masked_schema[0].table == "VICTOR_PARTNER"


def test_golden_rekeyed_consistently_with_schema() -> None:
    schema, golden, profiling = _inputs()
    _, masked_golden, _ = mask_case(schema, golden, profiling)
    # partner number -> PARTN_NR was masked to COL_0001 in the schema; golden agrees.
    assert masked_golden.mappings[0].source_column == "COL_0001"
    # ambiguous candidates masked to the same names as the schema.
    cand_cols = {c.column for c in masked_golden.ambiguous[0].candidates}
    assert cand_cols == {"COL_0001", "COL_0003"}
    # gaps have no source column — unchanged.
    assert masked_golden.gaps[0].concept == "claims ratio"


def test_profiling_rekeyed_examples_stripped() -> None:
    schema, golden, profiling = _inputs()
    _, _, masked_profiling = mask_case(schema, golden, profiling)
    col = masked_profiling["VICTOR_PARTNER"]["COL_0001"]
    assert col.uniqueness_ratio == 0.99  # distributions kept
    assert col.example_values == []  # example values leak semantics -> stripped
