---
type: spec
status: not-measured
updated: 2026-10-23
---

# WP91 — A point-in-time table per hub, generated as a bounded `table` in vault-agent's own SQL (ADR-0016 option B, first increment)

Status: **Approved and in progress** (2026-10-23, the owner's choice of option B on ADR-0016) · Owner: Mischa Eismann · Author:
Claude. Backlog C22 (`backlog-2026-10-candidates-3.md`); the trial `spike-pit-trial-results.md`; the decision
`adrs/ADR-0016-business-vault-pit-bridge.md`. Bridges are not this WP.

## 1 What is built, in one paragraph

Opt-in: a run with `--pit --as-of-start D1 --as-of-end D2 [--as-of-grain day|month]` (CLI) or the same fields on
the workbench's run start emits, beside the raw vault, a Business Vault folder `models/business_vault/` with one
as-of spine `as_of_dates` and one `pit_<hub base>` per hub that has **two or more descriptive satellites** (standard
or multi-active, parent = the hub; effectivity satellites and link satellites are not a hub's descriptive payload).
A PIT row is (hub hash key, `AS_OF_DATE`, and per satellite `<SAT>_PK`, `<SAT>_LDTS`: the satellite's latest load at
or before the as-of date). Without `--pit` every artifact is byte-identical to today.

## 2 The rules

1. **Ghost entries are AutomateDV's ghost records.** A missing satellite row becomes AutomateDV's own ghost values —
   `{{ automate_dv.binary_ghost(none, var('hash', 'MD5')) }}` for the key, `{{ automate_dv.date_ghost(date_type=
   'timestamp') }}` for the load date — and the project turns `enable_ghost_records: true` on, so every **standard**
   satellite carries the matching ghost row and a PIT→satellite join on (key, load date) finds a row for every entry.
   Decided over WP86's `-2` hub key because the satellites have no row for it; decided over the deprecated macro's
   literal because that literal is the same value spelled by hand. AutomateDV has no ghost record for a
   multi-active satellite (`ma_sat.sql`, 0.11.4): a PIT entry of such a satellite that is a ghost joins nothing —
   stated in the model's header and in the operations manual; a consumer joins those LEFT.
2. **The spine is `dbt_utils.date_spine`** over the operator's bounds (`as_of_start` inclusive, `as_of_end`
   exclusive, as dbt_utils defines it) and grain; both bounds are required when `pit` is on — a PIT without a bound
   is a cross join without a limit, and nothing in the inputs says what the limit should be. `dbt_utils` is declared
   in `packages.yml` (1.4.1, the version AutomateDV 0.11.4 already resolves) only when PIT is on.
3. **The SQL is the trial's variant B**, per satellite one grouped LEFT JOIN on `key = key AND ldts <= AS_OF_DATE`
   with `MAX(ldts)`; no hex round trips, no `DISTINCT`. Materialised `table` (model config and a
   `business_vault: +materialized: table` block in `dbt_project.yml`). Columns: the hub's hash key as the raw vault
   names it, `AS_OF_DATE`, then `<SAT_NAME_UPPER>_PK`, `<SAT_NAME_UPPER>_LDTS` per satellite in model order.
4. **Where it lives.** `agents/business_vault_generator.py`, deterministic, no prompt, reading the model and the
   raw-vault metadata the code generator just produced (`src_pk`, `src_ldts` per satellite and hub — the one
   place those names are decided). Called from `CodeGeneratorAgent.run` after the staging pass; the mapper's re-bind
   does not touch it (a PIT depends on no binding). Output: `state.artifacts.business_vault_models`, metadata block
   `automatedv.yml['pit']`, files under `models/business_vault/` (`write_outputs`), listed in the report's paths.
5. **A human sees it as a disclosure.** One `PIT_GENERATED` flag per PIT (kind, role `disclosure`, grouped), naming
   the hub and its satellites — ADR-0007's reading: a PIT is deterministic from the model, nothing to decide; the
   operator deselects by not asking for PITs (per-hub selection is a later increment).
6. **State.** `VaultAgentState.business_vault: BusinessVaultOptions` (`pit`, `as_of_start`, `as_of_end`,
   `as_of_grain`), persisted with the checkpoint so a resume keeps it; the workbench's `run.json` records the CLI
   equivalent with the flags.
7. **Not in this WP.** Bridges; an incremental PIT; per-hub selection; PIT over link satellites; ghost rows for
   multi-active satellites; Databricks verification (keyless rendering is platform-neutral, the build is a separate
   recorded activity as WP72's).

## 3 Acceptance (keyless)

`tests/test_wp91_pit.py`: options default off and `pit` without bounds refused; eligibility (two or more descriptive
satellites; link and effectivity satellites excluded); the rendered PIT reads the hub, the satellites and the spine
with AutomateDV's ghost helpers; the spine over the bounds; scaffolding gains the ghost var, the block and `dbt_utils`
only when PIT is on and is byte-identical otherwise; the code generator emits models, metadata and one disclosure per
PIT; `write_outputs` places them; the CLI refuses `--pit` without bounds; the workbench's start body carries the fields.
The existing byte-identity guards carry inertness.

## 4 Pre-registration (keyless `dbt build` on PostgreSQL)

The owner's Sales run regenerated as for the fourth `aw` rebuild (WP85 remedies, WP89, WP90 — the three hand views)
with `pit` on, `as_of_start 2026-10-15`, `as_of_end 2026-10-26`, grain day, built twice into a fresh schema `aw_wp91`:

- **P1** 13 PIT models (the hubs with two or more descriptive satellites in that vault, counted from its metadata
  today) and `as_of_dates`; **PASS = 407 + 14 = 421** both builds, nothing failing; second build 180 of 180
  incremental models `INSERT 0 0` (the ghost rows arrive in the first build).
- **P2** `pit_sales_order` has 346 115 rows and, row for row, the load dates of the trial's variant B; every entry of
  a standard satellite joins **exactly one** satellite row on (`_PK`, `_LDTS`), ghost entries included — 0 unjoined
  over all 13 PITs' standard satellites.
- **P3** every standard satellite holds exactly one row more than in `aw` (the ghost, `RECORD_SOURCE =
  'AUTOMATE_DV_SYSTEM'`); multi-active and effectivity satellites and every hub and link equal `aw`.
- **P4** the ghost entries of multi-active satellites join nothing (rule 1), and those are the only unjoined entries.

Not predicted: wall time; the PITs' sizes; which hubs beyond the 13 the chain's vaults would give.
