---
type: spec
status: not-measured
updated: 2026-11-16
---

# WP136 — A link that takes a hub no declared key leads to: an accepted inferred key is read, the hub's own table binds its stage, the missing key is named (C64)

Status: **Approved and in progress** (2026-11-16, on the owner's go of that day: fix C64) · Owner: Mischa
Eismann · Author: Claude. Candidate C64. **The candidate named two possible causes and two options; the trace
found neither cause, and neither option would have repaired the case** (§1). What is built is the part that
follows from decisions already taken (ADR-0018, WP42, WP85); the part that would be a new modelling decision is
not built and is laid before the owner (§4, C74).

## 1 What is wrong — traced at zero cost on the stored runs

C64 (2026-11-14) asked why the binder offered `WorkOrderRouting` nothing: the freely chosen link name, or the
composite hub in a link with a translation. Neither. Read from the three chains that carry the shape (the
twenty-sixth, and both of 2026-11-15):

1. **The catalogue declares no key for the participation.** `WorkOrderRouting` carries `ProductID` — it is part
   of its primary key — and declares two foreign keys, to `WorkOrder` and to `Location`. None to `Product`
   (Microsoft's schema has none). The modeler takes `hub_product` into the link all the same: an operation is
   „for a product". The relation therefore offers three of the link's four hubs (WP42), no relation offers all
   four, the link is bound to nothing (`none`), and no licence exists that would translate `ProductID` into the
   hub's key (`ProductNumber` since WP125). The licence for `LocationID` exists and is not applied either: the
   key repair repairs a link on the relation it reads, and this link reads none.
   **Measured on the 36 stored chain models** (fifth steps, the full catalogue): 54 of 1 955 links are offered by
   no relation; 36 of them — one in every chain — are this one, a link over `WorkOrderRouting` with
   `hub_product` (under eight names). On the surrogate-keyed chains it did not show where the link was named
   like the table: the stage hashed `ProductID` as it stood.
2. **The path the product has for a key the catalogue lacks does not reach the binder.** `infer-keys`
   (ADR-0018, WP99) finds it: run against the data copy, `WorkOrderRouting.productid → Product.productid`
   (67 131 rows, 149 distinct values, all among the 504). The proposer offers it as a licence of provenance
   `inferred`, a human may accept it — and then nothing reads it. The offer counts `foreign_keys`; the inference
   lives beside them (`inferred_keys`). Replayed with that licence accepted, the second chain's stage stayed
   exactly as it was. Declaring the same key in the catalogue by hand binds the link. An accepted inference was
   a decision without effect.
3. **The hub's own stage has no binding of its own.** `hub_work_order_operation` (composite: `WorkOrderID`,
   `OperationSequence`; `source_entity: WorkOrderRouting`) is named after the concept, so the name rule binds
   nothing; such a hub gets its relation from the mapper's proposal — after the validator, and here not at all:
   the mapper's concept is the key's label (`work_order_operation`), which names no column. Both chains of
   2026-11-15 left that stage inferred (the first was bound by hand at sign-off — a binding WP134 would now
   refuse, see rule 2). The model itself says which table the hub is built from.
4. **The review does not say what is missing.** The stage's flag reads „no declared source table matched".
   Which hub, which relation, which column: not said.

## 2 The rules

1. **An inferred key a human accepted is a key of its relation.** Wherever a link's relation is resolved — the
   key repair, the offer and evidence tiers, both link gates of the validator, WP135's rename, the binding
   reasons — the increment's tables are read with their declared foreign keys *and* the accepted licences of
   provenance `inferred` (`link_proposal.keyed_schemas`). From there the declared path runs unchanged: the
   relation offers the hub, the link reads it, the licence translates. The column is spelled as the table
   declares it (a data copy reflects `productid`). Nothing else reads it: the catalogue, the prompt and
   staging's own reading stay as declared (WP99 rule 7); an inference nobody accepted changes nothing
   (ADR-0018 §4). The translation built on it is a decision to confirm, as WP128 made it.
2. **A new hub is bound to the table its own model names, before the validator.** A single-source hub of the
   increment whose `source_entity` names exactly one table of the increment, where the name rule binds none,
   gets that table as its stage's relation (`staging_generator.hub_provenance`) — the last tier, after a
   human's binding, the mapper's and a ratified proposal's override, a carried binding and the name rule; the
   column check (WP73) judges it like any other. Because it is bound when the validator runs, **the gates that
   read a stage's relation see it**: the hub's satellites are grain-judged (WP85) in the attempt, not bound
   behind the gate by the mapper. Never a hub of the vault being extended (it carries its binding), never a
   multi-source hub.
3. **The missing key is named.** A new link no relation offers, where — among the relations that offer the
   most of its participations — exactly one carries, for every hub it does not offer, a column that is a name
   candidate (WP99's tier) for the single-column primary key of a table that hub is built from, gets one
   disclosure, `link_key_missing` (asset the link, reason the relation): which relation, which hub, which
   column, and the two ways to supply the key — a declaration in the source schema, or `infer-keys` and a yes
   at the resolution checkpoint. Told where the link's stage stayed inferred. **The name is a pointer, never a
   key**: nothing binds, joins or translates on it (WP34's rejected name-only tier stays rejected). Not a
   column the relation declares a key into something else, not its own single-column primary key, not a
   natural key's name (they recur as attributes).

## 3 Why not more

- **Binding on the name** (`ProductID` is called like `Product.ProductID`, so join on it) is the tier WP34
  rejected and ADR-0018 replaced by evidence a human decides on. A wrong join loads wrong keys with every gate
  green.
- **A gate that refuses the link** (remedy: leave the hub out — the product is reachable through the work
  order) would change what the modeler builds in every chain measured so far and cost an attempt in most. It
  may be right; it is a modelling decision, and the candidate's go did not name it. Candidate C74.
- **Binding the hub's stage behind the validator** (a fallback where the mapper has no answer) was the first
  form of rule 2 and was dropped before this spec: it would have made, silently, the binding WP134 refuses
  when a human makes it at sign-off (a relation unique on three columns under a hub keyed on two).

## 4 Not done

- **C74** (above): what the tool does where no key evidence exists stays as it is — the link's stage is
  inferred and disclosed; new is only that the disclosure says what is missing.
- **The shipped demo is not regenerated.** It would need a catalogue with inferred keys and one yes at a
  checkpoint — a paid chain and the owner's decision, also on how the demo's checkpoints are answered.
- **`infer-keys` over a catalogue that declares keys** infers, for a column with a declared foreign key, the
  next-best target (25 of 36 inferences on the AdventureWorks catalogue: `WorkOrder.productid →
  ProductProductPhoto.productid` beside the declared key to `Product`). Noise at the checkpoint, declined by the
  bulk answer. Found here, not repaired: candidate C73.
- An accepted inferred **link proposal** (the target hub already exists) is not routed through
  `keyed_schemas`: it names its hub and binds by the proposal's own override (WP34 §3.5). Read in the code,
  not measured.
- Accepted inferred keys are not carried to later increments as keys; the link's binding and translation are
  (WP77, WP105), which is what a later step reads.
- A hub the mapper binds where its model names no single table is still bound after the validator (WP134 §3).

## 5 Pre-registration

A prototype of the three rules was replayed on both chains of 2026-11-15 before this spec was written — that
is how rule 2 moved in front of the validator — so P3 and P4a are predictions with their result known. P4b and
P5 are not.

- **P1** guards (`tests/test_wp136_link_key_not_declared.py`) red first — nine of fourteen: the seven that
  state the new behaviour, and two that pin what stays by asking the new function (a hub of the vault being
  extended, a hub named like its table) and are red only for its absence. The five others that pin what stays
  (an inference nobody accepted, the mapper's answer first, the name binding nothing, an offered link told
  nothing, a natural key's name no pointer) green by design. Then all green.
- **P2** suite with no key reachable, ruff, bare mypy; no byte-identity fixture changes; the guards of WP42,
  WP73, WP85, WP90, WP99, WP134 and WP135 unchanged.
- **P3** reach, zero cost. Rule 2 over the ten stored runs of 2026-11-15: it fires for
  `hub_work_order_operation` in each chain's third step and for no other hub. Rule 3 over the 36 stored
  fifth-step models: 25 links told, one per model, every one over `WorkOrderRouting` for `hub_product`; the
  other 11 of §1's 36 are bound by name and need no telling.
- **P4a** replay of the second chain of 2026-11-15, **no key accepted**: step 3 refuses
  `stg_work_order_operation` → `WorkOrderRouting` for the columns the link hashes (`BINDING_REJECTED`, in place
  of the `shared` disclosure) and tells `link_key_missing`; one inferred stage stays in steps 3 to 5; no
  validation error; no other stage differs from WP135's replay. First chain: one `link_key_missing` in step 3,
  nothing else new.
- **P4b** the same chain with the key: step 3's increment read with the keys `infer-keys` found in the data
  copy; the real proposer offers `WorkOrderRouting.productid` as a licence of provenance `inferred`; the bulk
  answer declines it and one explicit yes takes it. Then `stg_work_order_operation` is bound to
  `WorkOrderRouting` before the validator with two joins (`Product` reading `PRODUCTID`, `Location` reading
  `LOCATIONID`); **no inferred stage in steps 3 to 5**; no validation error; the product translation is flagged
  to confirm; two links `WorkOrderRouting` now also offers (`link_product_location`, `link_work_order_product`)
  keep their relation and become bindings by evidence — two more decisions at step 3's sign-off.
- **P5** keyless build of P4b's fifth project on PostgreSQL (database `aw_source`, a schema of its own)
  **with no hand view**: no error, no skip; a second build inserts nothing; `link_work_order_operation` holds
  one row per row of `WorkOrderRouting` (67 131), every product key joins `hub_product`, and the (work order,
  sequence, product number, location name) tuples equal the source's through its joins, both ways.
- **P6** live: none in this WP. That the modeler is refused, and repairs, a satellite on a hub bound by rule 2
  is WP85's loop, measured live for other stages; for this one, the next chain.

## 6 Measured

Appended when built.

### Measured (2026-11-16)

- **P1 ✔.** Nine of fourteen red at `8759e10`, fourteen green after.
- **P2 ✔.** Numbers in `docs/log.md`. No byte-identity fixture changed; the guards of WP42, WP73, WP85, WP90,
  WP99, WP134 and WP135 untouched and green.
- **P3 — rule 3 ✔, rule 2's prediction was wrong.** Rule 3 over the 36 stored fifth-step models (1 955
  links): 25 told, one per model, every one over `WorkOrderRouting` for `hub_product`
  („WorkOrderRouting.ProductID is named like Product.ProductID"). **Rule 2 binds five hubs per chain, not the
  one announced:** `hub_work_order_operation` in step 3, and `hub_purchase_order`, `hub_purchase_order_line`
  (step 4), `hub_sales_order`, `hub_sales_order_line` (step 5) — hubs named after the concept whose tables are
  the header and detail tables. The prediction was measured on the rule's first form (a fallback where the
  mapper has no answer, §3) and carried over unchecked when the rule moved in front of the validator. The four
  are the hubs the mapper bound to the same tables after the validator: their final staging is unchanged
  (byte for byte in the replay), they are now bound when the gates look, and no gate objects — no validation
  error in any of the ten replayed steps that the stored runs did not have.
- **P4a ✔.** Second chain, no key: steps 1 and 2 as stored; step 3 refuses `stg_work_order_operation` →
  `WorkOrderRouting` („declares none of PRODUCTNUMBER, NAME that the stage hashes or derives") and tells
  `link_key_missing`; the `shared` disclosure is gone; one inferred stage in steps 3 to 5 (98 / 115 / 168
  declared); no validation error; no stage differs from WP135's replay. First chain: one `link_key_missing` in
  step 3 (`link_work_order_operation_location`); its two validation errors in step 3 are the ones its replay
  has had since WP133 and WP134 (the bill of materials before the remedy, and the satellite on the stage a
  human bound at sign-off).
- **P4b ✔.** `infer-keys` over the full catalogue against the data copy: 63 of 68 tables read, 36 inferred
  foreign keys, among them `WorkOrderRouting.productid → Product.productid` (67 131 rows, 149 distinct values,
  504 on the other side, candidate by name, tied with `ProductProductPhoto.productid`). The real proposer on
  step 3's increment: 28 declared proposals and licences, 11 inferred licences; the bulk answer accepts the 28
  and declines the 11; one explicit yes takes `WorkOrderRouting.productid`. Then: `stg_work_order_operation`
  declared on `WorkOrderRouting` **at validation**, two joins (`Product` reading `PRODUCTID`, `Location`
  reading `LOCATIONID`); declared stages 99 / 116 / 169, **inferred 0** in steps 3 to 5; no validation error;
  the product translation flagged to confirm; `link_product_location` (kept on `ProductInventory`, by payload)
  and `link_work_order_product` (kept on `WorkOrder`, by key) become bindings by evidence — two more decisions
  in step 3. One zero-key stage more (`stg_work_order_operation_zero_keys`). First chain with the key:
  `stg_work_order_operation_location` declared on `WorkOrderRouting` with the same two joins, inferred 0.
- **P5 ✔.** The replayed fifth project of the second chain, built on PostgreSQL (database `aw_source`, schema
  `replay_wp136`) **with no hand view** — no relation named `raw_…` exists in the schema: PASS=586, ERROR=0,
  SKIP=0 of 586 (the demo: 575 with two hand views; WP135's replay: 579 with one); second build 186 of 186
  incremental models `INSERT 0 0`. `link_work_order_operation`: 67 131 rows — `WorkOrderRouting`'s; its (work
  order, sequence, product number, location name) tuples equal the source's through its joins both ways (0
  missing, 0 extra); every product and location key joins its hub, none on a zero key; 149 distinct products on
  both sides. `hub_work_order_operation`: 67 133 rows, two of them system rows.
- **P6** not measured: no chain has run on this code. In the second chain the satellites on
  `hub_work_order_operation` were already multi-active (the modeler had been refused them on another stage),
  so the replay does not show the grain gate firing on a stage bound by rule 2; the guard does.
- **Not announced, found while building:** the name candidate (`is_name_candidate`) moved from
  `key_inference` to `rules/dv2_rules` so that the disclosure reads it without importing the module that
  reads rows; `key_inference` re-exports it. The translation flag's asset spells the column as the inference
  does (`WorkOrderRouting.productid`), the stage as the table declares it (`PRODUCTID`).
