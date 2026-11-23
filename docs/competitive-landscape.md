# Competitive Landscape & Differentiation

> **Purpose.** Where Vault-Agent sits relative to existing Data Vault automation and the emerging
> "LLM-for-Data-Vault" work — what is crowded, what is emerging, and what this project adds.
> Based on public information; **snapshot: summer 2026**, TurboVault Engine added 2026-10-30 and re-read
> 2026-11-23 — this space moves fast.

## TL;DR

"Automating Data Vault" is **not** novel — it is a mature, well-funded commercial category. What
is sparse is the specific combination Vault-Agent occupies: an **open-source, agentic system that
starts from business requirements** (not a source schema), encodes the **methodology as inspectable
rules**, generates code through the **open AutomateDV/dbt** stack, and documents its reasoning
(ADRs, validation, human-in-the-loop). The differentiation is the *entry point* and the
*transparency*, not the act of generating Data Vault objects.

## The space has three layers

**1. Data Vault automation — crowded and mature.** A commercial category with established vendors: VaultSpeed,
WhereScape (Data Vault Express), Datavault Builder, Coalesce, biGENIUS-X, Agnostic Data Labs
(Roelant Vos's closed-source successor to his TEAM/VDW open-source line, archived 2026), plus
open-source dbt packages (AutomateDV, datavault4dbt). These are production-proven and enterprise-supported. Two
things characterise almost all of them: they start from **source schemas / metadata**, and they
are **GUI- or template/YAML-driven**, not LLM-driven. DACH relevance is high — several of the
strongest players are German or Swiss (biGENIUS, Scalefree and its ecosystem).

**2. LLMs that generate Data Vault models — emerging, mostly academic (2025).** Recent papers
(e.g. MDPI's *Data Vault* case study; the *AI-Powered Data Vault 2.0 Modeling* preprint) show
ChatGPT deriving DV models, with formal validity scoring. The idea is "in the air" — but it is
research/PoC, and again works **from source metadata**, not from requirements documents. Vendors
are adding AI features to their products at the same time.

**3. Open-source, agentic, requirements-to-AutomateDV — effectively empty in public.** A
multi-agent (LangGraph) system that goes from **business requirements** → DV2.0 model → AutomateDV
/dbt code, with self-correcting validation, data contracts, an ADR trail, and human-in-the-loop:
no public equivalent was found when this page was researched. This is where Vault-Agent works.

## Comparison

| Tool | Primary input | Method | Codegen target | License | Reasoning trail (ADRs) | DV-rule validation | Maturity |
|---|---|---|---|---|---|---|---|
| **VaultSpeed** | Source schema / metadata | GUI, metadata-driven; AI-assisted features | Proprietary → Snowflake, Databricks, BigQuery, Fabric, Redshift | Commercial | — | Built-in templates/tests | Production, enterprise |
| **WhereScape (DV Express)** | Source metadata | GUI, full-lifecycle automation | Proprietary, multi-platform | Commercial | — | Built-in | Production, enterprise |
| **Datavault Builder** | Source metadata | Integrated GUI, ELT generation | Proprietary, multi-platform | Commercial | — | Built-in testing | Production |
| **Coalesce** | Source/columns | Column-aware GUI transforms; DV patterns | Proprietary → Snowflake et al. | Commercial | — | Pattern/tests | Production |
| **biGENIUS-X** | Source metadata | DWA, AI-assisted, metadata-driven | Proprietary, multi-platform | Commercial | — | Built-in | Production (DACH) |
| **Agnostic Data Labs** | Source-to-target mapping metadata (git-native) | Metadata + template-driven generation; non-opinionated (DV/ELM, Dimensional, Lakehouse) | Template-driven SQL, platform-agnostic | Free, closed-source | — | Metadata/schema validation | New; successor to the long-standing TEAM/VDW OSS line |
| **TurboVault Engine** (Scalefree, 2026) | A finished Data Vault metamodel (Excel/SQLite/JSON/IRiS workbooks); an MCP server lets a chat client write one | Template-driven generation (Django, Jinja); completeness validation; the modelling itself is left to the connected assistant, no modelling rules in the engine | dbt on datavault4dbt; SQLMesh on datavault4sqlmesh since 0.23.0 | AGPL-3.0, dual-licensed | `reasoning` free-text field, no record | Completeness and reference checks (hash key named, business key present, two hubs per link, a satellite's parent defined) | 0.24.0 on PyPI (2026-11-13), pre-MVP by its own rules file; the successor of TurboVault4dbt |
| **AutomateDV / datavault4dbt** | Hand-written staging metadata (YAML) | dbt macros/templates | dbt (you target the platform) | Open source | — | Macro contracts + dbt tests | Production (OSS) |
| **Academic LLM-for-DV** (MDPI, Preprints 2025) | Source schema / metadata | LLM (ChatGPT) + prompt engineering | Varies / conceptual | Research | — | Validity-coefficient research | Research / PoC |
| **Vault-Agent** (this project) | **Business requirements documents** (IREB-aligned) | **Multi-agent LLM** (LangGraph), rules-as-code | **AutomateDV / dbt** (open) | **Open source** | **Yes — one proposed ADR per run, each construct traced to its requirements** | **Independent validator gates + self-correcting loop** | Early; see [status and limits](status.md) |

(Cells left as "—" mean the capability is not a public, advertised feature of that tool, not that
it is impossible; some vendors are adding AI features quickly.)

## Update 2026-10-30 — TurboVault Engine (Scalefree)

Read at the repository on 2026-10-30.
Scalefree's `turbovault-engine` is the successor of TurboVault4dbt: a Django-based, CLI-first generator that
takes a **finished** Data Vault metamodel — hubs, links, satellites, PITs, prejoins, reference tables in Excel,
in a SQLite file that mirrors the Excel sheets, in its own JSON or in IRiS workbooks — validates it for
completeness and renders a dbt project on datavault4dbt. Created 2025-12-21, 0.21.0 on PyPI (2026-10-04),
AGPL-3.0 with a dual-licence offer, two main authors. Since 2026-04-29 it embeds an MCP server with ten tools
(`project_create`, `create_source_metadata`, `list_entities`, `commit_model`, `validate_model`, `generate_dbt`,
…) and documents it as „AI-assisted Data Vault modeling": an AI assistant is to propose the
model from table descriptions and write it in through `commit_model`. There is no proposal tool, no rule and no
gate on Data Vault semantics in the engine; the proposal schema has a free-text `reasoning` field. The
„database catalog" in its README is the SQLite mirror of the Excel format, not a source system's catalogue; the
`source_metadata` JSON format is the contract of a closed „TurboVault Studio" live-database connector, and the
source-metadata import is an open issue there.

What this changes in the map above: layer 1 now has a player that hands the modelling to an LLM **without**
rules — the opposite bet to this project's rules-as-code and measured gates — and it competes at the exit
(a dbt project for a Data Vault macro package) and in the DACH channel, where Scalefree's name, training and
reach are the real competition. It does not compete at the entry (requirements, business-key evidence, entity
resolution, data contracts, brownfield, the review queue, the ADR trail) nor on measurement. Its MCP import
schema is also an interface: a ratified model could be exported into it for datavault4dbt customers
(decided on 2026-10-31 in [ADR-0020](architecture/adrs/ADR-0020-turbovault-export.md): not now — and, should
a datavault4dbt customer ask, into its project JSON rather than the MCP schema).

## Update 2026-11-23 — TurboVault Engine at 0.24.0

Re-read at the repository at release 0.24.0 (changelog 2026-11-12), three releases after the reading above.
**New:** a second output — SQLMesh projects on datavault4sqlmesh beside dbt on datavault4dbt (0.23.0); a
configurable `dbt_project.yml` and an optional `profiles.yml` (0.22.0); pre-stages, dbt models that prepare a
table's data for its stage (0.24.0). A model can be exported as JSON, DBML or IRiS workbooks.
**Unchanged:** the MCP server has the same ten tools, and its generation tool writes dbt. The documented
validation checks completeness and references — a hash key named, a business key present, two hubs per link,
a satellite's parent defined, every referenced entity and source column present — and judges no modelling
choice. The repository's own rules file still places the engine in a pre-MVP phase; licence and the two main
authors are as before.

The assessment above stands, with one addition at the exit: the generator now serves two frameworks, where
this project generates for one macro package.

## Where Vault-Agent differentiates

Four things that are individually unremarkable but **rare in combination**:

1. **Requirements → model**, not schema → model. The incumbents start where a source already
   exists; Vault-Agent starts from the *business intent* (IREB-aligned parsing), addressing the
   slow, senior-architect-heavy front of the process.
2. **Transparent, agentic reasoning.** Every run ends in a proposed decision record that traces each
   construct to the requirements behind it; the validator is an independent gate; the modeler
   self-corrects against rule violations. The output shows *why* a construct exists, which matters
   for auditability in regulated DACH industries.
3. **Open stack, no lock-in.** Generation goes through AutomateDV/dbt, so the output is reviewable
   dbt code in git — reproducible, inspectable, and free of a proprietary runtime.
4. **Methodology depth + governance.** DV2.0 rules encoded as code (not prompts), data contracts
   for source-to-staging assets, and a human-in-the-loop checkpoint.

## Limitations — where the established tools are ahead

What has been measured, and what has not, is on the [status page](status.md). Against the
established tools:

- **Maturity & scale.** VaultSpeed/WhereScape run at billions of rows in production with support
  SLAs; Vault-Agent is an early, single-author project.
- **Breadth.** The commercial tools cover the full lifecycle (orchestration, monitoring, lineage
  UI, governance). Vault-Agent is focused on the modeling-and-generation front.
- **Reliability of LLM output.** Agentic data tooling is known to hallucinate (wrong joins, bad
  metadata) — which is exactly why the rules-as-code validator and human-in-the-loop exist, but it
  remains the central risk to manage and prove.

## What follows

- Automating Data Vault is not the contribution — that exists, and it is mature. The contribution
  is the combination: **requirements as the entry point, a visible reasoning trail, an open stack
  and the methodology as code**.
- The field is converging: vendors add AI features and academic prototypes multiply. What is
  scarce in public is a reproducible end-to-end example — which is why the demo, its inputs and
  the measured limits ship with the repository.
- Comparable prototypes probably exist inside consultancies and are not published; this page can
  only map what is public.

## Sources

- [Top 12 Data Warehouse Automation Tools 2025 — Streamkap](https://streamkap.com/resources-and-guides/data-warehouse-automation-tools)
- [VaultSpeed — Data Vault 2.0 Automation Platform](https://www.vaultspeed.com/platform)
- [WhereScape — Data Vault Express](https://www.wherescape.com/solutions/automation-software/data-vault-express/)
- [Datavault Builder / DV automation tools overview — bitool.net](https://www.bitool.net/data-vault-tools.html)
- [Scalefree — Automation Options for Data Vault](https://www.scalefree.com/knowledge/webinars/data-vault-friday/automation-options-for-data-vault/)
- [MDPI — Enabling Intelligent Data Modeling with AI: A Data Vault Case Study (2025)](https://www.mdpi.com/2079-8954/13/9/811)
- [Preprints.org — AI-Powered Data Vault 2.0 Modeling (2025)](https://www.preprints.org/manuscript/202502.2012)
- [Agnostic Data Labs](https://agnosticdatalabs.com)
- [dbt Developer Blog — dbt Agent Skills](https://docs.getdbt.com/blog/dbt-agent-skills)
- [ScalefreeCOM/turbovault-engine — GitHub](https://github.com/ScalefreeCOM/turbovault-engine) (read 2026-10-30 and 2026-11-23)
- [turbovault-engine — PyPI](https://pypi.org/project/turbovault-engine/)
- [Datavault-UK/automate-dv — GitHub](https://github.com/Datavault-UK/automate-dv)
- [AutomateDV — Platform Support](https://automate-dv.readthedocs.io/en/latest/platform_support/)
