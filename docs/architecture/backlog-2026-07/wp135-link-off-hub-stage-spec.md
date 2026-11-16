---
type: spec
status: not-measured
updated: 2026-11-16
---

# WP135 — A link that would share a hub's stage while reading another relation is renamed after its hubs (C71)

Status: **Approved and in progress** (2026-11-16, on the owner's go of that day: fix C70 and C71; of the three
ways laid before him the same day — rename the link, give it a stage of its own under its name, a gate with a
remedy — the owner chose the rename) · Owner: Mischa Eismann · Author: Claude. Candidate C71.

## 1 What is wrong — and what C71 said instead

C71 was recorded (2026-11-15) as: a link named like a table is bound to that table by the name rule before its
declared keys are asked. That is what `resolve_link_relation` answers, but it is not why the stage fails, and
neither option the candidate named would have repaired it.

A stage is named after its construct's base: `stg_<base>`. `hub_product_subcategory` and
`link_product_subcategory` have one base, so **one staging model serves both** (`collect_staging_specs` groups
constructs by the stage that feeds them, by design: a hub and a link over one relation share its stage —
`hub_product_review` and `link_product_review` over `ProductReview`). Here they read two relations. The hub is built from
`ProductSubcategory`; the link's participations — `hub_product` and `hub_product_subcategory` — are offered by
`Product` alone (its own hub, and its foreign key `ProductSubcategoryID`). The shared stage hashes the
subcategory's name for the hub and the product number for the link. The hub's binding to `ProductSubcategory` is
then refused for the link's column (WP73, `BINDING_REJECTED`), the stage falls back to `raw_product_subcategory`,
and **the hub loses its declared relation with the link**. The link's licence over `Product.ProductSubcategoryID`
is ratified and never applied: the link does not „read" `Product` (the name tier), and `link_source_overrides`
does not repoint a stage a hub owns (reason `shared`, WP42).

**Measured on the 36 stored chain models** (fifth steps, 2026-09 → 2026-11-15, the full catalogue): 1 955 links,
91 on a single-source hub's stage, and for 60 of them the hub's relation offers the link's participations nothing
while another relation does — `link_product_subcategory` 24 times, `link_product_model` 19, `link_product_photo`
17. Not a case of the second demo chain alone: about two links per chain, each a refused binding and a decision
at sign-off since WP73 (what became of them before it was not examined). Under any other name the same link builds
(the first chain of 2026-11-15 named it `link_product_product_subcategory`: bound to `Product` by its offer,
translated, built).

## 2 The rule

A backstop in the modeler, `link_off_hub_stage`, on the delta as emitted — before the repair memory, the
remembered delta and every applier, so that the validator, a retry's payload and the memory see one name.

A link of this increment is renamed when **all** of these hold:

1. a single-source hub, of this increment or of the vault being extended, has the link's base (they would share
   `stg_<base>`);
2. at least one declared relation of the increment offers every participation of the link (WP42's offer, as a
   multiset);
3. no relation the hub is built from does — among the increment's tables and the carried catalogue;
4. the name the rule gives is a valid construct name, no construct of the vault or the delta has it, and its base
   is no hub's base.

The name is `link_` + the bases of its hubs in the order of its participations, a role after its hub
(`link_product_product_subcategory`; `hub_product`, `hub_product:component`, `hub_unit_measure` →
`link_product_product_component_unit_measure`) — the proposer's own form for a link it builds from a foreign key
(`link_proposal._link_name`). Satellites on the link follow it. Nothing else about the link changes.

Told: one `link_renamed` flag per rename — a **disclosure** (asset the new name, reason the old one; the message
names the hub, its relation and the relations that offer the link), and one `backstop` trace event
(`link_off_hub_stage`).

**When rule 4 declines, nothing is renamed** and the stage is refused and shown as before (WP73's decision).
Never a second link of one name, never a guess.

Unchanged: a link of the vault being extended (its name is materialised); a link whose hub's relation offers it
(the shared stage is right); a link no relation offers (C64's class — nothing says what it reads); the name tier
of `resolve_link_relation`.

## 3 Why a rename, and what it costs

The stage name derives from the construct name at more than a dozen call sites (the generators, the
carried-binding tier, the grain gate, the binding overrides, the subject areas); giving the link a stage of its own under its old name means a second
naming rule at each of them plus a field on the model so that the name holds across increments. That is the
cleaner end state and was laid before the owner as such; he chose the rename. A gate would leave the name to the
modeler and cost an attempt in most chains.

The cost: the table in the warehouse carries a name the modeler did not choose. It is the name DV practice gives
a link anyway, it is disclosed, and it is decided once — the renamed link travels in `dv_model.yml` and is never
renamed again.

## 4 Not done

- **A stage of its own under the link's name** (above). If wanted later, it replaces this backstop.
- **The name tier** (C71's own title): after the rename the link is not named like the table. A link named like
  a table that offers it nothing, on no hub's stage, stays as it was — 2 of 1 955
  (`link_sales_territory_history`, twice), not examined.
- **C64** (a link no relation offers: `link_work_order_operation`) — the other hand view of the demo.
- A multi-source hub's grandfathered feed stage shared with a link: not looked at; no case in the corpus.
- **The shipped demo is not regenerated.** Its second inferred stage is this shape; a new chain is a paid run
  and the owner's decision.

## 5 Pre-registration

A scratch prototype of rule 2 was replayed on the second chain of 2026-11-15 before this spec was written (that
is how the three ways were laid before the owner), so P4 is a prediction with its result known; P3 and P5 are
not.

- **P1** guards (`tests/test_wp135_link_off_hub_stage.py`) red first — six of ten; the four that pin what stays
  (a hub's relation that offers the link, a link nothing offers, a taken name, a link of the vault being
  extended) green by design — then green.
- **P2** suite with no key reachable, ruff, bare mypy; the byte-identity fixtures and WP42's, WP73's and WP105's
  guards unchanged.
- **P3** corpus: the rule over the 36 stored models (each as a delta against an empty vault, the full
  catalogue) renames only links among the 60 of §1, each to the name of §2; where it declines, rule 4 says why.
- **P4** zero-cost replay of the two chains of 2026-11-15. The first: five of five steps „model as stored", no
  stage changes. The second: one rename in step 3; in steps 3 to 5 `stg_product_subcategory` is bound to
  `ProductSubcategory` and `stg_product_product_subcategory` to `Product` with one translation; no
  `BINDING_REJECTED`; no validation error; one inferred stage left (`stg_work_order_operation`); no other stage
  changes.
- **P5** keyless build of the replayed fifth project on PostgreSQL with one hand view: no error, no skip; a
  second build inserts nothing; the link holds one row per product with a subcategory, every key joining its hub;
  `hub_product_subcategory` holds the table's names.
- **P6** live: none in this WP. The next chain, when the owner runs one.

## 6 Measured

Appended when built.
