"""Unit tests for source-schema grounding helpers (ADR-0004)."""
from vault_agent.grounding import (
    is_grounded,
    known_columns,
    render_schema_prompt_section,
)
from vault_agent.state import SourceTable


def test_known_columns_normalises_across_tables() -> None:
    schemas = [
        SourceTable(table="customer", columns=["national_customer_id", "Customer Name"]),
        SourceTable(table="account", columns=["account-number"]),
    ]
    assert known_columns(schemas) == {
        "NATIONAL_CUSTOMER_ID", "CUSTOMER_NAME", "ACCOUNT_NUMBER",
    }


def test_is_grounded_matches_business_label_to_physical_column() -> None:
    columns = known_columns([SourceTable(table="customer", columns=["national_customer_id"])])
    # The business label and the physical column normalise to the same identifier.
    assert is_grounded("national customer ID", columns)
    assert not is_grounded("passport number", columns)


def test_render_schema_section_is_empty_when_no_schema() -> None:
    # Empty -> "" keeps the system prompt byte-identical to the no-grounding case.
    assert render_schema_prompt_section([]) == ""


def test_render_schema_section_lists_tables_and_columns() -> None:
    section = render_schema_prompt_section(
        [SourceTable(table="customer", columns=["national_customer_id", "customer_name"])]
    )
    assert "Known source columns" in section
    assert "**customer**: national_customer_id, customer_name" in section
