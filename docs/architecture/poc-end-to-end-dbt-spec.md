# PoC Spec — End-to-End Durchstich: requirements → running Data Vault (dbt + AutomateDV + Postgres)

> **Purpose.** Turn the generated AutomateDV/dbt models into a *running* Data Vault: real
> tables loaded by real ETL, executed locally. This is the proof that the pipeline's output is
> not just plausible SQL but **operable** code. Implementation-ready blueprint for Claude Code,
> same `[ENFORCE]`/`[GUIDE]` discipline as
> [review-2026-06-remediation-spec.md](./review-2026-06-remediation-spec.md).
>
> **Author of spec:** review/architecture pass, 2026-06-16. **Implements:** Claude Code.

## How to use this in Claude Code

Work the **Rollout order** at the bottom. Each phase is self-contained and ends with a
`dbt` command that must succeed. Keep `ruff`/`mypy`/`pytest` green for any Python touched (the
demo builder script is deterministic and must run without an API key). Do not bypass AutomateDV
(see `CLAUDE.md` → "What NOT to do"): the raw-vault models come from the **code generator's
output**, never hand-written.

Definition of done: `dbt build` runs green against a local Postgres for the bank demo, the vault
tables are populated, and a verification query shows non-zero rows in every hub/link/satellite.
The demo lives in the repo and is documented.

---

## 0. Key decision & finding (read first)

**AutomateDV does not support DuckDB.** The official platform matrix lists **Snowflake, Google
BigQuery, MS SQL Server, Databricks, Postgres** (Redshift planned). DuckDB has no `duckdb__`
macro implementations, so `dbt run` on the AutomateDV macros would fail. This contradicts the
"DuckDB for demo" wording in `README.md`/`CLAUDE.md`.

**Decision:** the Durchstich targets **Postgres** — officially supported, fully local, free
(Docker or apt). Crucially, the code generator emits standard `{{ config(materialized='incremental') }}`,
**not** AutomateDV's custom materialisations, so the known Postgres custom-materialisation
limitation (CTE handling) does **not** apply here.

**Consequence (in scope for this spec):** update `README.md` and `CLAUDE.md` to say **Postgres**
(not DuckDB) as the local demo target. (DuckDB could later be revisited via a custom
duckdb→postgres dispatch shim — out of scope, tracked as a follow-up in §9.)

Sources: AutomateDV Platform Support — https://automate-dv.readthedocs.io/en/latest/platform_support/ ·
dbt Compatibility — https://automate-dv.readthedocs.io/en/latest/versions/

---

## 1. Software & versions [ENFORCE]

All free / open source. Pin these (verified against AutomateDV docs, 2026-06):

| Component | Version | Notes |
|---|---|---|
| AutomateDV | `0.11.4` | dbt package via `packages.yml` (dbt Hub: `Datavault-UK/automate_dv`) |
| dbt-core | `~=1.9.0` | AutomateDV 0.11.4 supports dbt `>=1.9, <3.0`; 1.9.x is the conservative choice |
| dbt-postgres | `~=1.9.0` | adapter; install alongside dbt-core |
| PostgreSQL | `16` | local server; Docker (recommended) or apt |

Install (in the project, via uv — keep these in an optional extra so they don't bloat the core
package):

- Add a `demo` optional-dependency group in `pyproject.toml`: `dbt-core~=1.9.0`,
  `dbt-postgres~=1.9.0`.
- `uv sync --extra demo` then `uv run dbt deps` (pulls AutomateDV per `packages.yml`).

Postgres via Docker (preferred — reproducible, no host install): a `docker-compose.yml` in the
demo dir with `postgres:16`, a named volume, port `5432`, db `vault`, user/password `vault`/`vault`.
Provide an apt fallback note in the runbook for users without Docker.

---

## 2. Target architecture

Three dbt layers, raw → staging → raw vault:

```
seeds/raw_*.csv  ──►  models/staging/stg_*.sql   ──►  models/raw_vault/{hub,link,sat}_*.sql
(raw source data)     (automate_dv.stage:               (generator output:
                       adds HK / HASHDIFF,                automate_dv.hub/link/sat/eff_sat)
                       LOAD_DATETIME, RECORD_SOURCE)
```

- **Seeds** = the toy raw source data (CSV), loaded with `dbt seed`.
- **Staging** = hand-authored `automate_dv.stage()` models that compute the hash keys and
  hashdiffs the vault models reference. **This is the layer the generator does not yet emit** —
  see §9.
- **Raw vault** = the **code generator's output**, dropped in unchanged. The generator already
  sets `source_model='stg_<base>'`, so the vault models `ref()` the staging models by name.

---

## 3. The fixed bank DV model [ENFORCE]

To make the Durchstich deterministic (no LLM variance), the demo uses a **fixed, hand-checked**
`DVModel` for the bank domain, fed to the **real** `CodeGeneratorAgent`. Construct names and
columns below are exact — staging and seeds must match them, because the generator derives
physical names from them via `normalize_identifier` (UPPER_SNAKE) and the suffixes in
`rules/dv2_rules.py` (`_HK`, `_HASHDIFF`, `LOAD_DATETIME`, `RECORD_SOURCE`, `stg_`).

Derived from `examples/inputs/bank_account_requirements.md`:

| Construct | Type | Key facts | Generated physical names |
|---|---|---|---|
| `hub_customer` | hub | BK `national customer ID`, source_entity `customer` | model `hub_customer`, `src_pk=CUSTOMER_HK`, `src_nk=NATIONAL_CUSTOMER_ID`, source `stg_customer` |
| `hub_account` | hub | BK `account number`, source_entity `account` | `src_pk=ACCOUNT_HK`, `src_nk=ACCOUNT_NUMBER`, source `stg_account` |
| `link_account_customer` | link (standard) | connects `hub_account`, `hub_customer`; `driving_key=["hub_account"]` (one owner at a time per account) | `src_pk=LINK_ACCOUNT_CUSTOMER_HK`, `src_fk=[ACCOUNT_HK, CUSTOMER_HK]`, source `stg_account_customer` |
| `sat_customer_details` | satellite (standard) | parent `hub_customer`; attrs `customer name`, `date of birth` | `src_pk=CUSTOMER_HK`, `src_hashdiff=CUSTOMER_DETAILS_HASHDIFF`, `src_payload=[CUSTOMER_NAME, DATE_OF_BIRTH]`, source `stg_customer` |
| `sat_account_details` | satellite (standard) | parent `hub_account`; attrs `balance`, `status` | `src_hashdiff=ACCOUNT_DETAILS_HASHDIFF`, `src_payload=[BALANCE, STATUS]`, source `stg_account` |
| `sat_account_customer_eff` | effectivity sat | parent `link_account_customer`; attrs `effective from`, `effective to` (in that order) | `src_pk=LINK_ACCOUNT_CUSTOMER_HK`, `src_dfk="ACCOUNT_HK"`, `src_sfk=["CUSTOMER_HK"]`, `src_start_date=EFFECTIVE_FROM`, `src_end_date=EFFECTIVE_TO`, source `stg_account_customer` |

This exercises **hub + standard link + standard satellite + effectivity satellite** — four
construct types, all with consistent grain and all officially Postgres-supported. Multi-active
satellites (addresses) and transactional links (transactions) are **deliberately deferred** to
§9 because they surface real generator design questions (grain of a sat's source model;
self-referencing links). Keep the core Durchstich clean; document the rest as findings.

> **Note on the effectivity satellite:** verify it runs under standard `incremental` on Postgres
> during Phase B. If AutomateDV's `eff_sat` on Postgres needs behaviour the generator's plain
> `incremental` config doesn't give, fall back to delivering Phase A (hubs/link/standard sats) as
> the headline Durchstich and record the eff_sat result as a finding — do not block the PoC on it.
>
> **Update (2026-06-23): resolved** by
> [eff-sat-incremental-fix-spec.md](./eff-sat-incremental-fix-spec.md). The incremental eff_sat
> *did* need more than the plain config: `src_eff` had to be decoupled from `src_start_date` (the
> generator now emits a dedicated `APPLIED_DTS` column), and auto end-dating had to be enabled in
> the generated `config(is_auto_end_dating=true)`. The incremental run is now green and idempotent,
> and end-dating is demonstrated via a two-phase load (demo README → "Phase B2").

---

## 4. Deliverables — repository layout

Create under `demo/bank_postgres/` (committed; a public demo artifact):

```
demo/bank_postgres/
├── README.md                      # the runbook (see §7)
├── docker-compose.yml             # postgres:16
├── build_vault_models.py          # builds the fixed DVModel, runs CodeGeneratorAgent, writes raw_vault/*.sql
├── dbt_project.yml
├── packages.yml                   # AutomateDV 0.11.4
├── profiles.yml                   # postgres target (or document ~/.dbt/profiles.yml)
├── seeds/
│   ├── raw_customer.csv
│   ├── raw_account.csv
│   └── raw_account_customer.csv
└── models/
    ├── staging/
    │   ├── stg_customer.sql
    │   ├── stg_account.sql
    │   └── stg_account_customer.sql
    └── raw_vault/                 # GENERATED — do not hand-edit
        ├── hub_customer.sql
        ├── hub_account.sql
        ├── link_account_customer.sql
        ├── sat_customer_details.sql
        ├── sat_account_details.sql
        └── sat_account_customer_eff.sql
```

`models/raw_vault/` is written by `build_vault_models.py`. Add a `.gitkeep` or commit the
generated files (commit them — reviewers should see the output without running the script).

---

## 5. The generator-integration script [ENFORCE]

`build_vault_models.py` ties the demo to the **real system output**:

1. Construct the fixed bank `DVModel` (the §3 constructs) directly in Python using
   `vault_agent.state` models (`Hub`, `Link`, `Satellite`, `DVModel`). No LLM, no API key.
2. Run `CodeGeneratorAgent().run(state)` on a `VaultAgentState(dv_model=...)` (await it; it is
   async). This is the deterministic generator — same code path the pipeline uses.
3. Write each `state.artifacts.dbt_models[name]` to `models/raw_vault/<name>.sql`.
4. Print the generated metadata summary and any `state.errors` (there should be none for this
   model; an eff_sat with no driving key would flag — the model declares one).

Acceptance: running `uv run python demo/bank_postgres/build_vault_models.py` regenerates the six
`raw_vault/*.sql` files identically (idempotent), with no errors. Add a tiny test that imports the
builder, runs it to a temp dir, and asserts six models are produced and contain
`automate_dv.hub`/`link`/`sat`/`eff_sat` — keeps the demo from rotting if the generator changes.

---

## 6. Staging models [ENFORCE]

Hand-authored `automate_dv.stage()` models. They must output exactly the HK/HASHDIFF/technical
columns the generated vault models reference (§3). Seeds carry `LOAD_DATETIME` and `RECORD_SOURCE`
explicitly; staging passes them through (`include_source_columns=true`) and adds the hashes.

**`stg_customer`** (source: seed `raw_customer`)
- hashed_columns: `CUSTOMER_HK` ← `NATIONAL_CUSTOMER_ID`; `CUSTOMER_DETAILS_HASHDIFF` ← hashdiff of
  `[CUSTOMER_NAME, DATE_OF_BIRTH]`.
- carries through: `NATIONAL_CUSTOMER_ID, CUSTOMER_NAME, DATE_OF_BIRTH, LOAD_DATETIME, RECORD_SOURCE`.

**`stg_account`** (source: seed `raw_account`)
- hashed_columns: `ACCOUNT_HK` ← `ACCOUNT_NUMBER`; `ACCOUNT_DETAILS_HASHDIFF` ← hashdiff of `[BALANCE, STATUS]`.
- carries through: `ACCOUNT_NUMBER, BALANCE, STATUS, LOAD_DATETIME, RECORD_SOURCE`.

**`stg_account_customer`** (source: seed `raw_account_customer` — the ownership-over-time table)
- hashed_columns: `ACCOUNT_HK` ← `ACCOUNT_NUMBER`; `CUSTOMER_HK` ← `NATIONAL_CUSTOMER_ID`;
  `LINK_ACCOUNT_CUSTOMER_HK` ← `[ACCOUNT_NUMBER, NATIONAL_CUSTOMER_ID]`.
- carries through: `EFFECTIVE_FROM, EFFECTIVE_TO, LOAD_DATETIME, RECORD_SOURCE` (eff_sat needs the dates).

Example shape (AutomateDV v0.11 stage macro):

```sql
-- models/staging/stg_customer.sql
{{ config(materialized='view') }}
{%- set yaml_metadata -%}
source_model: 'raw_customer'
hashed_columns:
  CUSTOMER_HK: 'NATIONAL_CUSTOMER_ID'
  CUSTOMER_DETAILS_HASHDIFF:
    is_hashdiff: true
    columns:
      - 'CUSTOMER_NAME'
      - 'DATE_OF_BIRTH'
{%- endset -%}
{% set metadata_dict = fromyaml(yaml_metadata) %}
{{ automate_dv.stage(include_source_columns=true,
                     source_model=metadata_dict['source_model'],
                     derived_columns=none,
                     hashed_columns=metadata_dict['hashed_columns'],
                     ranked_columns=none) }}
```

(`source_model='raw_customer'` resolves the seed via `ref()`.)

---

## 7. Seeds (toy data) [GUIDE]

Small, deterministic CSVs that demonstrate history (so the satellites and eff_sat have something
to track). Suggested minimum: 3 customers, 3–4 accounts, and an ownership transfer (one account
changes owner → two rows in `raw_account_customer` with different `EFFECTIVE_FROM/TO`).

Columns (header names drive the staging references — keep them exactly):
- `raw_customer.csv`: `NATIONAL_CUSTOMER_ID, BANK_CUSTOMER_REFERENCE, CUSTOMER_NAME, DATE_OF_BIRTH, LOAD_DATETIME, RECORD_SOURCE`
- `raw_account.csv`: `ACCOUNT_NUMBER, BALANCE, STATUS, LOAD_DATETIME, RECORD_SOURCE`
- `raw_account_customer.csv`: `ACCOUNT_NUMBER, NATIONAL_CUSTOMER_ID, EFFECTIVE_FROM, EFFECTIVE_TO, LOAD_DATETIME, RECORD_SOURCE`

Use `LOAD_DATETIME` as a timestamp (e.g. `2026-01-01 00:00:00`) and `RECORD_SOURCE` as a short
literal (e.g. `BANK.CORE`). Configure seed column types in `dbt_project.yml` where Postgres would
otherwise guess wrong (dates/timestamps).

---

## 8. Runbook & verification [ENFORCE]

The demo `README.md` documents these steps; the implementer must actually run them and confirm green:

```bash
cd demo/bank_postgres
docker compose up -d                      # postgres:16 on localhost:5432
uv sync --extra demo                      # dbt-core + dbt-postgres
uv run python build_vault_models.py       # regenerate models/raw_vault/*.sql from the generator
uv run dbt deps                           # pull AutomateDV
uv run dbt seed                           # load raw_* CSVs
uv run dbt run                            # build staging + raw vault
uv run dbt test                           # AutomateDV/dbt tests (add not_null/unique on hub HKs)
```

**Acceptance criteria:**
- `dbt seed`, `dbt run`, `dbt test` all exit 0 (equivalently `dbt build`).
- Every hub, the link, and every satellite table exists and has > 0 rows.
- The eff_sat (if Phase B lands) end-dates the transferred account's first owner row.
- A verification query (ship it as `analyses/verify_vault.sql` or in the README) selects row
  counts per vault table and the ownership history for the transferred account.
- Re-running `dbt run` is idempotent (incremental models add no duplicate rows on a second run
  with unchanged seeds).

**Postgres friction points to expect and resolve (don't be surprised):**
1. **Identifier case.** The generator emits UPPER_SNAKE names; Postgres folds unquoted identifiers
   to lowercase. Confirm AutomateDV's Postgres adapter quoting makes `CUSTOMER_HK` etc. resolve;
   if not, align seed header case / set `quote_columns` consistently. This is the single most
   likely failure — budget time for it.
2. **eff_sat on incremental** — resolved (see §3 note update + eff-sat-incremental-fix-spec.md):
   needed `src_eff` ≠ `src_start_date` and `is_auto_end_dating=true` in the generated config.
3. **Hash NULL handling** — AutomateDV has documented NULL-handling behaviour; seed non-null keys.

---

## 9. Known limitations surfaced (track as findings / follow-ups)

These are **valuable outputs** of the PoC — capture them in the demo README and, where they imply
a product change, as draft ADRs:

- **Staging layer is not generated.** The code generator emits raw-vault models but not the
  `stg_*` models AutomateDV needs (hash key/hashdiff computation). Candidate next feature: a
  staging generator (the generator already knows every HK/HASHDIFF name and its source columns).
  This is the natural sequel to this PoC and the biggest single gap between "generates code" and
  "generates a runnable project".
- **Multi-active satellite grain.** The generator sets a satellite's `source_model` to
  `stg_<parent base>`, but multi-active data (e.g. customer addresses) has finer grain than the
  hub's staging. Deferred from the core model; revisit when the staging generator lands.
- **Self-referencing links.** A transaction links `account`↔`counterparty account` (same hub
  twice); `connected_hubs` as a list of hub names can't express two roles of one hub. Deferred;
  document as a modeling-capability gap.
- **Project scaffolding.** `dbt_project.yml`/`packages.yml`/`profiles.yml`/seeds are hand-authored
  here. A future "emit a runnable dbt project" mode would generate them too.
- **DuckDB.** Out of scope (unsupported by AutomateDV). If a zero-server demo is later wanted,
  evaluate a custom `duckdb__` dispatch shim mapping to AutomateDV's Postgres macros.

---

## 10. Docs to update [ENFORCE]

- `README.md`: change the "DuckDB (demo)" references to **Postgres**; in "Quick start" or a new
  "Run the generated vault" subsection, link `demo/bank_postgres/README.md`. Update the
  architecture diagram's "Targets" line (`Snowflake · MS Fabric · Postgres (demo)`).
- `CLAUDE.md`: in the tech-stack line, change "DuckDB for demo" to "Postgres for the local demo
  (AutomateDV does not support DuckDB)"; add a one-line current-milestone note when the PoC lands.
- `docs/demos/README.md`: add a row pointing at the runnable Postgres Durchstich.

---

## Rollout order

1. **Scaffolding + Phase A (core):** demo dir, `docker-compose.yml`, `pyproject.toml` `demo`
   extra, `build_vault_models.py`, `packages.yml`, `dbt_project.yml`, `profiles.yml`, seeds,
   `stg_customer`/`stg_account`, `hub_customer`/`hub_account`/`sat_customer_details`/
   `sat_account_details`. Goal: `dbt seed && dbt run && dbt test` green for **two hubs + two
   standard satellites**. ← the minimum publishable Durchstich.
2. **Phase A+ (link):** add `stg_account_customer` + `link_account_customer`; green.
3. **Phase B (eff_sat):** add `sat_account_customer_eff`; green, or record the finding (§3 note).
4. **Docs:** README/CLAUDE.md/demos updates (§10) + demo `README.md` runbook + verification query.
5. **Guardrail test:** the `build_vault_models.py` smoke test (§5).
6. **Findings:** write up §9 in the demo README; open draft ADR for the staging generator if you
   want to pursue it next.

After each phase: `dbt build` green, and `ruff`/`mypy`/`pytest` green for any Python.

## Traceability

| Item | Spec section | New ADR? |
|---|---|---|
| Postgres over DuckDB | §0, §1 | optional (records the platform decision) — recommended |
| Fixed bank model via real generator | §3, §5 | no |
| Staging generator (future) | §9 | **yes, when pursued** |
| README/CLAUDE.md target change | §10 | no |
