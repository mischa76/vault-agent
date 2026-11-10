"""C60 — what AutomateDV does with late and out-of-order rows on vault-agent's output
(pre-registration in docs/architecture/backlog-2026-11-candidates.md, C60).

    uv sync --extra demo
    uv run python -m eval.automatedv.scenario

Part 1 generates a project with vault-agent's own `CodeGeneratorAgent` for one landing table
(`av_src.contact`: a hub and a satellite) and replays six loads A–F, some stamped before the
satellite's newest load. Part 2 builds the bank demo's effectivity satellite with its two batches
in reverse order. Needs PostgreSQL via the libpq variables (defaults: the local demo database
`aw_source` as `vault`) and network for `dbt deps`; drops and recreates the schemas `av_src`, `av`,
`av_bank` (and dbt's suffixed ones) — nothing else. Prints each prediction with its measurement."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
BUILD = HERE / "build"
PROJECT = BUILD / "contact"
BANK = BUILD / "bank"
REPO = HERE.parent.parent
PROFILE = """{name}:
  target: dev
  outputs:
    dev:
      type: postgres
      host: "{{{{ env_var('PGHOST', 'localhost') }}}}"
      port: "{{{{ env_var('PGPORT', '5432') | int }}}}"
      user: "{{{{ env_var('PGUSER', 'vault') }}}}"
      pass: "{{{{ env_var('PGPASSWORD', 'vault') }}}}"
      dbname: "{{{{ env_var('PGDATABASE', 'aw_source') }}}}"
      schema: {schema}
      threads: 4
"""

LOADS: list[tuple[str, str]] = [
    (
        "A 03-01: 1 gold, 2 silver",
        "insert into av_src.contact values (1, 'gold', '2026-03-01'), (2, 'silver', '2026-03-01');",
    ),
    (
        "B late: 1 bronze stamped 02-15",
        "update av_src.contact set segment = 'bronze', load_datetime = '2026-02-15' where "
        "contactid = 1;"
        "delete from av_src.contact where contactid = 2;",
    ),
    (
        "C 03-10: 1 gold re-delivered",
        "update av_src.contact set segment = 'gold', load_datetime = '2026-03-10' where "
        "contactid = 1;",
    ),
    (
        "D 03-20: 1 'Gold' (case only)",
        "update av_src.contact set segment = 'Gold', load_datetime = '2026-03-20' where "
        "contactid = 1;",
    ),
    (
        "E late: 2 silver stamped 02-20 (equal to its newest)",
        "delete from av_src.contact where contactid = 1;"
        "insert into av_src.contact values (2, 'silver', '2026-02-20');",
    ),
    (
        "F late: 1 bronze stamped 02-25 (equal to the version before the newest)",
        "delete from av_src.contact where contactid = 2;"
        "insert into av_src.contact values (1, 'bronze', '2026-02-25');",
    ),
]


def connect() -> Any:
    import psycopg2

    connection = psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        user=os.environ.get("PGUSER", "vault"),
        password=os.environ.get("PGPASSWORD", "vault"),
        dbname=os.environ.get("PGDATABASE", "aw_source"),
    )
    connection.autocommit = True
    return connection


def dbt(project: Path, *args: str) -> str:
    done = subprocess.run(
        [str(Path(sys.executable).parent / "dbt"), *args, "--profiles-dir", str(project)],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    log = done.stdout + done.stderr
    if done.returncode != 0:
        raise RuntimeError(log[-3000:])
    return log


def summary(log: str) -> str:
    """The satellite's result word from dbt's log line, ANSI colours removed (`INSERT 0 1`, `SELECT
    2`)."""
    import re

    plain = re.sub(r"\x1b\[[0-9;]*m", "", log)
    found = re.findall(r"sat_contact_details \.+ \[(\w+ [0-9 ]+)", plain)
    return found[-1].strip() if found else "?"


def generate() -> None:
    from vault_agent.agents.code_generator import CodeGeneratorAgent
    from vault_agent.cli import write_outputs
    from vault_agent.state import DVModel, SourceColumn, SourceTable, VaultAgentState

    model = DVModel.model_validate(
        {
            "hubs": [
                {
                    "name": "hub_contact",
                    "business_key": "ContactID",
                    "source_entity": "contact",
                    "description": "a contact",
                }
            ],
            "links": [],
            "satellites": [
                {
                    "name": "sat_contact_details",
                    "parent": "hub_contact",
                    "attributes": ["Segment"],
                    "source_table": "contact",
                    "description": "the segment",
                }
            ],
        }
    )
    table = SourceTable(
        table="contact",
        schema="av_src",
        columns=[
            SourceColumn(name="contactid", type="integer"),
            SourceColumn(name="segment", type="text"),
        ],
    )
    state = asyncio.run(
        CodeGeneratorAgent().run(VaultAgentState(dv_model=model, source_schemas=[table]))
    )
    write_outputs(state, PROJECT)
    (PROJECT / "profiles.yml").write_text(PROFILE.format(name="vault_project", schema="av"))


def main() -> int:
    connection = connect()
    cursor = connection.cursor()
    cursor.execute(
        "set client_min_messages = warning; drop schema if exists av_src cascade; "
        "drop schema if exists av cascade; drop schema if exists av_bank cascade; create "
        "schema av_src; "
        "create table av_src.contact (contactid integer, segment text, load_datetime timestamp "
        "not null, "
        "record_source text not null default 'av_src.contact');"
    )
    shutil.rmtree(BUILD, ignore_errors=True)
    generate()
    dbt(PROJECT, "deps")
    inserted: dict[str, str] = {}
    for index, (label, sql) in enumerate(LOADS):
        cursor.execute(sql)
        log = dbt(PROJECT, "build", *(["--full-refresh"] if index == 0 else []))
        inserted[label[0]] = summary(log)
        print(f"load {label}: sat_contact_details {inserted[label[0]]}")

    def history(contact: int) -> list[tuple[str, str]]:
        cursor.execute(
            "select s.segment, s.load_datetime::date::text from av.sat_contact_details s "
            "join av.hub_contact h using (contact_hk) where h.contactid = %s "
            "and s.record_source <> 'AUTOMATE_DV_SYSTEM' order by s.load_datetime",
            (contact,),
        )
        return [(r[0], r[1]) for r in cursor.fetchall()]

    one, two = history(1), history(2)
    print(f"contact 1 history: {one}")
    print(f"contact 2 history: {two}")
    checks = [
        ("P1 B (late, differs) inserted with its own ldts", ("bronze", "2026-02-15") in one),
        ("P2 C (equal to the newest) inserts nothing", ("gold", "2026-03-10") not in one),
        # since WP123 (C61) both P3 checks report DIFFERS — the fix: D inserts, `Gold` is newest
        ("P3 D (case only) inserts nothing", not any(s == "Gold" for s, _ in one)),
        ("P3 newest value reads 'gold' while the source said 'Gold'", one and one[-1][0] == "gold"),
        ("P4 E (late, equal to the newest) inserts nothing", two == [("silver", "2026-03-01")]),
        (
            "P5 F (late, equal to the version before the newest) inserted",
            ("bronze", "2026-02-25") in one,
        ),
        (
            "P5 two consecutive identical versions (bronze, bronze)",
            [s for s, _ in one[:2]] == ["bronze", "bronze"],
        ),
    ]
    for name, ok in checks:
        print(f"{'HOLDS ' if ok else 'DIFFERS'} {name}")

    # Part 2 — the bank demo's effectivity satellite, its two batches in reverse order (P6, not
    # predicted)
    shutil.copytree(
        REPO / "demo" / "bank_postgres",
        BANK,
        ignore=shutil.ignore_patterns("target", "dbt_packages", "logs", "__pycache__"),
    )
    (BANK / "profiles.yml").write_text(PROFILE.format(name="bank_postgres", schema="av_bank"))
    dbt(BANK, "deps")
    dbt(BANK, "seed")
    eff = [
        "stg_account",
        "stg_customer",
        "stg_account_customer",
        "hub_account",
        "hub_customer",
        "link_account_customer",
        "sat_account_customer_eff",
    ]
    dbt(BANK, "run", "--select", *eff, "--vars", '{load_batch: "2026-04-01"}', "--full-refresh")
    dbt(BANK, "run", "--select", *eff, "--vars", '{load_batch: "2026-01-01"}')
    cursor.execute(
        """select c.national_customer_id, e.effective_from::date::text,
                  e.effective_to::date::text, e.load_datetime::date::text
             from av_bank.sat_account_customer_eff e
             join av_bank.hub_account a on a.account_hk = e.account_hk
             join av_bank.hub_customer c on c.customer_hk = e.customer_hk
            where a.account_number = 'ACC-503'
            order by e.load_datetime, c.national_customer_id"""
    )
    rows = cursor.fetchall()
    print("P6 ACC-503 after 2026-04-01 then 2026-01-01 (owner, from, to, loaded):")
    for row in rows:
        print("   ", row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
