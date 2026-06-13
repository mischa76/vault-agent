"""Source-schema grounding (ADR-0004).

Cross-checks proposed business keys and satellite attributes against the columns that
actually exist in the declared source tables (``state.source_schemas``), and renders the
declared schema into the LLM prompts so candidates are drawn from real columns.

Optional by construction: every helper here no-ops on an empty schema list, so a pipeline
run with no declared schema behaves exactly as before. Matching reuses
``normalize_identifier`` so a business label (``"national customer ID"``) grounds against a
physical column (``NATIONAL_CUSTOMER_ID``)."""
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import SourceTable


def known_columns(source_schemas: list[SourceTable]) -> set[str]:
    """Normalised set of every column across the declared source tables."""
    return {
        normalize_identifier(col)
        for table in source_schemas
        for col in table.columns
    }


def is_grounded(label: str, columns: set[str]) -> bool:
    """True if a proposed label matches a known source column (normalised)."""
    return normalize_identifier(label) in columns


def render_schema_prompt_section(source_schemas: list[SourceTable]) -> str:
    """Render the declared schema as a prompt section; '' when nothing is declared.

    Returning '' on an empty schema keeps the system prompt byte-identical to the
    no-grounding case, preserving the no-regression guarantee."""
    if not source_schemas:
        return ""
    lines = [
        "## Known source columns",
        "",
        "Draw business keys and attributes from these real source columns where possible; "
        "do not invent columns that are not listed below:",
        "",
    ]
    for table in source_schemas:
        cols = ", ".join(table.columns) if table.columns else "(no columns listed)"
        lines.append(f"- **{table.table}**: {cols}")
    return "\n" + "\n".join(lines) + "\n"
