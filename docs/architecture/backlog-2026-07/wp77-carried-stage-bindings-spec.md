---
type: spec
status: not-measured
updated: 2026-10-17
---

# WP77 — A stage's binding travels with the model: the catalogue carries every declared binding, and a later increment keeps it unless its own resolution says otherwise

Status: **Approved and in progress** (2026-10-17, user: „nein, wir machen jetzt weiter bis der
Fehler ausgeräumt ist“) · Owner: Mischa Eismann · Author: Claude. From the twentieth chain's
whole-vault build (`docs/log.md`, 2026-10-17): of its 34 inferred-bound stages, 24 had been
bound to a declared table in an earlier step and lost that binding in a later one. No prompt
change; the suite stays keyless.

## 1 The defect, in one paragraph

WP74 carried the *tables* (`carried_schemas`), so a stage whose construct name matches a
declared table binds again in every later step. But most link stages and some hub stages are
bound by *resolution*, not by name: the offer tier (`resolve_link_relation`, WP42), a ratified
proposal, a ratified mapping, the WP73-safe override — all of which read `state.source_schemas`
(this increment's tables, with their foreign keys) and this increment's proposals. In the next
step those tables are only in the catalogue, which carries no foreign keys and no proposals, so
the resolution finds nothing and the stage falls to `raw_<base>`. Measured on the twentieth
chain: inferred 0 / 4 / 9 / 21 / 34 per step, of which 4 / 2 / 12 / 6 were bound the step before
(`stg_address_state_province` bound in step 1, inferred from step 2 on; `hub_purchase_order`
from `PurchaseOrderHeader`, bound in step 4, inferred in step 5). Ten of the 34 were never
bound: six `ambiguous` (a human's decision) and four `none`.

## 2 The rules

1. **The binding is what travels.** `dump_source_catalogue(tables, bindings)` writes a second
   section, `stage_bindings: {<stage model>: <relation>}` — every staging model whose final
   binding is declared (`source_binding: declared` in the staging metadata), keyed by stage name
   and valued by the relation as declared, translations included (the relation, not the view).
   `rules`-free: `existing_model.stage_bindings(staging_metadata)` reads it from
   `artifacts.automatedv_yaml["staging"]`, after the mapper's re-bind, so a binding a human
   ratified travels too. `load_carried_bindings(path)` reads it back (`{}` when absent — an
   older output keeps working, degraded as before).
2. **A typed field, staging only.** `VaultAgentState.carried_bindings: dict[str, str]`,
   loaded wherever `carried_schemas` is (`run --existing`, the workbench, the harness between
   steps and for a case's `existing`), passed by the code generator and the mapper's re-bind
   into `build_staging(..., carried_bindings=)` → `bind_sources`. Nothing else reads it.
3. **Precedence.** For a stage not bound at collection time: this run's override (a ratified
   mapping, a ratified proposal, the offer) first; then the carried binding, applied only when
   the relation is among the binding schemas (increment plus catalogue) and passes WP73's
   column check (`_rejected` — a refused carried binding is flagged `binding_rejected` and
   the stage reads `raw_<base>`, as for an override); then the name match; then inferred.
   A carried binding raises no flag: it was reviewed when it was made.
4. **Transitive.** A step writes every declared binding it has, including the ones it kept
   from the catalogue, so step 5 carries steps 1 to 4.

## 3 Guards before the change

1. `dump_source_catalogue` with bindings renders `stage_bindings`; `load_carried_bindings`
   reads them from the directory and the model-file path, `{}` from an output without them.
2. `stage_bindings(metadata)` returns the declared stages' relations (mapping form and bare),
   skips inferred ones.
3. `build_staging` on a two-step fixture whose step-1 hub `hub_purchase_order` is built from
   `PurchaseOrderHeader` (bound by override in step 1): step 2 without `carried_bindings`
   infers `stg_purchase_order` (today); with the carried binding it binds to
   `PurchaseOrderHeader` in its block with no `SOURCE_BINDING` flag; a carried binding to a
   relation lacking a hashed column is refused with `binding_rejected`; a this-run override
   to another relation wins over the carried binding.
4. `write_outputs` writes `stage_bindings` from the staging metadata and the loader reads
   them; `write_step_vault` the same; `VaultAgentState` carries the field and the CLI
   pipeline passes it.

## 4 Pre-registration

The twentieth chain's kept five projects replayed keylessly in order, each step's declared
bindings carried into the next: the fifth project's inferred stages fall from 34 to the ten
never bound (six `ambiguous`, four `none`), `unresolved_stage_refs` stays empty; rebuilt on
Databricks into fresh schemas, the build fails on at most those ten staging views and their
dependants, nothing else, and the hubs equal their sources' keys. The twenty-first chain:
`stage_refs_inferred` per step no longer grows by earlier steps' stages.

## 5 Not in this WP

The ten never-bound stages (a human's `--map` / review decision for `ambiguous`; a binder tier
for `none` only with its own reasoning); carrying proposals or foreign keys (the catalogue
stays binding-only).

## 6 Results

*(appended after the change)*
