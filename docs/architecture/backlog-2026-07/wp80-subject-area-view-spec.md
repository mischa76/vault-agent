---
type: spec
status: not-measured
updated: 2026-10-18
---

# WP80 — The Model perspective shows the vault by subject area: one diagram per source schema, with the neighbouring hubs it reaches into, derived from what each construct reads

Status: **Approved and in progress** (2026-10-18, user: „ok, bau die Fachgebiets-Sicht in der
Workbench als WP80“) · Owner: Mischa Eismann · Author: Claude. From the DBeaver session of
2026-10-18 on the twenty-first chain's PostgreSQL build: one ER diagram of 340 relations is
unreadable, and the readable cut turned out to be the five AdventureWorks schemas — the owner's
observation „vermutlich muss man diagramme nach subject areas aufgliedern“. The workbench
already holds the whole model as one Mermaid graph (14.4); it gains the same cut, computed, not
drawn by hand.

## 1 What is missing, in one paragraph

The Model perspective renders `build_model_mermaid(model)`: every hub, link and satellite of the
run in one `flowchart`. For the bank demo that is a dozen nodes; for the twenty-first chain's
fifth step it is 185 constructs plus 11 feed cylinders, and a reader looking for „Sales“ finds
nothing to hold on to. The model carries no subject-area field, and it needs none: a construct's
subject area is **the schema of the relation its stage reads** — a hub's bound relation, a
link's bound relation, a satellite's own `source_table` or its parent's relation, a multi-source
hub's feeds. That is what the staging generator decided already (`bind_sources`, WP7/WP77), and
what the catalogue carries for every earlier increment (WP74). The partition into schemas is
therefore a reading of the generated project, as the Project section (WP78) is — no model call,
no new decision, nothing a human has to maintain.

## 2 The rules

1. **A construct's subject areas are the schemas of the relations it reads.** `subject_areas`
   (`src/vault_agent/subject_areas.py`) takes the model, the declared tables (the increment's
   `source_schemas` and the catalogue's `carried_schemas`) and the staging metadata when the
   project is generated (`automatedv_yaml["staging"]`: `source_model`, `source_binding`), else
   recomputes the bindings as the generator does (`collect_staging_specs` + `bind_sources`, with
   the carried bindings). A single-source hub, a link, and a satellite with its own stage read
   one relation each; a multi-source hub is a member of every area one of its feeds lives in; a
   satellite names a feed (`satellite_feed`) and follows it, or has no `source_table` and follows
   its parent's areas. A relation whose schema is `None` lands in the area **`(no schema)`**
   (the seed world: one area, the whole model). A construct whose stage is inferred — no
   declared relation — lands in **`(unbound)`**: exactly the stages the Project section lists
   under „to provide“, seen as a diagram. Area names are schema names, ordered alphabetically,
   the two bracketed areas last; an area knows whether it is **the increment's** (one of its
   relations is in `source_schemas`).
2. **Neighbours make the diagram whole.** An area's diagram shows its members and, dashed, the
   **neighbours**: hubs a member link participates in, and the parent of a member satellite,
   that belong to another area. Without them the link edges the owner missed in DBeaver would
   be missing here too. A neighbour renders as its node only — no feeds, no satellites, no
   edges of its own.
3. **One Mermaid builder.** `build_model_mermaid(model, members=…, neighbours=…)` renders the
   subset; without a scope it renders exactly what it rendered before (the report's fixture
   pin, `tests/fixtures/report/report_fixture.html`, is the guard). Edges are emitted only
   when both ends are in the diagram; the `neighbour` class is declared only when a scope is
   given.
4. **The API carries the areas.** `GET /api/runs/{id}/model` gains `areas`: a list of `{name,
   increment, hubs, links, satellites, neighbours, mermaid}`, member names sorted as the model
   lists them. The whole-model `output_mermaid` stays.
5. **Shown on the Model perspective** as a strip above the output diagram: „whole model“ and
   one button per area with its member count (the increment's area marked). Selecting an area
   swaps the diagram for the area's and narrows the inventory to its members, neighbours
   tagged. With a single area the strip is not shown (nothing to choose). The console gains
   nothing; chapter 14 gains 14.8.
6. **Not a model statement.** A subject area is a view of what the project reads, never a
   field on a construct, never a flag, never a gate. Changing a binding at the checkpoint moves
   a construct between areas; nothing else does.

## 3 Guards before the change

1. `subject_areas` on a three-table fixture in two schemas (`crm.Customer`; `fin.Account`,
   `fin.AccountCustomer`) with `hub_customer`, `hub_account`, `link_account_customer`,
   `sat_customer_details` (parent's stage), `sat_account_details`, and a never-bound
   `link_customer_region`: areas `crm` (hub, satellite; no neighbours), `fin` (hub, link,
   satellite; neighbour `hub_customer`), `(unbound)` (the link; neighbour `hub_customer`), in
   that order; the same answer from the staging metadata and from the recomputation; the
   `(no schema)` area alone when the tables declare no schema.
2. A multi-source hub fed from `crm` and `fin` is a member of both; a satellite naming the
   `fin` feed is in `fin` only; a satellite without `source_table` on it is in both.
3. `build_model_mermaid(model, members=…, neighbours=…)` for `fin`: contains the member nodes
   and `HUB_CUSTOMER` with `class HUB_CUSTOMER neighbour;`, the link's two edges, and neither
   `sat_customer_details` nor an edge to it; `build_model_mermaid(model)` unchanged (the report
   fixture pin, existing).
4. The API: the stub run's model response carries `areas` whose members cover every construct
   of the model, each area with `mermaid` starting with `flowchart`.
5. The frontend: the Model perspective renders the strip from a view with two areas, the
   whole-model diagram first; clicking an area shows that area's diagram title, narrows the
   inventory and tags the neighbour; a view with one area shows no strip.

## 4 Pre-registration

The twenty-first chain's kept fifth project (model, catalogue and staging metadata as written),
read with the same rule by hand before the change (`scratchpad/areas_prereg.py`):

| area | hubs | links | satellites | neighbours | in the diagram |
|---|---|---|---|---|---|
| HumanResources | 4 | 2 | 10 | 0 | 16 |
| Person | 7 | 4 | 17 | 0 | 28 |
| Production | 15 | 14 | 31 | 2 | 62 |
| Purchasing | 4 | 4 | 8 | 2 | 18 |
| Sales (increment) | 12 | 17 | 24 | 6 | 59 |
| (unbound) | 1 | 8 | 1 | 8 | 18 |

`hub_business_entity` is a member of Person, HumanResources, Purchasing and Sales (eleven feeds
in four schemas) — the integration hub by construction. `(unbound)` holds
`hub_work_order_operation`, the seven never-bound links and the effectivity satellite of one of
them: the eight inferred stages the PostgreSQL build failed on (2026-10-18), as a picture. The
hand count from the step outputs (2026-10-18, `vault21_subject_areas.md`: 28/16/61/18/58)
differs where the increment attribution and the schema attribution differ — the multi-source
hub counted as a neighbour there, and the unbound constructs counted with their step.

## 5 Not in this WP

A subject area as a model field or as an input the modeler reads (the schema is the source
system's statement, the model has no second one); a per-area ER diagram in the report
(`report.py` keeps the whole-model graph; the workbench is where a reader chooses); grouping the
inventory by area when the whole model is selected; a diagram of the physical build (DBeaver's
job).

## 6 Results

*(appended after the change)*
