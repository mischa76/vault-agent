# Roelant Vos / DSAF — Mapping onto Vault-Agent

> **Purpose:** Turn "Vos/DSAF" from a name-drop into an explicit, *critically assessed* foundation.
> Records (a) what Vault-Agent already embodies, (b) what is deliberately out of scope, and
> (c) where Vos diverges from the Linstedt DV2.0 canon — so adopting his ideas never silently
> pulls us away from DV2.0/CDVP² conformance.
>
> **Sources:** a curated study set compiled from roelantvos.com (glossary, pattern catalog,
> decision tables, bibliography) plus live verification of the GitHub repositories. Version
> numbers below are as of the study set (May 2026) and should be re-checked against the repos
> before relying on them.

## Vos's stack and where the code lives

All current open source lives under the **`data-solution-automation-engine`** GitHub org
(the older `RoelantVos/*` repos are deprecated and their URLs often redirect):

| Component | What it is | Repo |
|---|---|---|
| **VDW** — Virtual Data Warehouse | Code generator: DWA-JSON metadata + **Handlebars** templates → SQL/DDL/Biml. Database-less since v1.6.2. | `data-solution-automation-engine/Virtual_Data_Warehouse` |
| **TEAM** — Taxonomy of ETL Automation Metadata | Desktop tool to manage source-to-target mapping metadata; emits DWA-JSON into Git. Git directory *is* the repository (no DB since v1.6.5). | `data-solution-automation-engine/TEAM` |
| **DIRECT** — Data Integration Run-time Execution Control | ETL process-control framework: Module/Batch lifecycle, restartable, auditable. v2.0 ported to MS Fabric. | `data-solution-automation-engine/DIRECT` |
| **DWA Schema** | JSON Schema (draft 7, v2.1) for design-metadata interchange between any metadata tool and any generator. Core classes: DataObject, DataItem, DataObjectMapping, DataItemMapping, BusinessKeyDefinition. | `data-solution-automation-engine/data-warehouse-automation-metadata-schema` |
| **Agnostic Data Labs (ADL)** | Commercial, git-native successor to TEAM; non-opinionated (DV/ELM, Dimensional, Lakehouse). | agnosticdatalabs.com |

His current umbrella synthesis is the 2025 book **Data Engine Thinking** (with Dirk Lerner,
TEDAMOH), `dataenginethinking.com`. The **DSAF workshop sample** in the project library
(`Fortbildung/Roelant Vos DSAF WS/`) is a concrete VDW+TEAM instance — Handlebars templates plus
TEAM connection config.

## What Vault-Agent already embodies (credit, don't rebuild)

- **Metadata/pattern/template separation.** Vos's whole thesis (TEAM = metadata, VDW = templates,
  generator = engine) is the same separation Vault-Agent lives: rules/metadata in code,
  generation through AutomateDV templates. This is the single biggest "we already do DSAF" point —
  it just was never credited.
- **Deterministic, idempotent, restartable loads.** Vos makes this a first-class principle (the
  "anti-duplicate" `WHERE NOT EXISTS` tail on every load; re-initialisation from the PSA).
  Vault-Agent already aims for idempotent tools — worth elevating to an explicit generation rule.

## What is absent (deliberate scope decisions, not oversights)

| DSAF concept | Status in Vault-Agent | Disposition |
|---|---|---|
| **Persistent Staging Area (PSA)** — his "single most consequential idea": insert-only, ordered archive enabling full DV rebuild | Not modelled | **ADR decision.** Architecturally heavy; sits *outside* core DV2.0. Decide deliberately, don't default. |
| **PIT / Bridge** presentation tables | Code generator emits hubs/links/sats/nh-links only | Concrete, codeable gap; AutomateDV supports both. Reasonable next feature. |
| **Virtualisation (schema-on-read)** as the default above PSA | Vault-Agent materialises physical dbt models | Deliberate divergence — keep materialised; note it. |
| **DIRECT-style run-time control** (Module/Batch audit) | Out of scope (LangGraph orchestrates) | Leave out; different layer. |

## The critical lens — where Vos ≠ Linstedt DV2.0

This is the part that matters for CDVP² conformance. Vos has, over fifteen years, *deliberately
revised* several DV2.0 positions. Several are genuine improvements; all of them move away from the
strict Linstedt/Olschimke canon. Adopting "Vos" wholesale would therefore change what "DV2.0
compliant" means for the agent. Recommended stance: **anchor DV2.0 correctness on Linstedt/Olschimke
(matches CDVP²); treat each Vos revision as an opt-in, ADR-gated alternative — never the silent
default.**

| Topic | Linstedt DV2.0 canon | Vos's position | Recommended for Vault-Agent |
|---|---|---|---|
| Surrogate key | Hash key (MD5/SHA-1) | **Natural Business Key (NBK)** preferred for small/medium; hash only for MPP | Default to hash (canon, AutomateDV-native). NBK = future ADR. |
| Satellite end-dating | Persisted load-end-date common | **Insert-only**, derive end-date on read; end-dating deprecated | Keep canon default; insert-only is a legitimate ADR. |
| Link-Satellites | Standard DV2.0 construct | **ELM** (Hultgren) — relationship-describing Hubs, no physical LSAT | Keep LSAT (canon). Flag ELM as an alternative school, not a default. |
| Driving keys | Driving-key LSAT + effectivity sat | **Foreign-key Link** (his 2023 remedy) | Encode the canon driving-key/effectivity first; FK-link is an alternative. |
| Multi-active sats | Attribute-in-PK / separate sat | Prefers **weak Hub** or JSON-in-SAT | Support canon; weak-Hub as option. |
| Key collision | **BKCC** (per-source collision code) | Composite/concatenated keys + Record Source | Note both; BKCC is the canon answer. |

Two of the schools the user flagged show up directly here: Vos has **adopted Hultgren's ELM** as his
preferred physical implementation since ~2023, which is exactly the Genesee-Academy (modelling-only)
vs Scalefree/Linstedt (full methodology+modelling+architecture trilogy) tension. Vault-Agent should
stay on the Linstedt trilogy as its spec of record and reference ELM/Vos as commentary.

## Tooling honesty

Vos does **not** use dbt/AutomateDV — the study set explicitly notes dbtvault/AutomateDV are
"not engaged by name" in his work. His generator is VDW/Handlebars over the DWA JSON schema. So his
*patterns and decision tables* are transferable to Vault-Agent, but his *tooling* is a parallel
ecosystem, not a dependency. We borrow the thinking, not the engine.

## Candidate ADRs this surfaces

1. **PSA: yes/no** — adopt a Persistent Staging Area, or rely on AutomateDV staging + source replay?
2. **Hash key vs NBK** — keep hash as the DV2.0-canon default; document when NBK would win.
3. **End-dating vs insert-only satellites** — which is the generated default, and on which target.
4. **ELM / foreign-key Link vs classic Link-Satellite + driving key** — modelling-school stance.
5. **PIT/Bridge generation** — add to the code generator's repertoire for the presentation layer.

## Reference architecture (for the docs)

Vos's four layers, for mapping our generated artifacts onto a recognised DSAF frame:
**Source → Staging Layer (transient SA + persistent PSA) → Integration Layer (Raw DV + Business DV)
→ Presentation Layer (Information Marts, via PIT/Bridge).** Vault-Agent currently targets the
Integration Layer (Raw DV) and the source-to-staging boundary; PSA and Presentation are the
explicit white space.

## Where to go deeper (primary sources beyond the blog)

The study set flags these as thin on the blog and best taken from the whitepapers / book:
*Pattern for Data Mart Delivery* (canonical PIT/Bridge/dimension generation), *Consistency &
Referential Integrity* (15 pp.), *Merging Time-Variant Data Sets*, and **Data Engine Thinking**
(the 700-page canonical methodology). Worth fetching from the roelantvos.com Publications page when
implementing PSA or the presentation layer in earnest.
