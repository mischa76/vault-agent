#!/usr/bin/env python
"""Generate the grounded+ratified mapping demo's dbt models from the *real* generator.

This is the runnable capture of WP9 §10.8 (docs/architecture/backlog-2026-07/wp9-mapping-spec.md,
acceptance #8): a GROUNDED + RATIFIED single-source run whose GENERATED staging binds to the
real, business-named source tables (``customer`` / ``account`` / ``account_customer``) rather
than the inferred ``raw_*`` relations of the ungrounded demo (demo/bank_postgres).

Deterministic, no LLM, no API key — the same principle as demo/bank_postgres/build_vault_models.py:
a fixed, hand-checked ``DVModel`` (identical to that demo's, so both stay comparable) is fed to
the same ``CodeGeneratorAgent`` the pipeline uses, but here the state also carries

  * a DECLARED source schema (ADR-0004 grounding) —
    examples/inputs/bank_source_schema_enriched.yml — so the generated staging binds to the
    declared tables by name, and
  * the RATIFIED business↔source mapping (WP9) the live SourceMapperAgent proposed and a human
    accepted, applied via ``rebind_staging`` exactly as the pipeline's resume path does.

For the bank the two coincide (the source column names already equal the business keys, so the
ratified ``src_nk`` equals the grounded one) — that is precisely why the bank is the high-floor
case. The MAPPING half (the live mapper + profiling) is documented in README.md with its measured
result; this script reproduces the deterministic BUILD half so ``dbt build`` is re-runnable by
anyone, byte-identically, without a key.

Run: ``uv run python demo/mapping_postgres/build_vault_models.py`` (or from this directory).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.source_mapper import rebind_staging
from vault_agent.source_schema import load_source_schemas
from vault_agent.state import (
    DVModel,
    Hub,
    Link,
    Proposal,
    ProposedMapping,
    Satellite,
    SourceTable,
    VaultAgentState,
)

HERE = Path(__file__).parent
# The declared source schema is the exact §10.8 input, kept in one place (examples/inputs).
ENRICHED_SCHEMA = (
    HERE.parents[1] / "examples" / "inputs" / "bank_source_schema_enriched.yml"
)


def build_grounded_bank_model() -> DVModel:
    """The fixed bank DV model — IDENTICAL to demo/bank_postgres' build_bank_dv_model(), so the
    two demos differ only in *how the source is bound* (ungrounded raw_* vs. grounded+ratified),
    never in the model. 2 hubs, one standard link with a driving key, 2 standard sats, 1 eff_sat."""
    hubs = [
        Hub(
            name="hub_customer",
            business_key="national customer ID",
            source_entity="customer",
            description="A bank customer, anchored on the national customer ID.",
        ),
        Hub(
            name="hub_account",
            business_key="account number",
            source_entity="account",
            description="A bank account, anchored on the bank-issued account number.",
        ),
    ]
    links = [
        Link(
            name="link_account_customer",
            # Order fixes src_fk = [ACCOUNT_HK, CUSTOMER_HK].
            connected_hubs=["hub_account", "hub_customer"],
            description="Ownership of an account by a customer (one owner at a time).",
            link_type="standard",
            driving_key=["hub_account"],
            unit_of_work="One account is owned by exactly one customer at any point in time.",
        ),
    ]
    satellites = [
        Satellite(
            name="sat_customer_details",
            parent="hub_customer",
            attributes=["customer name", "date of birth"],
            description="Descriptive customer attributes.",
            sat_type="standard",
        ),
        Satellite(
            name="sat_account_details",
            parent="hub_account",
            attributes=["balance", "status"],
            description="Descriptive account attributes that change over time.",
            sat_type="standard",
        ),
        Satellite(
            name="sat_account_customer_eff",
            parent="link_account_customer",
            # Start date first, end date second.
            attributes=["effective from", "effective to"],
            description="Active period of the account-customer ownership relationship.",
            sat_type="effectivity",
        ),
    ]
    return DVModel(hubs=hubs, links=links, satellites=satellites)


def ratified_mappings() -> ProposedMapping:
    """The business↔source mapping the live SourceMapperAgent proposed and a human accepted
    (WP9 §5). Only the hub business keys drive staging re-binding (``source_overrides``); the
    descriptive attributes stay source-faithful. Category ``exact_name`` / status ``accepted``
    mirror the live §10.8 run (all 9 concepts resolved by exact name, 0 gaps, 0 unresolved)."""
    return ProposedMapping(
        proposals=[
            Proposal(
                concept="national customer ID",
                entity="customer",
                table="customer",
                column="national_customer_id",
                confidence=0.99,
                category="exact_name",
                ratification_status="accepted",
                evidence=["Anchor table for the customer entity is 'customer'.",
                          "Exact concept-to-column name match; uniqueness=1, null=0."],
            ),
            Proposal(
                concept="account number",
                entity="account",
                table="account",
                column="account_number",
                confidence=0.99,
                category="exact_name",
                ratification_status="accepted",
                evidence=["Anchor table for the account entity is 'account'.",
                          "Exact concept-to-column name match; uniqueness=1, null=0."],
            ),
        ]
    )


def declared_source_schema() -> list[SourceTable]:
    """The declared (grounded) source schema — the exact §10.8 enriched input (ADR-0004)."""
    return load_source_schemas(ENRICHED_SCHEMA)


async def build_state() -> VaultAgentState:
    """Run the real code generator over the fixed model, grounded, then apply the ratified
    mapping via the same ``rebind_staging`` the pipeline's resume path uses (WP9 §6)."""
    state = VaultAgentState(
        dv_model=build_grounded_bank_model(),
        source_schemas=declared_source_schema(),
    )
    state = await CodeGeneratorAgent().run(state)
    state.mappings = ratified_mappings()
    rebind_staging(state)  # ratified hub-key bindings override the inference (no-op-equal here)
    return state


def write_project(state: VaultAgentState, out_dir: Path = HERE) -> list[Path]:
    """Write the generated raw-vault + staging models and scaffolding into a runnable dbt
    project. README.md (curated §10.8 walkthrough) and profiles.yml / seeds (user inputs) are
    committed by hand and NOT overwritten — so the generated scaffolding's README is skipped."""
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

    for rel_path, content in state.artifacts.scaffolding.items():
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
    meta = state.artifacts.automatedv_yaml
    print(f"Generated {len(written)} file(s) into {HERE}:")
    for path in sorted(written):
        print(f"  - {path.relative_to(HERE)}")
    print(
        "Summary: "
        f"{len(meta.get('hubs', {}))} hub(s), "
        f"{len(meta.get('links', {}))} link(s), "
        f"{len(meta.get('satellites', {}))} satellite(s), "
        f"{len(state.artifacts.staging_models)} staging model(s)."
    )
    # Grounded + ratified: every staging model binds to a declared source table, so there are
    # NO inferred-source-binding flags (the contrast with the ungrounded demo/bank_postgres).
    if state.flags:
        print("\nGenerator flags:")
        for flag in state.flags:
            print(f"  ! [{flag.severity}] {flag}")
    else:
        print("No generator flags (every staging model bound to a declared source).")


if __name__ == "__main__":
    main()
