# datavault4dbt probe and oracle (C56)

A reproducible check of what **datavault4dbt** builds, against an **oracle** computed independently of the
package — written when datavault4dbt (and TurboVault, which generates datavault4dbt code) came up as a possible
second target for vault-agent (C47, ADR-0020). Candidate C56 in
`docs/architecture/backlog-2026-11-candidates.md` holds the comparison with AutomateDV; `docs/log.md`
(2026-11-09) the rounds that led here.

## Run

```bash
uv sync --extra demo                         # dbt-core 1.9 + dbt-postgres
uv run python -m eval.datavault4dbt.scenario
```

Needs a PostgreSQL with `HumanResources.JobCandidate` (the `aw_source` database the WP110 loader writes,
`eval/adventureworks/load_postgres.py`), reached through `PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD`/`PGDATABASE`
(defaults: the local demo database `aw_source` as `vault`), and network for `dbt deps`. It **drops and recreates
the schemas `dv4x_src` and `dv4x`** and touches nothing else. The keyless part — the two hash models pinned against
the warehouse's hashes — runs in the suite: `tests/test_c56_datavault4dbt_hashing.py`.

## What it does

- `project/` — a dbt project on datavault4dbt **2.3.0** with the package's defaults (only the escape characters
  set): stages, hubs (one from two sources, one keyed on a `date`, one on a `uuid`), a link with a hub in two roles,
  a NULL participant and a prejoined key, a non-historised link, `sat_v0`/`sat_v1` (one over an `xml` column, one
  with the high-water mark off), an effectivity satellite, a record-tracking satellite, a multi-active satellite,
  the snapshot control tables and a PIT. `models/defects/` holds the two models that fail on purpose.
- `scenario.py` — creates the sources and replays four loads: first deliveries; an ownership change, a re-delivery
  and a **late** row stamped before the previous load; a new transaction, a corrected one, a deleted key and a
  removed phone; a change of **case only**. Then it builds the two defect models and runs the oracle.
- `oracle.py` — recomputes from the sources and the loads what the vault must hold: hub keys and their hashes, link
  combinations, one satellite row per change, `sat_v1` end dates, every PIT row, the multi-active groups, and every
  hashkey/hashdiff of a collision probe (`dv4x_src.nasty`) under the documented rules (`hashing.py`).
- Exit 0 when every check holds **except the recorded defects**, and the defect models fail as recorded; exit 1 on a
  new failure **or on a defect that went away** — after a package upgrade either is news.

## Result (2026-11-09: datavault4dbt 2.3.0, dbt-core 1.9.10, dbt-postgres 1.9.1, PostgreSQL 16.15)

Everything reconciles — hubs, links, satellite histories, `sat_v1` end dates (next load − 1 µs), every PIT row,
multi-active groups, every hashkey, no delimiter collision — except:

1. **A reserved payload column breaks `sat_v0` on PostgreSQL** (`syntax error at or near "group"`): the stage
   escapes it when the escape variables are set, `postgres__sat_v0` prints the payload without
   `escape_column_names` (Snowflake, SQL Server, Databricks and Fabric escape it there).
2. **`control_snap_v1.md`'s own example fails**: `forever: 'TRUE'` is a string, every adapter's macro tests
   `is true`, and PostgreSQL gets `INTERVAL ' '`. The boolean `true` builds.
3. **The hashdiff is case-insensitive** unless the root project sets
   `datavault4dbt.hashdiff_input_case_sensitive: true` itself — the package documents `TRUE` as the default.
   Consequence: `gold` → `Gold` is not stored, and the satellite's current value differs from the source's.
4. **PostgreSQL's `regexp_replace` without `g`**: only the first backslash and quote are escaped and only the first
   `\n \t \v \r` of the whole hash input is removed. Consequence: `ab` and `a⏎b` share a hashdiff, so do `ab⏎c` and
   `abc`, while `a⏎b⏎c` differs from both — a text that gains or loses a line break is not historised.

**Observations, not defects:** a dangling reference (a product id that does not exist) becomes the zero key, the same
as a missing one, unflagged; under the default high-water mark a late row is not loaded at all (with
`disable_hwm: true` it is, and the timeline is right); a deleted key stays current in its satellite, only the
record-tracking satellite shows its deliveries ending; a source `timestamp` arrives as `timestamptz`.

Nothing has been reported upstream; whether to is the owner's decision.
