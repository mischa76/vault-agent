---
type: backlog
status: proposed
updated: 2026-10-21
---

# Backlog candidates of October 2026 — from the owner's hands-on run

Status: **Proposed, not prioritised** (2026-10-21) · Owner: Mischa Eismann · Author: Claude.
Collected during the owner's own end-to-end run of AdventureWorks in the workbench (started
2026-10-19). Each entry needs its own go; the order below is the order they came up, not a
priority. Nothing here is built.

## C1 — ADR candidate: a source-driven mode (a run without a requirements document)

**Question (owner, 2026-10-21):** what happens today when only an input model is attached?

**Today, read from the code:** the run does not start. `vault-agent run` takes the requirements
document as a required, existing argument; the workbench's `StartRun.requirements` is required
(422 without). With an empty document the run would proceed and produce almost nothing: the
parser extracts no requirements, the business-key agent flags `missing_input` („no requirements
in state") and returns no keys, the contract agent still drafts one contract per table and the
proposer still derives key licenses from the declared foreign keys — both read the schema — but
the modeler's rule is „model only what the requirements support", so no hub is built and
licenses without hubs build nothing.

**The candidate:** a *source-driven* mode beside today's *requirements-driven* one: a raw vault
derived from the source catalogue — hubs from primary keys, links from foreign keys, satellites
from the remaining columns — largely deterministic and possibly without a model call. Common in
Data Vault practice for a first raw layer.

**Why it is an ADR and not a flag:** it inverts the product's premise. Nobody would ask whether
a table is a business concept: an associative table becomes a hub, a surrogate key a business
key, and the model takes the shape of the source instead of the business. The gates that make
the requirements-driven mode safe (`E_HUB_PAYLOAD_UNREAD`, the key licenses, entity resolution)
assume a modeler that chose its constructs from the business's words.

**Options the ADR would weigh:**

1. Do not build it (the product stays requirements-driven; the schema grounds and completes).
2. A deterministic source-driven generator as a separate entry point, its output marked as
   source-shaped and never mixed with requirements-driven runs.
3. A middle way: draft the requirements from the schema, a human corrects the draft, then the
   normal run starts — the way the AdventureWorks requirements were derived for the eval
   (`eval/adventureworks/derive.py`).

**Evidence to gather first:** how a derived-requirements run on AdventureWorks compares with
the owner-written chain (constructs, review load), and what a deterministic derivation makes of
AdventureWorks' associative tables (`BusinessEntityAddress`, `ProductProductPhoto`).

## C2 — Deleting in the workbench (projects, input files, runs)

The API creates and reads, nothing deletes (verified 2026-10-20: no `DELETE` route). Rules the
WP would need: a file a run has read is kept (its `run.json` and CLI equivalents name it); a run
another run extends (`existing_run`) is kept while referenced — its `metadata/` holds the model,
the catalogue and the stage bindings the extension started from; a running or paused run is
cancelled first (WP69). Confirmation in the frontend, a line in the event stream, 409 on a
violated rule.

## C3 — Project settings tab, including a naming profile

A per-project `settings.json` and a tab: target platform, model ids, an Anthropic-compatible base
URL (the SDK honours `ANTHROPIC_BASE_URL`; the client builds `AsyncAnthropic(api_key=…)` only),
recorded in each `run.json` and its CLI equivalents; secrets stay in `.env`, the tab shows only
whether they are set. A `NamingProfile` in `rules/` beside `PlatformProfile`: prefixes, suffixes,
the technical columns' names (`LOAD_DATETIME`, `RECORD_SOURCE`, `_HK`, `_HASHDIFF`,
`APPLIED_DTS`), upper or lower snake case — the default profile byte-identical. CamelCase and
case-sensitive names deliberately deferred: AutomateDV renders columns unquoted, so they need
quoting everywhere (WP79's `escape: true` as the mechanism) and a build per platform. An
OpenAI-compatible endpoint is a different protocol behind `ForcedToolCaller` — its own ADR.

## C4 — WP82: parity between the CLI and the workbench

The owner's word (2026-10-20): CLI and workbench must produce identical results. Gaps read from
the code: at start, `--target-platform` and `--profiling`; at the checkpoint, `--map` and
`--mappings`. The WP: a „reads TABLE.COLUMN" field on each `source_binding` item at sign-off
(the same function as `--map`), platform and profiling at start (shared with C3), and a test
holding `run`'s and `resume`'s options against the API's request models so the next CLI option
cannot bypass the workbench silently. A build from the workbench (the former WP81 sketch) is
**not** part of it: the workbench ends at the written project (14.3), the owner confirmed.

## C5 — Zoom and full screen for the Model perspective's diagrams

Mermaid's SVG is scaled to the tile's width, so a 13-table `erDiagram` becomes unreadable and the
tile never scrolls. Per tile: zoom in, out, fit, 1:1, Ctrl+wheel; scrollbars in both directions;
a full-screen overlay; the zoom remembered per tile while the page is open. Possibly the input
diagram by subject area too (the table's schema is the criterion, WP80).

## C6 — `W_UNTRACED_CONSTRUCT`

The modeler is told to cite `requirement_ids` for every construct, but no gate checks it
(verified 2026-10-21: neither the validator nor the gate catalogue reads `requirement_ids`). A
warning for every construct without one — a warning, because three paths are legitimately
untraced: links from ratified foreign-key proposals, translations from key licenses, satellites
the payload gate (`E_HUB_PAYLOAD_UNREAD`) makes the modeler add.

## C7 — Phase 3 spike: extending a vault vault-agent did not build

Reserved by the incremental-extension charter (§3.1), unscheduled. Needed: an introspection
reader deriving `dv_model.yml`, catalogue and bindings from a foreign AutomateDV project or a
database's DDL; a mode that references existing constructs instead of regenerating them
(„regenerate, don't patch", §3.2, does not hold for a foreign vault's physical names); a hash
agreement per vault (algorithm, separator, normalisation) in the platform profile, without which
a new link stands beside the existing hub instead of on it. Proposed test bed: the twenty-first
chain's PostgreSQL vault treated as foreign.
