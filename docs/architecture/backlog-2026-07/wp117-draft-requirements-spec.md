---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP117 — `vault-agent draft-requirements`: the catalogue drafted into a document a human corrects (ADR-0019, C1, C27 stage 4)

Status: **Approved and in progress** (2026-10-31, ADR-0019 accepted by the owner the same day) · Owner: Mischa
Eismann · Author: Claude. Builds what ADR-0019 decides; the experiment's instrument
(`eval/adventureworks/draft_requirements.py`, 2026-10-30) is promoted, not rewritten.

## 1 What is built

1. **A command, not a mode** (ADR rule 1). `vault-agent draft-requirements --source-schema FILE --out FILE
   [--area NAME] [--technical COLUMN …]` reads the house format (`load_source_schemas`, the file `run
   --source-schema` reads) and writes one Markdown document; `run`, the workbench and the pipeline are unchanged,
   the document enters where every document enters. `--area` names the subject area in the title (default: the one
   schema the tables share, else `source`); `--technical` names columns stated once per entity as technical, never as
   attributes (the eval passes AdventureWorks' `ModifiedDate` and `rowguid`; a column of a GUID type is technical
   without being named). A schema that does not load is an attributable error before anything is written, exit 1.
2. **Deterministic and keyless; the experiment's rules promoted** (ADR rule 2). `src/vault_agent/draft_requirements.py`
   owns them, typed on `SourceTable`: a table is a *relationship* when two or more foreign keys cover its primary key,
   a *subtype* when exactly one does, else an *entity* identified by its single-column declared unique key where one
   exists, else by its primary key; columns in words, never by physical name; one requirement per described column,
   the undescribed in one, one per foreign key, the table's and the columns' comments verbatim; no sentence the
   catalogue did not say. The one rule the house format needs that the extract did not: **a unique key on a column of
   a GUID type (`uniqueidentifier`, `uuid` — the type, never the name) is not an identifier.** The eval's module
   delegates to it — `draft(extract, schema)` builds the house-format tables of the area and calls the product — so
   the six `adventureworks_drafted_*` documents regenerate from the product, byte-identically in their body; their
   leading comment becomes the typed header (deliberately, in this WP's commit, the C1 experiment's documents as run
   are in the kept outputs and the memo).
3. **Marked as a draft, and the mark is typed** (ADR rule 3). The document opens with an HTML comment the code reads:
   `vault-agent: drafted-from-catalogue`, `source:`, `date:`, `status: unreviewed`; `read_draft_header(text)` returns
   it typed or `None`. The human corrects the document and sets `status: reviewed`. The requirements parser reads the
   header of every document it extracts and raises `requirements_unreviewed` (a `FlagKind`, a **decision** — one
   item per document, so a skipped correction stands above the fold, never a refusal) while the status is
   `unreviewed`; a reviewed draft and an authored document raise nothing. The proposed ADR names the provenance
   beside the document (typed: the flag's kind and asset, never the text).
4. **What the draft does not read** (ADR rule 4): inferred keys, profiling, nullability — unchanged.

## 2 Acceptance (keyless)

`tests/test_wp117_draft_requirements.py`, red before the change: the header's round trip and absence; the
classification and the identifier rules on miniature tables, the GUID rule by type; the five area documents equal to
the product's output from each case's own `source_schema.yml` (after this WP's regeneration) and to the eval module's
delegating `draft`; the parser's flag on an unreviewed draft and its absence on a reviewed one and on an authored
document; the ADR's provenance line; the command writing the file and refusing a bad schema with exit 1; the roles
table classifying the new kind (WP43's guard). Byte-identity fixtures untouched.

## 3 Pre-registration

- **P1 — keyless.** Guards green; the regenerated six documents differ from the committed ones **only in the leading
  comment** (a diff over the files, recorded); suite, ruff, bare mypy green.
- **P2 — the product on a catalogue the eval never saw.** The bank demo's `examples/inputs/bank_source_schema.yml`
  drafts to a document whose entities are the four bank tables, with `raw_account_customer` a relationship if its
  primary key is covered by two foreign keys and an entity otherwise — stated from the file before the run, the
  document's requirement count recorded.
- **P3 — no change elsewhere.** A `run` on an authored document raises no `requirements_unreviewed` flag (the
  parser guard); the review record is untouched (no chain ran).

## 4 Not in scope

A corrected draft's effect on the model and the review load (ADR rule 5 — the owner's measurement; after WP116 it
measures scope, not review); the workbench offering the command (a file of kind `requirements` can be uploaded as
today); LLM prose; a `--draft` flag on `run`.
