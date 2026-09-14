#!/usr/bin/env python
"""Generate the FK-derived-links demo's dbt project from the *real* proposer, applier and
generator — the keyless capture of WP36 (surrogate→natural-key translation, ADR-0013) and
WP37 (relationship-table links).

Both WPs were built and tested keyless on 2026-09-12, and both records say the same thing:
no ``dbt build`` had ever compiled a translation model or a relationship link's staging. This
demo closes that gap the way demo/bank_postgres and demo/mapping_postgres do — a fixed,
hand-checked input, the pipeline's own code, a running Data Vault on local PostgreSQL, no
API key.

What is fixed here is the modeler's *output*, not the model: the previous vault
(``hub_product`` keyed on ``ProductNumber``, ``hub_unit_measure``) and the delta the modeler
would emit for the Purchasing/Sales increment (``hub_vendor`` keyed on ``AccountNumber``,
``hub_shopping_cart_item``). Everything else — the proposals from the declared foreign keys,
their ratification, the pending participation resolved against the merged model, the link
names, the translation views and their tests, the staging binding — is computed by the same
functions the pipeline runs, in the pipeline's order:

  link_proposer → checkpoint (``--accept``) → modeler delta → apply_ratified_link_proposals
  → merge_models → CodeGeneratorAgent → ValidatorAgent → rebind_staging

The miniature is the AdventureWorks shape the two WPs were measured on:

  * ``ShoppingCartItem.ProductID → Product.ProductID`` — a surrogate reference to a hub keyed
    on the natural key ``ProductNumber``: WP36's translated link, staged through a
    ``stg_..._via_product`` view (LEFT JOIN, ``not_null`` + ``relationships`` tests).
  * ``ProductVendor`` — a hub-less table with three foreign keys (Product, UnitMeasure,
    Vendor): WP37's relationship link, three-way, two of its participations translated;
    the Vendor participation is PENDING at proposal time (Vendor is this increment's table)
    and resolves only after the modeler has built ``hub_vendor``.

Run: ``uv run python demo/fk_links_postgres/build_vault_models.py`` (or from this directory).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.model_merger import merge_models
from vault_agent.agents.orchestrator import apply_link_decision
from vault_agent.agents.source_mapper import rebind_staging
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.link_proposal import apply_ratified_link_proposals, collect_link_proposals
from vault_agent.state import (
    RESOLUTION_SAME_AS,
    DVModel,
    EntityResolution,
    Hub,
    Proposal,
    ProposedMapping,
    ResolutionProposal,
    Satellite,
    SourceTable,
    VaultAgentState,
    concept_key,
)
from vault_agent.subtype_feed import apply_subtype_feeds

HERE = Path(__file__).parent


def existing_vault() -> DVModel:
    """The prior vault (the Production increment): two hubs, keyed on NATURAL keys.

    ``hub_product`` on ``ProductNumber`` — not on the surrogate ``ProductID`` the foreign
    keys reference — is the whole reason WP36 exists (ADR-0013)."""
    return DVModel(hubs=[
        Hub(name="hub_product", business_key="ProductNumber", source_entity="Product",
            description="A product, anchored on its product number."),
        Hub(name="hub_unit_measure", business_key="UnitMeasureCode",
            source_entity="UnitMeasure", description="A unit of measure."),
        # WP38: the supertype, keyed on its natural key — the table's own key is a surrogate.
        Hub(name="hub_employee", business_key="NationalIDNumber", source_entity="Employee",
            description="An employee, anchored on the national ID number."),
    ])


def declared_source_schema() -> list[SourceTable]:
    """The Purchasing/Sales increment's declared tables (ADR-0004), with the foreign keys
    the source catalogue states (WP34 §3.1). Bare relation names — no ``schema`` — so
    staging binds by name to the seeds, the pattern verified since demo/bank_postgres.
    ``Product`` and ``UnitMeasure`` are re-declared because the translation joins through
    them and the seeds must exist; a declared referenced table must carry both the surrogate
    and the natural key (WP36 §2) or the proposal is a typed skip."""
    return [
        SourceTable(table="Product",
                    columns=["ProductID", "Name", "ProductNumber", "Color"]),
        SourceTable(table="UnitMeasure", columns=["UnitMeasureCode", "Name"]),
        SourceTable(table="Employee",
                    columns=["BusinessEntityID", "NationalIDNumber", "JobTitle"]),
        # WP38: a subtype keyed on the supertype's surrogate — no NationalIDNumber here.
        SourceTable(
            table="SalesPerson",
            columns=["BusinessEntityID", "SalesQuota", "Bonus"],
            foreign_keys=[
                {"columns": ["BusinessEntityID"], "references_table": "Employee",
                 "references_columns": ["BusinessEntityID"]},
            ],
        ),
        # WP39: keyed on the subtype's key — two hops from Employee.
        SourceTable(
            table="SalesPersonQuotaHistory",
            columns=["BusinessEntityID", "QuotaDate", "SalesQuota"],
            foreign_keys=[
                {"columns": ["BusinessEntityID"], "references_table": "SalesPerson",
                 "references_columns": ["BusinessEntityID"]},
            ],
        ),
        # WP39: a header that references the subtype — its link reaches hub_employee two hops on.
        SourceTable(
            table="SalesOrderHeader",
            columns=["SalesOrderID", "SalesOrderNumber", "SalesPersonID"],
            foreign_keys=[
                {"columns": ["SalesPersonID"], "references_table": "SalesPerson",
                 "references_columns": ["BusinessEntityID"]},
            ],
        ),
        SourceTable(table="Vendor",
                    columns=["BusinessEntityID", "AccountNumber", "Name", "CreditRating"]),
        SourceTable(
            table="ProductVendor",
            columns=["ProductID", "BusinessEntityID", "UnitMeasureCode", "StandardPrice"],
            foreign_keys=[
                {"columns": ["ProductID"], "references_table": "Product",
                 "references_columns": ["ProductID"]},
                {"columns": ["UnitMeasureCode"], "references_table": "UnitMeasure",
                 "references_columns": ["UnitMeasureCode"]},
                {"columns": ["BusinessEntityID"], "references_table": "Vendor",
                 "references_columns": ["BusinessEntityID"]},
            ],
        ),
        SourceTable(
            table="ShoppingCartItem",
            columns=["ShoppingCartItemID", "ShoppingCartID", "Quantity", "ProductID"],
            foreign_keys=[
                {"columns": ["ProductID"], "references_table": "Product",
                 "references_columns": ["ProductID"]},
            ],
        ),
    ]


def modeler_delta() -> DVModel:
    """What the modeler emits for the increment — fixed here, so the demo is keyless.

    ``hub_vendor`` is keyed on the natural key ``AccountNumber`` (as the paid run of
    2026-09-12 keyed it), so ``ProductVendor.BusinessEntityID`` needs a translation through
    ``Vendor``; ``hub_shopping_cart_item`` is keyed on its own surrogate. No link: the modeler
    is not asked to relate the increment to the prior vault — that is the proposer's job."""
    return DVModel(
        hubs=[
            Hub(name="hub_vendor", business_key="AccountNumber", source_entity="Vendor",
                description="A vendor, anchored on its account number."),
            Hub(name="hub_shopping_cart_item", business_key="ShoppingCartItemID",
                source_entity="ShoppingCartItem",
                description="A line in a shopping cart, anchored on its item id."),
            # WP39: the near side of the two-hop link.
            Hub(name="hub_sales_order", business_key="SalesOrderNumber",
                source_entity="SalesOrderHeader", description="A sales order."),
        ],
        satellites=[
            Satellite(name="sat_vendor_details", parent="hub_vendor",
                      attributes=["Name", "CreditRating"],
                      description="Descriptive vendor attributes.", sat_type="standard"),
            # WP38: the sales-representative role, on the supertype hub, read from the subtype.
            Satellite(name="sat_sales_person_details", parent="hub_employee",
                      attributes=["SalesQuota", "Bonus"], source_table="SalesPerson",
                      description="The sales-representative role of an employee."),
            # WP39: the role's quota history — a table keyed on the subtype's key, two hops on.
            Satellite(name="sat_sales_person_quota_history", parent="hub_employee",
                      attributes=["SalesQuota"], source_table="SalesPersonQuotaHistory",
                      sat_type="multi_active", child_dependent_key=["QuotaDate"],
                      description="Quota history of the sales-representative role."),
        ],
    )


async def build_state() -> VaultAgentState:
    """The pipeline's order, with the modeler replaced by ``modeler_delta``."""
    existing = existing_vault()
    state = VaultAgentState(
        existing_model=existing,
        source_schemas=declared_source_schema(),
        # WP38: the resolver's same-as, ratified at the resolution checkpoint as `--accept` does.
        resolutions=EntityResolution(proposals=[ResolutionProposal(
            concept=concept_key("BusinessEntityID", "sales representative"),
            resolution=RESOLUTION_SAME_AS, same_as="hub_employee",
            ratification_status="accepted",
        )]),
    )
    collect_link_proposals(state)          # the link_proposer node
    apply_link_decision(state, {"accept": True})  # the checkpoint, as `run --accept` answers it
    delta = apply_ratified_link_proposals(modeler_delta(), existing, state)  # dv2_modeler
    delta = apply_subtype_feeds(delta, existing, state)                        # dv2_modeler, WP38
    state.dv_model = merge_models(existing, delta, state)
    state = await CodeGeneratorAgent().run(state)
    state = await ValidatorAgent().run(state)
    # The source mapper's ratified answer for the one hub whose name does not match its table
    # (hub_sales_order ← SalesOrderHeader): the pipeline's mapper proposes it and `--accept`
    # ratifies it; the demo fixes it, as it fixes the modeler's delta.
    state.mappings = ProposedMapping(proposals=[Proposal(
        concept="SalesOrderNumber", entity="SalesOrderHeader", table="SalesOrderHeader",
        column="SalesOrderNumber", confidence=0.99, category="exact_name",
        ratification_status="accepted",
        evidence=["SalesOrderHeader is the anchor table of the sales order."],
    )])
    rebind_staging(state)                  # the source_mapper's re-bind (link overrides, WP34 §3.5)
    return state


def write_project(state: VaultAgentState, out_dir: Path = HERE) -> list[Path]:
    """Write the generated models and scaffolding into a runnable dbt project. README.md,
    profiles.yml and the seeds are hand-authored and NOT overwritten."""
    written: list[Path] = []
    raw_dir = out_dir / "models" / "raw_vault"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, sql in sorted(state.artifacts.dbt_models.items()):
        path = raw_dir / f"{name}.sql"
        path.write_text(sql, encoding="utf-8")
        written.append(path)
    stg_dir = out_dir / "models" / "staging"
    stg_dir.mkdir(parents=True, exist_ok=True)
    for name, sql in sorted(state.artifacts.staging_models.items()):
        path = stg_dir / f"{name}.sql"
        path.write_text(sql, encoding="utf-8")
        written.append(path)
    for rel_path, content in sorted(state.artifacts.scaffolding.items()):
        if rel_path == "README.md":
            continue  # curated by hand — see README.md
        target = out_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written


def main() -> None:
    state = asyncio.run(build_state())
    written = write_project(state)
    print(f"Generated {len(written)} file(s) into {HERE}:")
    for path in sorted(written):
        print(f"  - {path.relative_to(HERE)}")
    proposals = state.link_proposals
    print(f"\nLink proposals: {len(proposals.proposals)} per-key, "
          f"{len(proposals.relationships)} relationship-table; all ratified (--accept).")
    for link in state.dv_model.links:
        parts = ", ".join(
            ref.hub + (f" via {ref.key_translation.through_table}" if ref.key_translation else "")
            for ref in link.hub_refs
        )
        print(f"  {link.name}: {parts}")
    issues = state.validation_report.issues
    print(f"\nValidator: {len(issues)} issue(s)"
          + (" — " + ", ".join(sorted({i.code for i in issues})) if issues else ""))
    print(f"\nFlags ({len(state.flags)}):")
    for flag in state.flags:
        print(f"  ! [{flag.severity}] {flag.kind}: {flag.message}")


if __name__ == "__main__":
    main()
