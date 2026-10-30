---
type: spec
status: not-measured
updated: 2026-10-30
---

# WP97 — A table's own comment in the house format: read from the catalogue, carried by the derivation, shown where column comments are shown (C31)

Status: **Approved and in progress** (2026-10-30, the owner's go for C31) · Owner: Mischa Eismann · Author: Claude.
Backlog C31 (`backlog-2026-10-candidates-3.md`, found by WP96). Builds on the house format (`SourceTable`, WP9 §3.1),
the catalogue reader (WP96, ADR-0017) and the derivation (`eval/adventureworks/derive.py`).

## 1 What is wrong, in one paragraph

A source catalogue states a description per table — AdventureWorks has one on 66 of 68 tables, verbatim in the
extract; PostgreSQL keeps it in `pg_description` with `objsubid = 0`, SQL Server as `MS_Description` on the table,
Oracle in `ALL_TAB_COMMENTS` — and the house format has no field for it. The derivation drops it, WP96's reader
reads it from no catalogue because there is nowhere to put it, and the two agents that read column comments as
evidence (the entity resolver's and the source mapper's payloads) see a table only by its name. Where the name is
cryptic (the SAP case of C27 tier C in miniature: `KNA1`, `VBAK`) the table's description is the one line that says
what the table is.

## 2 The rules

1. **One field, verbatim.** `SourceTable.comment: str | None`, default `None`. The loader accepts `comment:` on a
   table entry; the catalogue reader transcribes the catalogue's table comment unchanged (whitespace kept, as for
   column comments); the derivation carries the extract's table description where Microsoft wrote one. Never
   authored, never normalised at rest.
2. **Shown where column comments are shown, and nowhere else.** Column comments reach two model inputs today: the
   entity resolver's payload and the source mapper's payload (WP9 §3.1, WP32). The table comment reaches the same
   two, as a `source_tables` list of `{table, comment}` entries (whitespace collapsed, as the column comments are
   there), present only when at least one table has a comment. It does **not** reach `render_schema_prompt_section`
   — the business-key, contract and modeler prompts — because column comments do not either and because a change
   to the modeler's input is a measured change (WP34 §3.8's rule, the WP30.2 lesson): if the owner wants the modeler
   to read it, that is a WP of its own with a live run, and the guard here is updated deliberately. The carried
   catalogue (`dump_source_catalogue`, WP74) carries no comments and stays byte-identical.
3. **Inert when absent.** A table without a comment renders, loads, dumps and prompts exactly as before: no
   `comment` key in the written file, no `source_tables` key in either payload, every existing fixture unchanged.
4. **The reader's protocol grows by one method.** `CatalogueReader.table_comment(table, schema) -> str | None`;
   `NotImplementedError` (SQLite) is „no comment", as for the other optional facts. `InspectorReader` reads
   `Inspector.get_table_comment(...)["text"]` (`sqlalchemy/engine/reflection.py` 1330, `ReflectedTableComment` in
   `engine/interfaces.py` 566; the PostgreSQL dialect answers from `pg_description`, `dialects/postgresql/base.py`
   5606). In the written file the key sits after `schema`/`database` and before `columns`.

## 3 Not this WP

Rendering the table comment to the modeler, the business-key identifier or the contract agent (rule 2). A table
comment as evidence in the mapper's offer tier or the resolver's category (`comment_grounded` reads column comments;
unchanged). Carrying it in the catalogue that travels with the model. The C31 text's claim that column comments are
rendered in „the grounding prompt, the contracts" was wrong — they are not — and this spec corrects it; the log
entry says so.

## 4 Pre-registration

- **P1** (keyless, the reader): a stub reader with a table comment → `SourceTable.comment` verbatim, whitespace
  kept; a stub that raises `NotImplementedError` → `None`; the SQLite fixture of WP96 → `None` on every table and
  no table-level `comment` key in the written file; a file written with a table comment loads back through the
  house loader with the comment equal; the key order in the file is `table, schema, [database,] comment, columns`.
  Red before the change (no field, no method).
- **P2** (keyless, the loader and the model): `comment:` on a table entry loads; a `SourceTable` built without it
  has `comment is None`; a dict without the key validates as before.
- **P3** (keyless, the two payloads and the three inert surfaces): the entity resolver's payload and the source
  mapper's payload carry `source_tables: [{table, comment}]` exactly for the tables with a comment, whitespace
  collapsed, and carry no such key when no table has one; `render_schema_prompt_section` and
  `dump_source_catalogue` are byte-identical with and without table comments, and the comment's text appears in
  neither. Red before (the payloads lack the key).
- **P4** (keyless, the derivation): `build_source_schema` carries the extract's table description; over the five
  subject areas 66 tables carry one and 2 (`Production.Document`, `Production.ProductDocument` — whichever two the
  extract has blank; counted, not assumed) carry none; the six dataset files, regenerated, agree with the extract
  table by table (the existing verbatim guard extended to tables). Red before.
- **P5** (local PostgreSQL 16, by hand): the DDL instrument's database `aw_ddl` rebuilt; `vault-agent
  source-schema` on its five schemas reads 66 table comments equal to the extract's, `None` on the other two; two
  reads byte-identical; the file loads.

## 5 Guards

`tests/test_wp97_table_comment.py` (P1–P4), committed red before the change, together with the extension of
`tests/test_adventureworks.py::test_comments_are_verbatim_and_never_authored` to table comments (deliberate update
of an existing guard, red until the datasets are regenerated). WP96's `_StubReader` gains the new method with the
change, because the protocol grows (same commit, said in the message). P5 is run by hand and recorded in
`docs/log.md`.
