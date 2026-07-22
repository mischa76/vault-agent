# 1. Introduction

## 1.1 What vault-agent is

Vault-agent is a multi-agent pipeline that turns a business requirements document into a
validated Data Vault 2.0 model and a runnable dbt project. You give it a requirements
document (Markdown, plain text, PDF, or Word), optionally a declared source schema and
profiling evidence, and it produces hubs, links, and satellites as AutomateDV-backed dbt
models — including the staging layer, data contracts for the source assets, a review
queue for human sign-off, and an Architecture Decision Record explaining what was
modelled and why. The output builds on a real warehouse: the reference verification runs
on PostgreSQL 16, and any AutomateDV-supported platform (Snowflake, BigQuery,
Databricks, MS SQL Server, PostgreSQL) is a valid target.

The design conviction behind it: the slow, unforgiving part of Data Vault work — key
identification, construct selection, loading logic — is automatable, but the *judgment*
is not. Every run therefore ends in front of a human. The pipeline proposes, flags what
it could not determine, and pauses for ratification; it never silently guesses. Where
the model made a decision that shapes the vault (a driving key, a satellite split, a
source mapping), that decision is captured for review rather than buried in generated
SQL.

Two properties matter for trusting the output. First, the methodology rules live in
code, not in prompts: a deterministic validator with stable E_/W_ codes (chapter 8)
gates every model against the Linstedt/Olschimke canon before any SQL ships, so
conformance is checkable and independent of which LLM produced the proposal. Second,
code generation goes exclusively through the established AutomateDV package — the
pipeline emits configuration for battle-tested macros, never hand-written loading SQL.

## 1.2 What vault-agent is not

It is not a general-purpose modeling tool: it models Raw Vault constructs. Business
Vault logic and mart semantics are deliberately out of automation scope (ADR-0007) —
where the pipeline detects that something belongs there (a derived KPI, a computed
effective-dating), it flags a gap for human design instead of inventing a source.

It is not a replacement for a data architect. The human-in-the-loop checkpoint is not a
formality: validation errors and unassigned contract owners block finalization by
design, and mapping ratification (chapter 7) assumes a source-literate reviewer. The
honest self-description in the mapper's own prompt applies to the whole system: *this is
an ASSIST step; a human ratifies the output.*

It is also not an interactive chat tool. A run is a batch pipeline with one
well-defined pause point; steering happens through inputs (requirements, schema,
profiling) and the checkpoint decisions, not through conversation.

## 1.3 How to read this manual

For a **first run**, read chapters 4 (installation), 6 (running), and 9 (building the
output on a warehouse) — the demos in 9.5 are the fastest way to see a healthy end
state. To **understand and judge an output**, read chapters 2 (concepts), 7
(checkpoint), and 8 (gates) — in that order; the review queue makes little sense
without the vocabulary. When something **goes wrong**, start with chapter 12
(troubleshooting) and escalate to chapter 10 (traces) when the symptom points at an LLM
decision. **Maintainers** — anyone bumping a model version or editing prompts — need
chapter 11.

## 1.4 Related documentation

The repo README covers positioning and a quick start; `docs/demos/` holds two guided
walkthroughs (bank, health insurance). `docs/methodology/` contains the DV2.0 rules
cheatsheet (the canon behind chapter 8), the DSAF and IREB mappings, and the LOOPS.md
mapping that explains the harness philosophy referenced in chapters 8 and 11.
`docs/architecture/` holds the ADRs and the work-package specs this manual cites by
number (WP*n*); when the manual and a spec disagree, the spec — and ultimately the
code — wins.
