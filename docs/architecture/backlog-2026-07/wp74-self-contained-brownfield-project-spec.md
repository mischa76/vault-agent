---
type: spec
status: not-measured
updated: 2026-10-17
---

# WP74 — A brownfield step's project is self-contained: the source catalogue travels with the model, and the harness checks that every stage resolves

Status: **Approved and in progress** (2026-10-17, the owner's go for WP74) · Owner: Mischa Eismann
· Author: Claude. From WP72 stage 3's first finding: the fifth step's project declared one
source block and degraded every earlier construct's staging to names dbt cannot resolve, so
the whole-vault project failed at parse. No prompt change; the suite stays keyless.

## 1 The defect, in one paragraph

A step's `source_schemas` are *this increment's* tables — the contract agent, the proposer and
the modeler's grounding depend on that (CLAUDE.md: handing a step the whole catalogue re-drafts
every contract). But staging is re-rendered for every construct on every run, existing ones
included, and `bind_sources` knows only the increment's tables: an existing construct's stage
finds no declared table, falls to `raw_<base>` (or keeps a satellite's `source_table` as a bare
name with no block), and the project references relations dbt cannot resolve. The previous
run knew the binding; nothing carried it.

## 2 The rules

1. **The catalogue travels with the model.** `write_outputs` writes
   `metadata/source_catalogue.yml` beside `dv_model.yml`: the declared tables this run bound
   to (its `source_schemas`) plus everything carried into it, with schema, database and the
   full declared columns, in the `source_schemas:` shape the house loader reads. Foreign keys
   are not carried — the catalogue is for binding, never for proposing.
2. **A typed split, not a wider `source_schemas`.** `--existing <dir>` loads the catalogue
   into a new state field, `carried_schemas`; `source_schemas` stays the increment's. The
   contract agent, the proposer, the resolver and the modeler's grounding never read
   `carried_schemas`; only staging does (and WP73's key check, which sees full columns).
3. **Staging binds against both.** `build_staging` binds specs and groups source blocks over
   `source_schemas + carried_schemas` (the increment's tables first on a name clash); an
   existing construct's stage therefore keeps its `source()` mapping and its block, and a
   satellite's `source_table` from an earlier increment gets its block too.
4. **The harness carries the catalogue as the CLI does.** `write_step_vault` writes it beside
   the step's model; `run_chain_once` loads it into the next step's `carried_schemas`, for a
   resumed step as well.
5. **„Green" learns to mean „resolvable".** A pure function, `unresolved_stage_refs(state)`,
   lists every staging model whose relation dbt could not resolve: a `source()` mapping whose
   block or table is missing from the generated `sources.yml`, or a bare name that is neither
   another staging model nor one of the project's declared blocks' tables. Inferred `raw_*`
   bindings are counted apart (they are disclosed, and a human maps them). The eval harness
   records both counts per step (`stage_refs_unresolved`, `stage_refs_inferred`) and scores
   `project_self_contained` = 1.0 when the first is 0 — gated at 1.0 for the chain case.

## 3 Guards before the change

1. `write_outputs` on a grounded state writes `metadata/source_catalogue.yml`; the house
   loader reads it back as the same tables with their columns and schema;
   `load_existing_catalogue(dir)` returns them and `[]` for an output written before WP74.
2. `build_staging(model2, schemas2, existing=model1, carried=schemas1)`: step 1's construct
   stages keep their `source()` mapping, `sources.yml` carries two blocks (step 1's schema
   and step 2's), a satellite with step 1's `source_table` renders in mapping form, and no
   stage of step 1 reads `raw_*`; without `carried` the same call degrades (today's state,
   kept as the contrast).
3. `cli.run --existing <dir>` on the stub pipeline populates `carried_schemas` from the dir's
   catalogue and leaves `source_schemas` the increment's; the catalogue the run writes carries
   both increments' tables.
4. `unresolved_stage_refs` on a state with a degraded project names the bare declared table
   and not the inferred `raw_*`; on a carried one returns nothing; the eval metric and score
   appear in a chain step's result, and the chain case gates `project_self_contained` at 1.0.

## 4 Pre-registration

Keyless replay: the Databricks chain's five step models with their schemas, run through
`build_staging` step by step with the catalogue carried — the fifth step's project lists five
source blocks and `unresolved_stage_refs` is empty (the inferred `raw_*` remain, disclosed).
Live: the nineteenth chain's five step results carry `stage_refs_unresolved` 0 and the score at
1.0, or the step and the stage are named.

## 5 Not in this WP

Building a step inside the eval harness with a warehouse (needs Postgres in the eval
environment; a separate decision); a better relation for inferred bindings.

## 6 Results

*(appended after the change)*

**2026-10-17 — built, keyless; replayed over the Databricks chain.** Guards `a4c72de` (red),
the change `eb60d02`, docs in the commit carrying this line. `metadata/source_catalogue.yml`
beside the model (`existing_model.dump_source_catalogue` / `load_existing_catalogue`, the
latter also from the model file's path, `[]` for an output written before today);
`VaultAgentState.carried_schemas`; `--existing` and the workbench load it; `build_staging`
binds and groups blocks over the increment's tables plus the carried ones (the increment's
first on a clash) — nothing else reads them; `write_step_vault` and `run_chain_once` persist
and carry it in the harness; `unresolved_stage_refs(models, sources_yml)`; the metrics
`stage_refs_unresolved` / `stage_refs_inferred` and the scorer `project_self_contained`, gated
at 1.0 on `adventureworks_incremental`. Six guards; 1220 tests, ruff, bare mypy. The guards'
one change to existing expectations: the bank scorer test's expected set gains the new
scorer at 1.0 (vacuous there). **§4 replay** (the five step models of the Databricks chain,
staging re-rendered step by step with the catalogue carried): source blocks 1 → 2 → 3 → 4 →
**5** (`Person`, `HumanResources`, `Production`, `Purchasing`, `Sales`), `unresolved_stage_refs`
**0 in every step**, inferred bindings 2 / 4 / 15 / 19 / 40 — the `source_binding` disclosures
that remain, a human's mapping, not the generator's loss. **Not measured:** the nineteenth
chain's live score; a dbt parse of the replayed fifth project (no warehouse here — the
resolution check is the keyless stand-in, as §5 says).
