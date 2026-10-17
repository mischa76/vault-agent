---
type: spec
status: not-measured
updated: 2026-10-17
---

# WP73 — A staging model is refused when its relation lacks a column it hashes; the override loop stops binding multi-source hubs' links

Status: **Approved and in progress** (2026-10-17, user: „go, bau WP73“) · Owner: Mischa Eismann
· Author: Claude. From WP72 stage 3 and the correction of 2026-10-17 (`docs/log.md`): 13 link
stagings bound to relations lacking a hashed participation column, deterministic, in every
chain, invisible without a build. No prompt change; the suite stays keyless.

## 1 The defect, in one paragraph

`link_source_overrides` (WP34 §3.5) binds a link to a ratified proposal's `source_table` when
a participating hub „binds to“ that table and the proposal targets another participation.
`hub_binds_to_source_table` is true for every feed of a multi-source hub (WP10), so a link on
`hub_business_entity` (twelve feeds by the sales step) is bound to whichever ratified
license's table the loop visits last — `EmployeePayHistory`, `Store`, `Vendor` — and the stage
hashes columns that relation does not carry. Nothing refuses it: the validator runs before
the mapper's re-bind, and `bind_sources` trusts every override.

## 2 The rules

1. **A binding is checked where it is decided.** `bind_sources` computes the columns a
   staging model reads from its relation — every hashed column (single, list, hashdiff) and
   every derived column's source — and, when the relation is a *declared* table, requires each
   to be declared there (normalised identifiers). An override or a name match that fails is
   **not applied**: the spec falls back to the inferred `raw_<base>` binding and raises a
   typed flag `FlagKind.BINDING_REJECTED` (asset: the staging model; `reason`: the rejected
   table) whose message names the missing columns. A translated stage (WP36/38 joins) is out
   of scope here, its columns are judged by the translation gates.
2. **The gate.** The validator reads the staging metadata the code generator stored
   (`artifacts.automatedv_yaml["staging"]`) and refuses, with `E_STAGE_COLUMN_NOT_IN_SOURCE`,
   any declared-bound, untranslated stage whose relation lacks a column it hashes or derives —
   the generalisation of `E_SAT_KEY_NOT_IN_SOURCE` to every construct; grounded runs only.
   Rule 1 keeps the re-bind from re-introducing what the gate refused.
3. **The loop.** The ratified-proposal loop of `link_source_overrides` binds a link only when
   the participating hub is built from the proposal's table *and from nothing else* — no
   `sources` feeds, or every feed that table; a multi-source hub's links keep the binder's
   own resolution (`offer`, else inferred and flagged).
4. **Review:** `BINDING_REJECTED` is a decision (a human maps the relation), grouped
   `binding-rejected`; its one-liner joins `rules/catalogue.py`; the gate joins the catalogue
   and chapter 8.

## 3 Guards before the change

1. `bind_sources`: a spec hashing `DEPARTMENTID` with an override to a declared
   `EmployeePayHistory` that lacks it ends bound to `raw_<base>` with one `BINDING_REJECTED`
   flag naming the table and the column; the same override to a table that declares the
   column binds silently; a name match to a table lacking a hashed column is refused the
   same way.
2. `link_source_overrides`: a hub with feeds `A` and `B`, a ratified license on `B`
   targeting the hub, and a link between the hub and another whose columns only `C`
   declares — no override to `B` (today there is one); a single-source hub from `B` keeps
   the override.
3. The validator on a state whose staging metadata binds a stage (declared) to a relation
   lacking a hashed column: one `E_STAGE_COLUMN_NOT_IN_SOURCE` naming the stage and the
   column; a translated stage is not judged; an inferred binding is not judged.
4. The registries: `FLAGS`, `GATES`, chapter 8, `REVIEW_FLAG_ROLES`, `REVIEW_FLAG_GROUPS`
   (the existing guards enforce them).

## 4 Pre-registration

The sales step's model of the Databricks chain (`dbx-chain/sales`, out of the repo), replayed
keyless through `build_staging` with the chain's ratified proposals: the seven `Store`
bindings disappear, replaced by inferred bindings with `BINDING_REJECTED` or `SOURCE_BINDING`
flags; no new binding to a relation lacking a column. The nineteenth chain, when it runs, will
show the gate's and the flag's live counts.

## 5 Not in this WP

The self-contained brownfield project and the harness building a step (WP74); a better
relation for the rejected links (a human's `--map`, or a later binder tier).

## 6 Results

*(appended after the change)*

**2026-10-17 — built, keyless; replayed on the Databricks chain's sales step.** Guards `269d883`
(red), the change `2153870`, docs in the commit carrying this line. **Two narrowings against §2,
both from the guards that held before:** the check reads the stage's *key* columns — each hash
key's source column(s) and each derived column's source — and not a hashdiff's attributes,
because a missing attribute is a partial schema and has been `W_ATTR_NOT_IN_SOURCE`'s warning
since WP7 (three staging-generator tests declare such partial schemas on purpose); and a hash
may read a *derived* column — a role alias such as `ORGANISATION_BUSINESSENTITYID` (WP41), which
AutomateDV derives before it hashes — so derived names count as available (the fk-links demo's
`link_business_entity_contact` showed it). The ratified-proposal loop iterates `ratified()`
link proposals, not licenses, which the guard now reflects. 1215 tests, ruff, bare mypy.
**§4 replay** (keyless: the purchasing step's model as `existing`, the sales schema, the real
proposer, `--accept`'s blanket ratification, then `source_overrides` and `build_staging` on the
sales step's final model): the proposer ratified 18 proposals from 13 tables, `Store` among
them; the seven links that read `Store` in the chain now bind `customer_person` and
`customer_store` to `Customer`, `person_credit_card` to `PersonCreditCard`,
`sales_order_sales_person` to `SalesOrderHeader` (the relations that carry their keys), and
`sales_person_sales_territory`, `sales_person_territory_history`, `store_sales_person` to the
inferred relation with a `source_binding` disclosure; `BINDING_REJECTED` fired 0 times, because
nothing wrong was proposed any more; the only stage reading `Store` is the hub feed's own
`stg_business_entity_store`. **Not measured:** the gate and the flag live (the nineteenth chain);
the HR, production and purchasing steps' replays (same mechanism, not repeated).
