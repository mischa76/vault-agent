"""WP11 — static HTML run report (keyless, deterministic).

Covers the spec §6 test matrix: idempotency/fixture pin, hostile-name escaping, Mermaid
graph structure (roles, driving keys, multi-source cylinders, sat classes, order), review-
queue parity with the WP5 §5.1 renderer, and the empty-state path.
"""
import html
import re
from pathlib import Path

from vault_agent.agents.orchestrator import (
    assemble_review_queue,
    render_review_queue_md,
)
from vault_agent.report import (
    _MERMAID_CDN,
    _review_section,
    build_model_mermaid,
    build_report,
)
from vault_agent.state import (
    DVModel,
    Hub,
    HubSource,
    Link,
    LinkHubRef,
    Satellite,
    ValidationIssue,
    ValidationReport,
    VaultAgentState,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "report" / "report_fixture.html"


def _graph_model() -> DVModel:
    """A model exercising every graph feature: multi-source hub, self-referencing link with a
    driving key, and one satellite of each type (one carrying its own source_table)."""
    return DVModel(
        hubs=[
            Hub(name="hub_account", business_key="account_number", source_entity="account",
                description="A bank account."),
            Hub(
                name="hub_customer", business_key="customer_id", source_entity="customer",
                description="A customer.",
                sources=[
                    HubSource(source_table="crm_customer", business_key_column="cust_id"),
                    HubSource(source_table="victor_partner", business_key_column="partn_id"),
                ],
            ),
        ],
        links=[
            Link(
                name="link_transfer",
                connected_hubs=["hub_account", LinkHubRef(hub="hub_account", role="counterparty")],
                description="A money transfer.",
                link_type="transactional",
                driving_key=["hub_account"],
                payload=["amount", "currency"],
            ),
        ],
        satellites=[
            Satellite(name="sat_account_details", parent="hub_account",
                      attributes=["status"], description="Account details."),
            Satellite(name="sat_customer_addresses", parent="hub_customer", sat_type="multi_active",
                      child_dependent_key=["address_type"], attributes=["street"],
                      description="Addresses.", source_table="raw_customer_address"),
            Satellite(name="sat_transfer_eff", parent="link_transfer", sat_type="effectivity",
                      attributes=["effective_from", "effective_to"], description="Effectivity."),
        ],
    )


def _rich_state() -> VaultAgentState:
    """A fully populated fixed state for the idempotency/fixture pin (deterministic)."""
    state = VaultAgentState(input_documents=["req.md"])
    state.dv_model = _graph_model()
    state.validation_report = ValidationReport(
        passed=True,
        issues=[
            ValidationIssue(severity="warning", code="W_SAT_WIDE", construct="sat_account_details",
                            message="Satellite is getting wide."),
        ],
    )
    state.artifacts.dbt_models = {"hub_account": "-- sql", "link_transfer": "-- sql"}
    state.artifacts.staging_models = {"stg_account": "-- sql"}
    state.artifacts.scaffolding = {"dbt_project.yml": "name: p\n"}
    state.artifacts.contracts = [
        {"name": "account", "owner": {"name": "TODO: assign", "email": None},
         "schema": [{"name": "account_number"}, {"name": "status"}]},
    ]
    state.flag("data_contract", "field 'x' type undetermined", kind="undetermined_type",
               asset="account.x")
    return state


# --- Idempotency + fixture pin -----------------------------------------------------------


def test_report_is_pure() -> None:
    state = _rich_state()
    assert build_report(state) == build_report(_rich_state())


def test_report_matches_pinned_fixture() -> None:
    assert build_report(_rich_state()) == _FIXTURE.read_text(encoding="utf-8")


# --- Escaping (treat every state string as hostile) --------------------------------------


def test_hostile_strings_are_escaped_everywhere() -> None:
    model = DVModel(hubs=[
        Hub(name="<script>alert(1)</script>", business_key="id", source_entity="e",
            description='he said "hi"'),
    ])
    state = VaultAgentState()
    state.dv_model = model
    out = build_report(state)

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out  # escaped in the HTML body
    assert "<script>alert(1)" not in out                   # never raw
    assert "&quot;hi&quot;" in out                          # the quote in the description
    # Exactly one raw opening <script tag — the pinned Mermaid include, nothing injected.
    assert out.count("<script") == 1
    assert _MERMAID_CDN in out
    # The Mermaid source alone also carries the name escaped, not raw.
    mer = build_model_mermaid(model)
    assert "&lt;script&gt;" in mer and "<script>alert" not in mer


# --- Mermaid graph structure -------------------------------------------------------------


def test_mermaid_graph_structure() -> None:
    mer = build_model_mermaid(_graph_model())

    # Self-referencing link: two edges from the link to the same hub node, exactly one of them
    # role-labelled; the unqualified participation is the driving key, so it is a thick edge.
    account_edges = re.findall(r"^\s*LINK_TRANSFER .*HUB_ACCOUNT$", mer, flags=re.MULTILINE)
    assert len(account_edges) == 2
    assert "  LINK_TRANSFER ==> HUB_ACCOUNT" in mer                       # driving → thick
    assert '  LINK_TRANSFER -->|"counterparty"| HUB_ACCOUNT' in mer        # role label

    # Transactional hexagon label.
    assert '  LINK_TRANSFER{{"link_transfer<br/>(transactional)"}}' in mer

    # Multi-source hub: one cylinder per feed, each edged into the hub.
    assert '  HUB_CUSTOMER__SRC0[("crm_customer.cust_id")]' in mer
    assert '  HUB_CUSTOMER__SRC1[("victor_partner.partn_id")]' in mer
    assert "  HUB_CUSTOMER__SRC0 --> HUB_CUSTOMER" in mer

    # One class per sat_type; a satellite with its own source_table notes it.
    assert "  class SAT_ACCOUNT_DETAILS sat_standard;" in mer
    assert "  class SAT_CUSTOMER_ADDRESSES sat_multi_active;" in mer
    assert "  class SAT_TRANSFER_EFF sat_effectivity;" in mer
    assert "<br/>src: raw_customer_address" in mer

    # Deterministic emission order: hubs before links before satellites.
    assert mer.index("HUB_ACCOUNT[") < mer.index("LINK_TRANSFER{{")
    assert mer.index("LINK_TRANSFER{{") < mer.index("SAT_ACCOUNT_DETAILS(")


# --- Review-queue parity with the WP5 §5.1 renderer --------------------------------------


def _summaries(text: str, pattern: str) -> list[str]:
    return re.findall(pattern, text)


def test_review_section_parity_with_markdown_renderer() -> None:
    """The report is the third review renderer: same items, same blocking-first order, same
    aggregation as render_review_queue_md (spec §6 parity, extends the WP5 pattern)."""
    state = VaultAgentState()
    # Four aggregatable advisory flags (> AGGREGATE_THRESHOLD) collapse to one line; a blocking
    # validation error and a contract owner stay individual and sort first.
    state.validation_report = ValidationReport(
        passed=False,
        issues=[ValidationIssue(severity="error", code="E_NO_HUBS", construct="model",
                                message="No hubs.")],
    )
    state.artifacts.contracts = [
        {"name": "account", "owner": {"name": "TODO: assign", "email": None}, "schema": []},
    ]
    for i in range(4):
        state.flag("data_contract", f"field {i} type undetermined", kind="undetermined_type",
                   asset=f"account.f{i}")

    md = render_review_queue_md(assemble_review_queue(state))
    html_section = _review_section(state)

    md_items = _summaries(md, r"- \*\*(.+?)\*\*")
    # The report escapes item text for HTML (e.g. ' → &#x27;); unescape before comparing, since
    # parity is about item identity and order, not the presentation-layer escaping.
    html_items = [html.unescape(s) for s in _summaries(html_section, r"<li><strong>(.+?)</strong>")]
    assert md_items == html_items          # identical text, identical order
    assert any("undetermined field type" in s for s in html_items)  # aggregated line present


# --- Empty / minimal state ---------------------------------------------------------------


def test_empty_state_renders_without_graph() -> None:
    out = build_report(VaultAgentState())
    assert out.startswith("<!doctype html>")
    assert 'class="mermaid"' not in out            # no graph section for an empty model
    assert "No model constructs" in out
    assert out.count("<script") == 1               # the include is still present
