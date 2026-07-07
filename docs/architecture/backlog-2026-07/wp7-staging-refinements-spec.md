# WP7 — Staging refinements: ma_sat grain, bound source() refs, seed column types

Status: Proposed · Size: M · Depends on: staging generator (landed 2026-07-06)

Three follow-ups the staging generator deliberately deferred (CLAUDE.md milestone note;
poc-end-to-end-dbt-spec §9). All deterministic.

## 7.1 Multi-active satellite staging grain

*Problem:* a ma_sat's data (e.g. customer addresses) has finer grain than its parent hub's
staging source; today the ma_sat reads `stg_<parent base>`, which is wrong whenever the
multi-active rows live in their own raw table (the usual case).

*Design:*

- `state.Satellite` gains `source_table: str | None = None` — "the raw relation this
  satellite's rows come from, when it differs from its parent's" (docstring per the house
  style; the modeler may fill it, grounding steers it to declared tables).
- `staging_generator.collect_staging_specs`: a satellite with `source_table` set gets its
  **own** staging spec named `stg_<normalize(base_name(sat.name))>` containing: the parent
  hub's HK (hashed from the parent hub's BK — the BK column must exist in the finer-grain
  table; that is what makes it attachable), the sat's hashdiff, cdk + attrs as source
  columns. `bind_sources` binds it against `source_table` verbatim (declared) — no
  inference, no flag.
- `code_generator._render_ma_sat`/`_render_sat`: `source_model` = the sat's own staging
  name when `source_table` is set, else parent staging (today's behaviour).
- Validator: new **warning** `W_MASAT_SHARED_GRAIN` when a `multi_active` satellite has
  **no** `source_table` — "multi-active rows usually come from their own source relation;
  sharing the parent's staging assumes equal grain — declare source_table or confirm".
- Modeler prompt [GUIDE] line + tool schema pick the field up automatically
  (schema derives from the pydantic model — verify `Satellite.model_json_schema()` output
  includes it).

## 7.2 Bound `source()` references (grounded runs)

*Problem:* staging references raw inputs by bare relation name; `sources.yml` is
documentation only. On a grounded run we know the declared tables and can bind properly.

*Design (activation rule: only when `state.source_schemas` is non-empty):*

- `state.SourceTable` gains `schema_name: str | None = None` and
  `database: str | None = None` (loader `source_schema.py` accepts optional `schema:` /
  `database:` keys per table entry; alias `schema` → `schema_name` to dodge the BaseModel
  attribute; extend loader validation + tests).
- For staging specs whose binding matched a declared table (`spec.bound`):
  `source_model:` in the rendered yaml_metadata becomes the AutomateDV mapping form
  `source_model:\n  raw: '<table>'`, and `sources.yml` declares source `raw` with
  `schema:`/`database:` from the first declared values (mixed schemas across tables →
  one source block per distinct schema, names `raw`, `raw_2`, …; keep it deterministic
  and tested).
- Unbound (inferred) specs keep bare names + `SOURCE_BINDING` flag — unchanged.
- Ungrounded runs: byte-identical output to today (regression guard test, mirroring the
  grounding no-regression pattern).

## 7.3 Seed column types from contracts

*Problem:* generated projects rely on dbt seed type inference (worked in the hardness
test, but fragile for e.g. all-numeric business keys, leading zeros).

*Design:* `staging_generator.build_staging` gains an optional `contracts` parameter
(`list[dict]`, `state.artifacts.contracts` — the data-contract agent runs *before* the
code generator in the graph, so they are available; pass them through from
`CodeGeneratorAgent.run`). For every staging spec whose `source_model` matches a contract
`name` (normalised): map contract field types to dbt/Postgres-safe seed types
(`string→varchar`, `integer→bigint`, `number→numeric`, `boolean→boolean`,
`string+format=date→date`, `…date-time→timestamp`, unions take the non-null member,
`unknown` → omit the column) and emit into the generated `dbt_project.yml` under
`seeds.<PROJECT_NAME>.<source_model>.+column_types`. `LOAD_DATETIME`/`RECORD_SOURCE`
always `timestamp`/`varchar`. No contract match → no column_types (inference, as today).

## Tests

Per sub-item in `tests/test_agents/test_staging_generator.py` (+ `test_validator.py` for
`W_MASAT_SHARED_GRAIN`, `test_source_schema.py` for the loader fields): ma_sat with/without
`source_table`; grounded mapping-form rendering incl. multi-schema sources.yml; ungrounded
byte-identity; contract-driven column_types incl. `unknown`-omission.

## Acceptance criteria

1. A ma_sat with `source_table` builds against its own staging model; without it the
   validator warns `W_MASAT_SHARED_GRAIN`.
2. Grounded runs emit `source()`-bound staging + a real sources.yml; ungrounded output is
   byte-identical to before this WP.
3. Contract-typed seeds appear in dbt_project.yml exactly per the mapping table.
4. Bank demo guardrails green (ungrounded → unchanged). Standard DoD. Re-verify the
   Postgres hardness test (fresh output, `dbt build`) once after landing — record the
   result in CLAUDE.md.
