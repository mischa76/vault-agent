# How requirements become a model — current behaviour, assumptions & target

> **Purpose.** A plain map of how Vault-Agent turns an input document into a Data Vault model
> and dbt code *today*, what it implicitly assumes, and the agreed **target architecture** for
> naming and inputs. Written to cut through ambiguity before building the next features.
> **Snapshot: 2026-06-17.**

## TL;DR

- **Today** Vault-Agent works from **one input — a functional requirements document in business
  prose** — and the LLM infers entities, business keys, relationships and attributes from that
  text. Physical column names are *derived from the prose* (`"national customer ID"` →
  `NATIONAL_CUSTOMER_ID`). So today's Raw Vault is named in **business language**.
- **Decision (this doc):** that is a **PoC simplification, not the target.** Per Data Vault 2.0
  doctrine, the **Stage and Raw Vault stay in the source-system dialect** (hard rules only);
  translation into a department's *Fachsprache* happens **downstream** (Business Vault soft rules,
  Information Marts). See [§ Target](#target-architecture).
- **Consequence:** the target needs **two inputs** — the requirements (scope + modeling intent)
  *and* the source schema (physical names + types) — plus a **mapping** between them.

---

## How the pipeline works today

The data actually flows like this (grounded in `src/vault_agent/`):

| Stage | Consumes | Produces | LLM? |
|---|---|---|---|
| `orchestrator` | inputs | execution plan, review queue | no |
| `requirements_parser` | the document (`.md/.txt/.pdf/.docx`) | `ParsedRequirement[]` (id, text, category, actor, action, object) | yes |
| `business_key_identifier` | requirements (+ optional source schema*) | `BusinessKeyCandidate[]` (entity, field, score, rationale) | yes |
| `data_contract` | requirements + business keys (+ optional schema*) | draft contracts + dbt tests | yes (enrichment) |
| `dv2_modeler` | requirements + business keys (+ optional schema*) | `DVModel` — hubs, links, satellites | yes |
| `code_generator` | `DVModel` | AutomateDV/dbt models + metadata | **no (deterministic)** |
| `validator` | model + artifacts | validation report (E_/W_ gates) | no |
| `human_checkpoint` | review queue | sign-off / owner assignment | no |
| `adr_author` | model | finalized ADR | no |

\* *The optional source schema (`state.source_schemas`) is read by the grounding helpers, the
modeler/business-key prompts, and the validator. It is now **fed** by a declared-file producer
(`vault-agent run --source-schema <file.yml>`, source-schema-input spec Phase 1), so grounding
activates when a schema is supplied; with no flag it stays empty and inert. Naming Stage/Raw Vault
from the source schema (the two-input target) remains Phase 2.*

### Where the names come from today

The model's identifiers are **free text the LLM lifts from the requirements prose**
(`Hub.business_key`, `Hub.source_entity`, `Satellite.attributes`). The deterministic
`code_generator` only normalises them to `UPPER_SNAKE` via `normalize_identifier`
(`"national customer ID"` → `NATIONAL_CUSTOMER_ID`; entity `customer` → `CUSTOMER_HK`).

There is **no source-system input and no source→target mapping**. If the real source column is
`KD_NR`, Vault-Agent cannot know it — it invents `NATIONAL_CUSTOMER_ID` from the text. **This means
today's Raw Vault is already named in business language** — which the next section corrects as a
target.

---

## Target architecture

**Naming rule (decided):** Stage and Raw Vault stay in the **source-system dialect**; business /
department *Fachsprache* is applied **only downstream** (Business Vault and Information Marts).

**Why (DV2.0 anchoring).** The Raw Vault is loaded with **hard rules only** — operations that do
*not* change the meaning of data (hashing, load-date, record-source, dedup, meaning-preserving type
alignment). Renaming to a business vocabulary is a **soft rule** (it imposes interpretation) and is
therefore excluded from the Raw Vault by doctrine; combined with **source-alignment**, the Raw
Vault mirrors the source. The canonical homes for renaming/harmonisation are the **Business Vault**
(soft business rules) and the **Information Marts** (consumer-specific presentation).

**Why it matters in practice.** The vault is *one* asset for *many* departments. Naming it in one
department's language alienates the others, who know the data by its source names. Harmonisation is
not even done across sources in the Raw Vault: sources are consolidated **only on the business key**
(same hub, collision code if needed), while descriptive attributes land in **one satellite per
source**, each keeping that source's native names. Translation to a single *Fachsprache* is
consumer-specific and belongs in the marts.

> Note: "source dialect" usually means source names with at most a **technical, meaning-preserving**
> normalisation (casing, illegal characters, prefixes) — not necessarily byte-for-byte. What is
> excluded is *business/department semantics* in the Raw Vault.

### Two inputs, clear roles

| Input | Role | Provided by |
|---|---|---|
| **Functional requirements** (business prose) | **Scope + modeling intent**: which entities/keys/relationships are relevant, grain, effectivity, which attributes are in scope | Business analyst / SME |
| **Source schema** (DB / file / XML metadata) | **Physical names + types** that actually populate Stage + Raw Vault | Source system / data engineer |
| **Mapping** (business concept ↔ source column) | Ties intent to physical reality | Analyst artifact — **agent proposes, human confirms (HITL)** |

So the requirements document drives *what to build and why*; the source schema drives *what things
are physically called*. The agent's job includes **proposing the mapping**, ratified at the
human-in-the-loop checkpoint.

---

## Minimum input requirements

**Today (single-input, PoC):** a functional requirements document that, in natural language,
states:

- the **business objects/entities** (e.g. customer, account, transaction);
- **explicit business keys** ("a customer is identified by their national customer ID" — without
  such a sentence the business-key identifier has nothing to latch onto);
- the **relationships**, with cardinality and temporal behaviour ("an account belongs to one
  customer at a time, ownership transferable" → effectivity);
- the **descriptive attributes** per object.

`examples/inputs/bank_account_requirements.md` is the reference shape.

**Target (two-input, enterprise):** the above **plus** a declared **source schema** (table/column
names + types) for the relevant objects, so Stage/Raw Vault can be named source-faithfully and the
mapping can be grounded.

---

## Gaps to close to reach the target

1. **Source-schema input + producer** — ✅ **done (Phase 1)**: `--source-schema` loads a declared
   YAML/JSON file into `source_schemas`, activating grounding. Richer producers (DDL parsing, DB
   profiler) remain future. Per [ADR-0007](architecture/adrs/ADR-0007-automation-scope-by-layer.md)
   this is **assist-level and selective** (a curated, requirements-scoped subset — not a full DB
   dump).
2. **Mapping step** — business concept ↔ source column, agent-proposed, human-confirmed; feeds the
   modeler so Raw Vault names come from the source, not the prose.
3. **Staging generator** — Vault-Agent emits raw-vault models but not the `stg_*` layer that
   computes hash keys/hashdiffs and is the natural home for meaning-preserving technical
   normalisation (see the [PoC spec](architecture/poc-end-to-end-dbt-spec.md)).
4. **Per-source satellites** — support multiple satellites per hub, one per source, with
   source-native attribute names.
5. **Downstream business naming** — translation into Fachsprache lives in Business Vault / Marts,
   which are **assist/scaffold scope only** ([ADR-0007](architecture/adrs/ADR-0007-automation-scope-by-layer.md)),
   not authoritative generation.

---

## Status: today vs. target

| Concern | Today | Target |
|---|---|---|
| Inputs | requirements prose only | requirements (scope/intent) + source schema (names/types) |
| Raw Vault naming | business language (from prose) | **source dialect** (technically normalised) |
| Source→target mapping | none (names invented from prose) | explicit, agent-proposed + human-confirmed |
| Cross-source handling | single implied source | consolidate on business key; **per-source satellites** |
| Fachsprache | (leaks into Raw Vault) | **downstream only** (Business Vault / Marts) |
| `source_schemas` | **fed** by `--source-schema` (declared file) → grounding active | richer producers (DDL parse, DB introspection) |

---

## Note

The naming/inputs decision recorded here ("source-dialect Stage + Raw Vault; Fachsprache
downstream; two-input target") is significant enough to promote to a dedicated **ADR** when the
source-schema producer and staging generator are actually built. Until then this map is the agreed
direction.

## References

- [ADR-0003 (amended): codegen backend = AutomateDV](architecture/adrs/ADR-0003-codegen-automatedv.md)
- [ADR-0004: source-schema grounding](architecture/adrs/ADR-0004-source-schema-grounding.md)
- [ADR-0005: data contracts](architecture/adrs/ADR-0005-data-contract-spec.md)
- [ADR-0006: human-in-the-loop review queue](architecture/adrs/ADR-0006-human-in-the-loop-review-queue.md)
- [ADR-0007: automation scope per layer](architecture/adrs/ADR-0007-automation-scope-by-layer.md)
- [PoC spec: end-to-end dbt + AutomateDV + Postgres](architecture/poc-end-to-end-dbt-spec.md)
- Methodology: Linstedt & Olschimke, *Building a Scalable Data Warehouse with Data Vault 2.0*
  (hard/soft rules, Raw Vault source-alignment); Roelant Vos, DSAF.
