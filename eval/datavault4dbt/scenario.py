"""C56 — the datavault4dbt probe, replayed from nothing: sources, four loads, the two defect
models, the oracle.

    uv sync --extra demo            # dbt-core 1.9 + dbt-postgres
    uv run python -m eval.datavault4dbt.scenario

Needs a PostgreSQL holding `HumanResources.JobCandidate` (the WP110 loader's `aw_source`), reached
through the libpq variables (`PGHOST`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`; defaults the local
demo database), and network for `dbt deps`. Drops and recreates the schemas `dv4x_src` and `dv4x` —
nothing else. Exit 0 when every check holds except the recorded defects and both defect models fail
as recorded; 1 otherwise (a new failure, or a defect that went away — either is news). See
README.md."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).parent / "project"

SETUP = """
set client_min_messages = warning;
drop schema if exists dv4x cascade;
drop schema if exists dv4x_src cascade;
create schema dv4x_src;
create table dv4x_src.probe (probeid integer primary key, doc json, pos point,
  load_datetime timestamp not null, record_source text not null default 'dv4x_src.probe');
create table dv4x_src.business_entity (businessentityid integer primary key, name text,
  load_datetime timestamp not null, record_source text not null default 'dv4x_src.business_entity');
create table dv4x_src.customer (customerid integer primary key, personid integer, storeid integer,
"group" text, segment text, load_datetime timestamp not null, record_source text not null default
'dv4x_src.customer');
create table dv4x_src.product (productid integer primary key, productnumber text not null,
  load_datetime timestamp not null, record_source text not null default 'dv4x_src.product');
create table dv4x_src.order_line (orderlineid integer primary key, productid integer, orderdate
date, rowguid uuid, qty integer, load_datetime timestamp not null, record_source text not null
default 'dv4x_src.order_line');
create table dv4x_src.vendor (vendorid integer primary key, vendorname text,
  load_datetime timestamp not null, record_source text not null default 'dv4x_src.vendor');
create table dv4x_src.contact (contactid integer primary key, segment text,
  load_datetime timestamp not null, record_source text not null default 'dv4x_src.contact');
create table dv4x_src.phone (contactid integer, phonetype text, phonenumber text, load_datetime
timestamp not null, record_source text not null default 'dv4x_src.phone', primary key (contactid,
phonetype));
create table dv4x_src.nasty (id integer primary key, k1 text, k2 text, attr text,
  load_datetime timestamp not null default '2026-04-01', record_source text not null default
  'dv4x_src.nasty');
"""

LOADS: list[tuple[str, str]] = [
    (
        "load 1 — everything's first delivery",
        """
insert into dv4x_src.probe values (1, '{"a": 1}', point(1, 2), '2026-01-01'),
  (2, '{"b": [1, 2]}', point(3, 4), '2026-01-01'), (3, null, null, '2026-01-01');
insert into dv4x_src.business_entity values (10, 'person ten', '2026-01-01'), (20, 'store twenty',
'2026-01-01'), (30, 'person thirty', '2026-01-01');
insert into dv4x_src.customer values (1, 10, null, 'retail', 'retail', '2026-01-01'),
  (2, null, 20, 'wholesale', 'wholesale', '2026-01-01'), (3, 30, 20, 'retail', 'retail',
  '2026-01-01');
insert into dv4x_src.product values (1, 'BK-100', '2026-01-01'), (2, 'BK-200', '2026-01-01');
insert into dv4x_src.order_line values
  (100, 1, '2026-01-05', 'a0000000-0000-0000-0000-000000000001', 3, '2026-01-01'),
  (101, 2, null, null, 1, '2026-01-01'),
  (102, 9, '2026-01-06', 'a0000000-0000-0000-0000-000000000002', 2, '2026-01-01'),
  (103, null, '2026-01-07', 'a0000000-0000-0000-0000-000000000003', 5, '2026-01-01');
insert into dv4x_src.vendor values (20, 'store twenty as vendor', '2026-01-01'),
  (40, 'vendor forty', '2026-01-01');
insert into dv4x_src.contact values (1, 'gold', '2026-03-01'), (2, 'silver', '2026-03-01');
insert into dv4x_src.phone values (1, 'home', '111', '2026-03-01'), (1, 'cell', '222',
'2026-03-01'), (2, 'cell', '333', '2026-03-01');
insert into dv4x_src.nasty (id, k1, k2, attr) values
  (1, 'a||', 'b', 'x'), (2, 'a', '||b', 'x'), (3, 'Ab', 'c', 'Same'), (4, 'AB', 'C', 'same'),
  (5, ' pad ', 'q', ' pad '), (6, 'pad', 'q', 'pad'), (7, '^^', null, '"quoted"'), (8, null, '^^',
  null), (9, null, null, 'all-null key'), (10, 'z', 'n1', 'ab'), (11, 'z', 'n2', E'a\\nb'), (12,
  'z', 'n3', E'a\\nb\\nc'), (13, 'z', 'n4', E'ab\\nc'), (14, 'z', 'n5', 'abc');
""",
    ),
    (
        "load 2 — an ownership change, a re-delivery, a LATE contact row (stamped before load 1's)",
        """
update dv4x_src.probe set doc = '{"a": 2}', pos = point(9, 9), load_datetime = '2026-02-01' where
probeid = 1;
update dv4x_src.customer set personid = 30, load_datetime = '2026-02-01' where customerid = 1;
update dv4x_src.customer set load_datetime = '2026-02-01' where customerid <> 1;
update dv4x_src.order_line set load_datetime = '2026-02-01';
update dv4x_src.contact set segment = 'bronze', load_datetime = '2026-02-15' where contactid = 1;
update dv4x_src.contact set load_datetime = '2026-03-05' where contactid = 2;
update dv4x_src.phone set load_datetime = '2026-03-05';
update dv4x_src.phone set phonenumber = '999' where contactid = 1 and phonetype = 'cell';
""",
    ),
    (
        "load 3 — a new order line and a corrected quantity, a deleted contact, a removed phone",
        """
insert into dv4x_src.order_line values
  (104, 1, '2026-02-02', 'a0000000-0000-0000-0000-000000000004', 7, '2026-02-02');
update dv4x_src.order_line set qty = 30, load_datetime = '2026-02-02' where orderlineid = 100;
delete from dv4x_src.contact where contactid = 2;
update dv4x_src.contact set segment = 'gold', load_datetime = '2026-03-10' where contactid = 1;
delete from dv4x_src.phone where contactid = 1 and phonetype = 'home';
update dv4x_src.phone set load_datetime = '2026-03-10';
""",
    ),
    (
        "load 4 — a change of case only",
        """
update dv4x_src.contact set segment = 'Gold', load_datetime = '2026-03-20' where contactid = 1;
""",
    ),
]

# The defect models and the message each must fail with (README, defects 1 and 2).
DEFECT_MODELS = {
    "customer_reserved_payload_s0": 'syntax error at or near "group"',
    "control_snap_v1_documented": "invalid input syntax for type interval",
}


@dataclass
class Build:
    ok: bool
    log: str


def dbt(*args: str) -> Build:
    executable = Path(sys.executable).parent / "dbt"
    done = subprocess.run(
        [str(executable), *args, "--profiles-dir", str(PROJECT)],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        check=False,
    )
    return Build(done.returncode == 0, done.stdout + done.stderr)


def connect() -> Any:
    import psycopg2  # the catalogue extra's driver; imported here so the module loads without it

    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        user=os.environ.get("PGUSER", "vault"),
        password=os.environ.get("PGPASSWORD", "vault"),
        dbname=os.environ.get("PGDATABASE", "aw_source"),
    )


def main() -> int:
    from eval.datavault4dbt.oracle import run_checks

    connection = connect()
    connection.autocommit = True
    with connection.cursor() as cursor:
        cursor.execute(SETUP)
    deps = dbt("deps")
    if not deps.ok:
        print(deps.log)
        return 1
    for index, (label, sql) in enumerate(LOADS):
        with connection.cursor() as cursor:
            cursor.execute(sql)
        args = ["build", "--exclude", "path:models/defects"] + (
            ["--full-refresh"] if index == 0 else []
        )
        build = dbt(*args)
        summary = next((ln for ln in build.log.splitlines() if "Done. PASS=" in ln), "no summary")
        print(f"{label}: {summary.split('Done. ')[-1]}")
        if not build.ok:
            print(build.log)
            return 1
    defects_as_recorded = True
    for model, message in DEFECT_MODELS.items():
        build = dbt("build", "-s", model)
        as_recorded = not build.ok and message in build.log
        defects_as_recorded &= as_recorded
        verdict = "fails as recorded" if as_recorded else "DOES NOT fail as recorded"
        print(f"defect model {model}: {verdict}")
    checks = run_checks(connection)
    for check in checks:
        mark = "PASS" if check.ok else ("KNOWN" if check.defect else "FAIL")
        note = (
            f"  [{check.detail}]" if check.detail and (not check.ok or check.informational) else ""
        )
        defect = f"  (defect {check.defect})" if check.defect and not check.ok else ""
        print(f"{mark} {check.name}{note}{defect}")
    passed = sum(c.ok for c in checks)
    print(f"{passed}/{len(checks)} checks pass")
    unexpected = [c for c in checks if c.ok == bool(c.defect)]
    for c in unexpected:
        print(
            f"UNEXPECTED: {c.name} — {'passes although a defect is recorded' if c.ok else 'fails'}"
        )
    return 0 if not unexpected and defects_as_recorded else 1


if __name__ == "__main__":
    raise SystemExit(main())
