"""WP102 — a translation model's name stays within the platform's identifier limit (C36).
Committed before the change, failing. WP100's build of arm T's fifth project found two translation
views of 74 and 103 characters; PostgreSQL's identifiers end at 63 and dbt refused the relations."""
from __future__ import annotations

from vault_agent.agents.staging_generator import (
    StagingSpec,
    build_staging,
    translation_model_name,
)
from vault_agent.rules.platforms import platform_profile
from vault_agent.state import DVModel, FlagKind, KeyTranslation, SourceTable

THROUGHS = ["Customer", "CreditCard", "CurrencyRate", "ShipMethod", "SalesTerritory"]
FULL = ("stg_sales_order_customer_via_customer_and_creditcard_and_currencyrate_and_shipmethod"
        "_and_salesterritory")


def _spec(throughs: list[str] = THROUGHS) -> StagingSpec:
    spec = StagingSpec(name="stg_sales_order_customer", base="sales_order_customer")
    for table in throughs:
        spec.add_translation(
            KeyTranslation(referencing_column=f"{table}ID", through_table=table,
                           surrogate_column=f"{table}ID", natural_key_column="NAME"),
            f"NAME_VIA_{table.upper()}",
        )
    return spec


# ── §2 rule 1: the profile knows its limit ─────────────────────────────────────────────────
def test_the_profiles_carry_their_identifier_limits() -> None:
    assert platform_profile("postgres").max_identifier_length == 63
    assert platform_profile("databricks").max_identifier_length == 255


# ── §2 rule 2: shortened deterministically, only when it would not fit ─────────────────────
def test_a_name_that_fits_is_the_full_name() -> None:
    assert len(FULL) == 103
    assert translation_model_name(_spec()) == FULL
    assert translation_model_name(_spec(), 255) == FULL


def test_a_name_that_would_not_fit_is_shortened_and_deterministic() -> None:
    short = translation_model_name(_spec(), 63)
    assert short.startswith("stg_sales_order_customer_via_5_") and len(short) <= 63
    assert short == translation_model_name(_spec(), 63)
    other = translation_model_name(_spec(list(reversed(THROUGHS))), 63)
    assert other != short and other.startswith("stg_sales_order_customer_via_5_")


# ── the built project: view, stage and schema.yml agree on the short name ──────────────────
def _tables() -> list[SourceTable]:
    refs = [SourceTable(table=t, schema="Sales", columns=[f"{t}ID", "Name"]) for t in THROUGHS]
    header = SourceTable(
        table="SalesOrderHeader", schema="Sales",
        columns=["SalesOrderID", *[f"{t}ID" for t in THROUGHS], "TotalDue"],
        foreign_keys=[{"columns": [f"{t}ID"], "references_table": t,
                       "references_columns": [f"{t}ID"], "references_schema": "Sales"}
                      for t in THROUGHS],
    )
    return [*refs, header]


def _model() -> DVModel:
    def translation(table: str) -> dict[str, str]:
        return {"referencing_column": f"{table}ID", "through_table": table,
                "through_schema": "Sales", "surrogate_column": f"{table}ID",
                "natural_key_column": "NAME"}
    hubs = [{"name": "hub_sales_order", "business_key": "SalesOrderID",
             "source_entity": "SalesOrderHeader", "description": "o"}]
    refs: list[dict[str, object]] = [{"hub": "hub_sales_order"}]
    for t in THROUGHS:
        name = "hub_" + "".join("_" + c.lower() if c.isupper() else c for c in t).lstrip("_")
        hubs.append({"name": name, "business_key": "Name", "source_entity": t, "description": t})
        refs.append({"hub": name, "key_translation": translation(t)})
    return DVModel.model_validate({
        "hubs": hubs,
        "links": [{"name": "link_sales_order_customer", "description": "l",
                   "connected_hubs": refs}],
        "satellites": [],
    })


def _build(platform: str) -> object:
    return build_staging(_model(), _tables(),
                         source_overrides={"SALES_ORDER_CUSTOMER": "SalesOrderHeader"},
                         target_platform=platform)  # type: ignore[arg-type]


def test_on_postgres_the_view_the_stage_and_the_yml_carry_the_short_name() -> None:
    result = _build("postgres")
    [short] = [n for n in result.models if "_via_" in n]  # type: ignore[attr-defined]
    assert len(short) <= 63 and short != FULL
    view = result.models[short]  # type: ignore[attr-defined]
    assert all(t in view for t in THROUGHS)  # the joined relations stay readable in the header
    assert f"source_model: '{short}'" in result.models["stg_sales_order_customer"]  # type: ignore[attr-defined]
    assert f"models/staging/{short}.yml" in result.scaffolding  # type: ignore[attr-defined]
    assert f"models/staging/{FULL}.yml" not in result.scaffolding  # type: ignore[attr-defined]
    assert not [f for f in result.flags if f.kind == FlagKind.GENERATION_GAP]  # type: ignore[attr-defined]


def test_on_databricks_the_full_name_fits_and_is_kept() -> None:
    result = _build("databricks")
    assert FULL in result.models  # type: ignore[attr-defined]


# ── §2 rule 3: a name over the limit after shortening is flagged, not truncated ────────────
def test_a_staging_name_over_the_limit_is_flagged_on_postgres_only() -> None:
    long_hub = "hub_" + "_".join(["measure"] * 9)  # stg_ + 71 characters
    model = DVModel.model_validate({
        "hubs": [{"name": long_hub, "business_key": "Code", "source_entity": "Measure",
                  "description": "m"}], "links": [], "satellites": [],
    })
    stage = "stg_" + long_hub[len("hub_"):]
    flagged = build_staging(model, [], target_platform="postgres").flags
    assert [f.asset for f in flagged if f.kind == FlagKind.GENERATION_GAP] == [stage]
    assert "63" in next(
        f.message for f in flagged if f.asset == stage and f.kind == FlagKind.GENERATION_GAP
    )
    assert not [f for f in build_staging(model, [], target_platform="databricks").flags
                if f.kind == FlagKind.GENERATION_GAP]
