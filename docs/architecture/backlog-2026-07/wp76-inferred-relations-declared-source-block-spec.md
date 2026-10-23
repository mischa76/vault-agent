---
type: spec
status: not-measured
updated: 2026-10-17
---

# WP76 — Inferred relations are declared: an `inferred` source block in the target schema, so a grounded project parses whole and only the unprovided stages fail at build

Status: **Approved and in progress** (2026-10-17, the owner's go) · Owner: Mischa Eismann
· Author: Claude. From the nineteenth chain's Databricks build (`docs/log.md`, 2026-10-17):
the fifth project failed `dbt parse` on `ref('raw_sales_order')` — one inferred binding made
the whole project unparseable; with the 50 inferred relations declared by hand as a source
block it parsed and built (PASS=220, the 50 errors exactly the unprovided relations). No prompt
change; the suite stays keyless.

## 1 The defect, in one paragraph

AutomateDV's `stage` macro turns a bare `source_model` name into a dbt `ref()`. In a seed
world (the ungrounded demos, no declared source schema) that is the verified pattern: the
seed `raw_<base>` is the node. In a grounded project whose declared inputs are addressed
through `source()` blocks there is no such node, so every inferred `raw_<base>` — the WP47
`none`/`ambiguous` bindings and the WP73 refusals — is a missing ref, and dbt refuses to parse
the project. Eighteen green chains produced projects that never parsed; the hand patch in the
nineteenth's kept fifth project proved the shape that does.

## 2 The rules

1. **An `inferred` block when the project speaks `source()`.** When `group_sources` yields at
   least one declared block (the project addresses declared inputs through `source()`),
   `build_staging` gives every unbound spec the source name `inferred`
   (`rules.INFERRED_SOURCE_NAME`) and adds one block of that name to `sources.yml`, with
   `schema: "{{ target.schema }}"` (quoted — dbt renders a source's `schema` with Jinja; the
   installed dbt-core 1.11 `SchemaYamlRenderer.should_render_keypath` skips only
   `description` and `loaded_at_query` for sources) and the merged inferred relations as its
   tables, each with the expected columns and a note naming it inferred. The stage then
   renders the mapping form `source_model: {inferred: raw_<base>}`; a translation view's own
   `source()` follows from the same `source_name`.
2. **Nothing else moves.** Ungrounded runs and grounded runs without a physical location
   (no block) keep the bare name — the seed pattern the Postgres demos are verified on.
   Declared bindings, blocks, metadata (`source_binding: inferred` stays) and flags are
   unchanged; `SOURCE_BINDING`/`BINDING_REJECTED` still say what a human must provide.
3. **Resolution is a parse-time fact.** `unresolved_stage_refs` is unchanged: an inferred
   relation declared under the `inferred` block resolves, so `project_self_contained` reads
   1.0 for a project dbt parses; `stage_refs_inferred` keeps counting what a human must
   provide. The two metrics now say two different things, as their names do.
4. **The README** says where an inferred relation is expected: a table or view of that name
   in the target schema (seeds land there too).

## 3 Guards before the change

1. `build_staging` over the WP74 fixture with an unbindable link (no override): the link's
   stage renders `source_model:\n  inferred: 'raw_account_customer'`; `sources.yml` carries a
   block `inferred` with `schema: "{{ target.schema }}"` and that table; the declared blocks
   are unchanged; `unresolved_stage_refs` is empty; the `SOURCE_BINDING` flag is still raised.
2. The same model ungrounded (no `source_schemas`) renders byte-identically to today's
   baseline (`staging_ungrounded_baseline`); a grounded run whose tables carry no location
   keeps `source_model: 'raw_account_customer'`.
3. A translation view whose link stage is inferred references `source('inferred', …)`, not
   `ref('raw_…')`.
4. The rendered `sources.yml` parses as YAML (the quoted Jinja) and the `inferred` block's
   schema value is `{{ target.schema }}`.

## 4 Pre-registration

The nineteenth chain's kept fifth project regenerated keylessly from its model and catalogue
(`--existing`, the replay path): `dbt parse` on Databricks succeeds without a hand patch, and
`dbt build` of the regenerated project fails exactly on the inferred stages
(`TABLE_OR_VIEW_NOT_FOUND`) and their dependants, nothing else. The twentieth chain:
`project_self_contained` 1.0 and `stage_refs_unresolved` 0 in every step, with
`stage_refs_inferred` > 0 reporting honestly.

## 5 Not in this WP

Providing the inferred relations (a human's `--map`, a later binder tier); a `through`
relation nothing stages in a translation view (still a bare ref).

## 6 Results

*(appended after the change)*
