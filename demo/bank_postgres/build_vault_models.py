#!/usr/bin/env python
"""Generate the bank demo's raw-vault dbt models from the *real* CodeGeneratorAgent.

This ties the runnable Durchstich (demo/bank_postgres) to the system's actual output: it
constructs a fixed, hand-checked bank ``DVModel`` (no LLM, no API key) and feeds it to the
same ``CodeGeneratorAgent`` the pipeline uses, then writes every emitted model to
``models/raw_vault/<name>.sql``. The vault SQL is therefore generated, never hand-written
(see CLAUDE.md → "What NOT to do" and docs/architecture/poc-end-to-end-dbt-spec.md §3/§5).

Running it is idempotent: same model in, byte-identical SQL out. Run with
``uv run python demo/bank_postgres/build_vault_models.py`` (or from this directory).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.state import DVModel, Hub, Link, Satellite, VaultAgentState

# Where the generated raw-vault models land — resolved from this file, not the cwd, so the
# script works both from the repo root and from inside demo/bank_postgres/.
RAW_VAULT_DIR = Path(__file__).parent / "models" / "raw_vault"


def build_bank_dv_model() -> DVModel:
    """The fixed bank DV model (spec §3). Construct names and columns are exact: the
    generator derives physical names from them (UPPER_SNAKE + the rules/ suffixes), so the
    staging models and seeds are written to match this model, not the other way round."""
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
            # Order fixes src_fk = [ACCOUNT_HK, CUSTOMER_HK] (spec §3).
            connected_hubs=["hub_account", "hub_customer"],
            description="Ownership of an account by a customer (one owner at a time).",
            link_type="standard",
            # The account is the fixed side; the owning customer rotates over time, so the
            # effectivity satellite end-dates by the account.
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
            # Order matters: start date first, end date second (spec §3).
            attributes=["effective from", "effective to"],
            description="Active period of the account-customer ownership relationship.",
            sat_type="effectivity",
        ),
    ]
    return DVModel(hubs=hubs, links=links, satellites=satellites)


async def generate_models(model: DVModel) -> VaultAgentState:
    """Run the real code generator over the fixed model."""
    state = VaultAgentState(dv_model=model)
    return await CodeGeneratorAgent().run(state)


def write_models(state: VaultAgentState, out_dir: Path = RAW_VAULT_DIR) -> list[Path]:
    """Write each generated dbt model to out_dir/<name>.sql; return the paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, sql in sorted(state.artifacts.dbt_models.items()):
        path = out_dir / f"{name}.sql"
        path.write_text(sql, encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    model = build_bank_dv_model()
    state = asyncio.run(generate_models(model))

    written = write_models(state)
    meta = state.artifacts.automatedv_yaml
    print(f"Generated {len(written)} raw-vault models into {RAW_VAULT_DIR}:")
    for path in written:
        print(f"  - {path.name}")
    print(
        "Summary: "
        f"{len(meta.get('hubs', {}))} hub(s), "
        f"{len(meta.get('links', {}))} link(s), "
        f"{len(meta.get('satellites', {}))} satellite(s)."
    )
    # Surface generator errors/flags (there should be none for this fixed model).
    if state.errors:
        print("\nGenerator flags/errors:")
        for err in state.errors:
            print(f"  ! {err}")
    else:
        print("No generator errors.")


if __name__ == "__main__":
    main()
