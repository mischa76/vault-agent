---
type: backlog
status: proposed
updated: 2026-10-22
---

# Backlog candidates of October 2026, part 2 — the owner's build of the whole vault, and the maturity analysis

Status: **Proposed, not prioritised** (2026-10-22) · Owner: Mischa Eismann · Author: Claude.
Continues `backlog-2026-10-candidates.md` (C1–C7, append-only). Two sources: the owner's own build of all
five AdventureWorks domains into PostgreSQL (2026-10-19 → 22; C8–C13 were first recorded in `docs/log.md`
the same days and are gathered here), and the owner's maturity analysis
`docs/handover/261022_vault-agent_Reifegradanalyse.pdf` (2026-10-22, judged on `main` at `d18b8d7`; C14–C21).
Each entry needs its own go; nothing here is built.

Every claim taken from the analysis was checked against the repo on 2026-10-22 unless marked
**(from the analysis, not re-measured)**.

## From the owner's build (C8–C13)

### C8 — Stale flags from earlier attempts reach the sign-off

Flags raised for a construct in one modeler attempt survive a re-model whose final shape no longer earns
them: the person run's code-generator flags, HR's „multi_active on multi-source hub not supported" next to a
generated satellite, Purchasing's `model_merger` „re-states existing link" for a link new in that run. The
review queue then asks a human about something that is not there. Candidate: scope flags to the attempt that
produced the final model, or re-derive generator and merger flags from the final model.

### C9 — Owner format at sign-off

A bare email disables accept; the reason is only a tooltip. „Record without accepting" then finishes the run
when nothing blocks — owners stored as name = email, email null, mappings left `proposed`. Candidate: an
inline message under the field; parse a bare email into `Name <email>` with the local part as name, or
accept it as email only.

### C10 — Seed config in grounded runs

A grounded run's `dbt_project.yml` carries `seeds:` column types for the increment's tables although staging
reads `source()`; every build warns of unused paths (7, 26, 6, 20 in the owner's steps). Candidate: emit the
seed block only for relations staged from seeds.

### C11 — A feed-bound multi-active satellite is generated as a standard satellite

`code_generator.py`'s ADR-0011 branch (a satellite naming one feed of a multi-source hub) calls `_render_sat`
whatever `sat_type`; `_render_ma_sat` is never reached and no gate names the lost child-dependent key. Three
satellites in the owner's vault: `sat_business_entity_pay_history` (`RateChangeDate`; +26, +35, +38, +38 rows
on re-runs), `sat_business_entity_email` (harmless in this data), `sat_business_entity_sales_quota_history`
(`QuotaDate`). Every multi-active satellite on a single-source hub or a link is a correct, idempotent `ma_sat`.
Candidate: guard first, then dispatch on `sat_type` in that branch, or refuse it as a generation gap.

### C12 — Nullable link participants: the link drops the row, its satellite keeps it

AutomateDV drops a link row when any participant key is NULL. A link bundling optional participants loses
relationships, and its satellites orphan rows: `link_customer_business_entity` keeps 635 of 19 820 customers
(each has a person *or* a store); `link_product_assembly_component` 2 387 of 2 484, with 103 orphaned rows in
`sat_product_assembly_component_details`. AutomateDV 0.11.4 provides zero keys
(`macros/staging/null_columns.sql`: `required`/`optional`, `-1`/`-2`); the generator passes none. Candidate:
stage a nullable participant key as `optional` (a hub's own key as `required`), plus a ghost hub row.

### C13 — A satellite whose parent key does not cover a unique key of its relation

`sat_product_assembly_component_details` hangs off the (assembly, component, unit) link while
`BillOfMaterials`' unique key includes `StartDate`; 195 keys recur, the standard satellite re-inserts on every
run (+195, +339). A modelling choice, not the generator's. Candidate: a warning or gate from the catalogue —
the satellite's key columns must cover a declared unique key of its relation, else a child-dependent key or
an effectivity shape is required. Open: whether the catalogue carries alternate keys in a readable form
(`schema_extract.json` reads Microsoft's `AK_` indexes; `source_schema.yml` shows only the primary key).

## From the maturity analysis (C14–C21)

### C14 — Repo hygiene: the workbench's data is committed, the next run's is one `git add .` away

Checked: `.gitignore` has no `workbench` entry; tracked are 36 files under `workbench/myproject/` and 95 under
`workbench-demo$/` (a `$` in the directory name); `workbench/adventureworks/` (the owner's whole build) is
untracked and would be committed by the next `git add .`. Candidate: remove both trees from the index, ignore
`workbench/` and `workbench-demo*/`, and point the quick start and the wiki's demo guide (`--root
workbench-demo` inside the repo) at a root outside the repo. Already-pushed history keeps the files — whether
that matters (no customer data so far) is the owner's call.

### C15 — Release 0.10.0

Checked: the last tag is `0.9.1`, `pyproject.toml` says `0.9.1`, 299 commits since (WP11–WP80 sit under
`[Unreleased]`). Candidate: cut 0.10.0 through the release workflow.

### C16 — Documentation drift

Checked: README's roadmap ends at WP10 with „Polish — next"; README says 33 `E_` gates where the validator has
35 (`rg -o '"E_[A-Z_]+"' src/vault_agent/agents/validator.py | sort -u`); README calls Databricks
„keyless-only so far, no workspace build recorded" although WP72 built on Databricks (2026-10-16/17);
`docs/reference-architecture.md` was last re-derived 2026-08-14 and still says „no data profiling"; ADR-0004,
-0005 and -0007 are `Proposed` in file and index although built. Candidate: README and reference architecture
re-derived from the code; the three ADRs' acceptance recorded by log entry and index (the ADR files stay
unchanged, records are append-only); the wiki page `vault-agent.md` brought up to date (it feeds CV and
positioning).

### C17 — A second real domain

The domain evidence rests on AdventureWorks alone. Candidate: run and build a landscape that is not
AdventureWorks, ideally bank- or insurance-like (the target market), with requirements written independently
of the schema, as WP30 did for AdventureWorks. Related, already open: semantic scale above ~30 tables
(`scale-test-findings.md`, candidate #5; `scale_300` never run).

### C18 — Close the inferred link stages

The owner's build needed seven hand-made views for link stages no rule could bind (reason `none`: a
participant's column carries no declared foreign key, e.g. `WorkOrderRouting.ProductID`), and the twenty-first
chain left eight stages inferred. `resume --map` binds hub stages only (`source_overrides`); link stages bind
from ratified proposals and offers (`link_source_overrides`) — neither the CLI nor the workbench can set one
after the fact. Candidate, two halves: a binding field for link stages at sign-off in both CLI and workbench
(extends C4), and an offer tier that may count a participant's column when it is part of the relation's
primary key.

### C19 — Workbench tests through the API, console coverage

WP78's relative-path defect passed every test because none went through the API (fixed 2026-10-21).
**(from the analysis, not re-measured:** `ui/console.py` 70 %, `ui/app.py` 79 % line coverage.) Candidate:
API-level tests for every workbench action that hands paths to a subprocess or the filesystem, and a coverage
floor for `ui/`.

### C20 — Positioning: the consultant's single-user tool, or a team tool (ADR)

Today the workbench binds to 127.0.0.1, has no authentication, and checkpoints in SQLite per run. Both
answers are coherent; they lead to different work (auth, a shared checkpointer, multi-user state vs. none).
Candidate: an ADR that decides before any pilot.

### C21 — Snowflake dialect and build

Snowflake is a strategic target (CLAUDE.md); only PostgreSQL and Databricks are verified by real builds.
Candidate: a Snowflake platform profile and one recorded build of a chain step, as WP72 did for Databricks.

## Not taken up as candidates

- **C1's ADR** (source-driven mode) — the analysis recommends deciding it before a pilot; it is already C1.
- **The evaluator walk-through** (the analysis: a guide exists, no result is recorded anywhere) — an activity
  for the owner, not a work package; its outcome belongs in the log.
- **Business Vault PIT/Bridge** — the analysis lists it as the one „Generate"-class gap; ADR-0007 keeps
  Business Vault logic human-ratified, so it stays out until the owner revisits that ADR.

## C10 — closed by WP107 (2026-10-31)

`dbt_project.yml` carries a `seeds:` block, and WP7 §7.3's seed column types, only for stages that read a seed — a bare
name no `source()` block and not WP76's `inferred` block declares. A grounded project reading sources alone has no
`seeds:` key; the seed world (ungrounded runs, the bank demos) is byte-identical. Measured keyless: the twenty-third
chain's fifth project builds with zero warnings (one before), PASS=421 of 421; the demo's Sales step types none of the
17 relations it reads through `source()`. Spec `backlog-2026-07/wp107-seed-block-only-for-seeds-spec.md`.
