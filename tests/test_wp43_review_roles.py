"""WP43 — decisions and disclosures in the review queue (spec §3, guards 1–3, 5–7).

Committed before the change, failing. Every assertion branches on typed fields: ``role``,
``kind``, ``severity``, ``FlagKind``, ``code`` — never on message text.
"""
from __future__ import annotations

import html
import re
import typing

from rich.console import Console

from eval.run import UsageTotals, run_metrics
from vault_agent.agents.orchestrator import (
    AGGREGATE_THRESHOLD,
    REVIEW_FLAG_ROLES,
    HumanReviewQueue,
    ReviewItem,
    ReviewRole,
    assemble_review_queue,
    render_review_queue_md,
)
from vault_agent.cli import _print_checkpoint
from vault_agent.report import _review_section
from vault_agent.state import (
    Artifacts,
    FlagKind,
    PipelineFlag,
    ValidationIssue,
    ValidationReport,
    VaultAgentState,
)


def _flag_kinds() -> set[str]:
    """Every FlagKind value the code declares (the code owns the list, CLAUDE.md)."""
    return {
        value
        for name, value in vars(FlagKind).items()
        if name.isupper() and isinstance(value, str)
    }


def _issue(severity: str, code: str, construct: str = "x") -> ValidationIssue:
    return ValidationIssue(
        severity=severity,  # type: ignore[arg-type]
        code=code,
        construct=construct,
        message=f"{code} on {construct}",
    )


def _mixed_state() -> VaultAgentState:
    """One of everything the role table distinguishes."""
    state = VaultAgentState(
        validation_report=ValidationReport(
            passed=False,
            issues=[
                _issue("error", "E_NO_HUBS", "dv_model"),
                _issue("warning", "W_HUB_NO_SAT", "hub_a"),
                _issue("info", "I_EXISTING_EXTENDED", "hub_b"),
            ],
        ),
        artifacts=Artifacts(
            contracts=[
                {"name": "customer", "owner": {"name": "TODO: assign", "email": None}},
            ],
        ),
    )
    state.flag("data_contract", "type undetermined", kind=FlagKind.UNDETERMINED_TYPE,
               asset="customer.status")
    state.flag("code_generator", "binding inferred", kind=FlagKind.SOURCE_BINDING,
               asset="stg_customer")
    state.flag("link_proposer", "translation", kind=FlagKind.LINK_TRANSLATION,
               asset="link_a_b")
    # Typed severity wins over kind: an error-severity flag of a disclosure kind is a decision.
    state.flag("source_mapper", "severe", severity="error", kind=FlagKind.MAPPING_GAP,
               asset="concept_z")
    # A kind the table has never heard of must not be hidden behind the fold.
    state.flag("future_agent", "unclassified", kind="made_up_kind", asset="thing")
    return state


# --- Guard 1: the role table and its derivation ------------------------------------------


def test_role_table_classifies_every_declared_flag_kind() -> None:
    """A new FlagKind must be classified explicitly; the owner placeholder never becomes a
    flag item (it is the structural contract_owner item), so it is the one exemption."""
    expected = _flag_kinds() - {FlagKind.OWNER_PLACEHOLDER}
    assert set(REVIEW_FLAG_ROLES) == expected
    assert set(REVIEW_FLAG_ROLES.values()) <= set(typing.get_args(ReviewRole))


def test_assemble_assigns_roles_from_typed_fields() -> None:
    queue = assemble_review_queue(_mixed_state())
    by_asset = {item.asset or item.summary: item for item in queue.items}

    assert by_asset["E_NO_HUBS on dv_model"].role == "decision"
    assert by_asset["W_HUB_NO_SAT on hub_a"].role == "disclosure"
    assert next(i for i in queue.items if i.kind == "contract_owner").role == "decision"
    assert by_asset["customer.status"].role == "decision"  # undetermined_type
    assert by_asset["stg_customer"].role == "disclosure"  # source_binding
    assert by_asset["link_a_b"].role == "decision"  # link_translation (ADR-0013 §3)
    assert by_asset["concept_z"].role == "decision"  # severity error wins over mapping_gap
    assert by_asset["thing"].role == "decision"  # unknown kind: conservative default


def test_role_default_on_a_bare_item_is_decision() -> None:
    """An item built without a role (the renderer parity tests do this) is never hidden."""
    assert ReviewItem(kind="review_flag", summary="x").role == "decision"


# --- Guard 2: the partition --------------------------------------------------------------


def test_queue_partitions_into_decisions_and_disclosures() -> None:
    queue = assemble_review_queue(_mixed_state())
    assert len(queue.decisions) + len(queue.disclosures) == len(queue.items)
    assert all(i.role == "decision" for i in queue.decisions)
    assert all(i.role == "disclosure" for i in queue.disclosures)
    assert queue.requires_signoff is True  # unchanged: an error and an owner block

    advisory_only = HumanReviewQueue(
        items=[ReviewItem(kind="validation_warning", summary="w", role="disclosure")]
    )
    assert advisory_only.requires_signoff is False


# --- Guard 3: info is information, not an item ------------------------------------------


def test_info_issue_yields_no_review_item_but_stays_in_the_report() -> None:
    state = _mixed_state()
    assert any(i.severity == "info" for i in state.validation_report.issues)
    queue = assemble_review_queue(state)
    assert all("I_EXISTING_EXTENDED" not in item.summary for item in queue.items)
    assert len([i for i in queue.items if i.kind == "validation_warning"]) == 1


# --- Guard 5: rendering order and aggregation -------------------------------------------


def _summaries(text: str, pattern: str) -> list[str]:
    return re.findall(pattern, text)


def _noisy_state() -> VaultAgentState:
    state = VaultAgentState(
        validation_report=ValidationReport(
            passed=True,
            issues=[
                _issue("warning", "W_SAT_ATTR_OVERLAP_CROSS_SOURCE", f"sat_{n}")
                for n in range(AGGREGATE_THRESHOLD + 1)
            ]
            + [_issue("warning", "W_BK_COLLISION_RISK", "hub_q")],
        ),
    )
    for n in range(AGGREGATE_THRESHOLD + 1):
        state.flag("code_generator", "inferred", kind=FlagKind.SOURCE_BINDING,
                   asset=f"stg_{n}")
    for n in range(AGGREGATE_THRESHOLD + 1):
        state.flag("data_contract", "undetermined", kind=FlagKind.UNDETERMINED_TYPE,
                   asset=f"c.f{n}")
    state.flag("link_proposer", "join through person", kind=FlagKind.LINK_TRANSLATION,
               asset="link_t1")
    state.flag("link_proposer", "join through address", kind=FlagKind.LINK_TRANSLATION,
               asset="link_t2")
    return state


def test_markdown_puts_every_decision_before_every_disclosure() -> None:
    queue = assemble_review_queue(_noisy_state())
    md = render_review_queue_md(queue)

    assert "Disclosures" in md
    decision_positions = [md.index(s) for s in ("link_t1", "link_t2")]
    disclosure_positions = [md.index(s) for s in ("W_BK_COLLISION_RISK", "W_SAT_ATTR_OVERLAP")]
    assert max(decision_positions) < md.index("Disclosures") < min(disclosure_positions)
    # Status line counts both roles.
    assert f"{len(queue.decisions)} decision(s)" in md
    assert f"{len(queue.disclosures)} disclosure(s)" in md


def test_markdown_aggregates_disclosed_warnings_by_code_and_keeps_wp5_groups() -> None:
    md = render_review_queue_md(assemble_review_queue(_noisy_state()))
    n = AGGREGATE_THRESHOLD + 1

    assert f"{n}× W_SAT_ATTR_OVERLAP_CROSS_SOURCE" in md  # warnings collapse by code
    assert md.count("W_BK_COLLISION_RISK") == 1  # a single warning stays individual
    assert f"{n}× inferred staging source binding(s)" in md  # WP5 group, unchanged
    assert f"{n}× undetermined field type" in md  # a grouped decision still collapses (WP5 #3)
    assert md.count("join through") == 2  # translations are never aggregated (ADR-0013 §3)


# --- Guard 6: three renderers, one order ------------------------------------------------


def test_console_and_html_follow_the_markdown_order() -> None:
    state = _noisy_state()
    queue = assemble_review_queue(state)
    md = render_review_queue_md(queue)
    console = Console(record=True, width=250)
    _print_checkpoint(console, queue)
    cli_text = console.export_text()
    html_section = _review_section(state)

    md_items = _summaries(md, r"- \*\*(.+?)\*\*")
    cli_items = [line.strip()[2:].split(" — ")[0] for line in cli_text.splitlines()
                 if line.strip().startswith("- ")]
    html_items = [html.unescape(s)
                  for s in _summaries(html_section, r"<li><strong>(.+?)</strong>")]
    assert md_items == html_items == cli_items
    for text in (md, cli_text, html_section):
        assert text.index("link_t1") < text.index("Disclosures") < text.index("W_BK_COLLISION")


# --- Guard 7: the eval carries both numbers ---------------------------------------------


def test_run_metrics_report_decisions_and_disclosures() -> None:
    state = _mixed_state()
    metrics = run_metrics(state, 1.0, UsageTotals())
    queue = assemble_review_queue(state)
    assert metrics["review_decisions"] == len(queue.decisions)
    assert metrics["review_disclosures"] == len(queue.disclosures)
    assert metrics["review_items_total"] == len(queue.items)
    assert metrics["review_decisions"] + metrics["review_disclosures"] == len(queue.items)


def test_role_literal_has_exactly_two_values() -> None:
    assert set(typing.get_args(ReviewRole)) == {"decision", "disclosure"}


def test_legacy_flag_without_kind_is_a_decision() -> None:
    """A bare PipelineFlag (kind GENERIC) is unclassified work, not provenance."""
    queue = assemble_review_queue(
        VaultAgentState(flags=[PipelineFlag(agent="pipeline", message="some flag")])
    )
    assert [i.role for i in queue.items] == ["decision"]
