---
type: spec
status: measured
updated: 2026-11-07
---

# WP119 — The source database in the workbench: read the catalogue, make the profile (C46)

Status: **Approved and in progress** (2026-11-07, on the owner's go to continue with C46) · Owner: Mischa Eismann ·
Author: Claude. Candidate C46 (`backlog-2026-11-candidates.md`, 2026-11-05), its question (a) read against ADR-0015 on
2026-11-06.

## 1 What is missing

The two producers of C27 — `vault-agent source-schema` (WP96, metadata only) and `vault-agent profile` (WP98, reads
rows; ADR-0008 #4's explicitly invoked, read-only, scoped step) — exist only on the command line. A workbench user has
to leave it, run a command with the right schemas, tables and checks, and upload the file through „attach schema" /
„attach profiling". Both specs deferred the workbench on purpose (WP96: „a catalogue step in the workbench is a later
increment under ADR-0015"); this is that increment.

## 2 The rules

1. **The connection stays in the environment** (ADR-0015, Option C: „secrets in the operator's `.env`"; reading of
   2026-11-06). The workbench reads `VAULT_AGENT_SOURCE_URL` from its own process and nowhere else: no request body,
   no project file and no response ever carries a password. What it shows is the URL as `hidden_url` renders it, or
   „not set". A per-project URL is not this WP (§3).
2. **One core, two callers.** The CLI bodies of `source-schema` and `profile` move into two functions —
   `source_schema_reader.produce_source_schema(url, schemas, *, views)` and `profiler.produce_profiling(url, schemas,
   tables, *, checks, sample, examples)` — returning the file text, a summary and the warnings, and raising typed
   errors (`SourceDriverMissing`, `SourceUnreachable`, `UnknownSchemas` with the catalogue's list, `UnknownTables`,
   `UnknownChecks`). The CLI maps the types to its exit codes and messages, unchanged; the API maps them to statuses.
   Neither caller branches on a message. The check-list resolution (`all`, `none`, `--examples` implying the check)
   moves with it, so both callers resolve the same way.
3. **Byte-identity.** For the same arguments the workbench writes the byte-identical file the command writes (the
   header carries no timestamp, by WP96/WP98 design). The project file records the command that reproduces it — with
   `--schema`, `--table`, `--check`, `--sample`, `--examples`, `--views` and `--out inputs/<name>`, and no `--url`:
   the command takes the same environment variable.
4. **The routes.**
   - `GET /api/source` — `{state, url, dialect, schemas}`: `state` is a typed field, `unset` | `ok` |
     `driver_missing` | `unreachable`, with `detail` (password removed) for the last two; `schemas` the catalogue's
     list when `ok`. Never a 5xx for a source that is not there.
   - `GET /api/source/tables?schema=…` (repeatable) — the `(schema, table)` pairs `select_tables` sees.
   - `POST /api/projects/{id}/source-schema {schemas, views, name}` — reads the catalogue, stores the file as a
     project input of kind `schema` through the store's existing path (so the house loader validates it as an upload
     is validated), returns the file entry, the summary, the warnings and the command.
   - `POST /api/projects/{id}/profile {schemas, tables, checks, sample, examples, name, reads_rows}` — the same for kind
     `profiling`. **`reads_rows` must be `true`** or the answer is 422: the row read is acknowledged in the request,
     not only in a dialog. The answer names every column the database refused (WP98's `warn`, collected, not printed).
   - Status mapping: source unset 409, driver missing or unreachable 502 with the detail, unknown schema/table/check
     422 naming what the catalogue holds, unknown project 404 (C44's type).
5. **The section.** A „Source" section in the Project perspective, above Inputs: the URL (hidden) or how to set it;
   „read catalogue" with a schema choice from the catalogue and a views toggle; „make profile" with a schema and table
   choice, the checks as toggles (`examples` off, marked as the one check that writes values), the sample size, and a
   confirmation that names what is read before the request goes out. The answer's command is shown under the file it
   wrote. Buttons follow the existing kinds (C45 is separate).

## 3 Not this WP

A per-project connection (a URL without password per project, the password from the environment) — the next step if
an engagement has several sources; it needs a rule for which variable carries which password. A password entered in
the browser — would need an amendment of ADR-0015. Progress and cancel for long profiles: the request is synchronous
(FastAPI's thread pool), as long as the command; WP68/WP69's run machinery is for runs. The button kinds (C45). SAP's
reader (C27 tier C). Requirements drafted from the catalogue (WP117 exists; not wired here).

## 4 Acceptance (keyless, SQLite as in WP96/WP98)

`tests/test_wp119_source_in_workbench.py`, committed red (import) before the change:
- **G1** `GET /api/source` with the variable unset → `state: unset`, no 5xx; with a SQLite URL → `ok` and the
  catalogue's schemas; with an unknown driver → `driver_missing`; the response body never contains a password (a URL
  with `user:secret@` set in the environment, `secret` absent from every response of the module's tests).
- **G2** `POST …/source-schema` writes `inputs/<name>`, byte-identical to `vault-agent source-schema` with the same
  arguments, listed as kind `schema`, its command recorded; an unknown schema → 422 naming the catalogue's schemas;
  variable unset → 409.
- **G3** `POST …/profile` byte-identical to `vault-agent profile` for the same schemas, tables, checks, sample and
  examples; without `reads_rows: true` → 422 and no file; a refused column named in the answer; unknown table or
  check → 422.
- **G4** The existing WP96 and WP98 CLI tests unchanged and green — the refactor keeps exit codes and messages.
- **G5** `Project.test.tsx`: the section shows `not set` from the API; with a catalogue, the schema choice comes from
  it, „read catalogue" posts the chosen schemas, „make profile" asks for confirmation and posts `reads_rows: true`.

## 5 Pre-registration

- **P1** G1–G5 green; the whole suite green with no key reachable (DoD); ruff, bare mypy; `tsc`, `vitest`.
- **P2** Byte-identity holds for both producers on the SQLite fixture (G2, G3) — the claim is keyless and SQLite-only;
  PostgreSQL is checked by hand once on vault-dev's AdventureWorks copy (`person` schema, catalogue and a one-table
  profile) and recorded as such, or recorded as not done.
- **P3** No password in any response, file or recorded command (G1's sweep).
- **P4** `vault_agent.ui` coverage stays at or above CI's floor of 85; the manual's chapter 14 (API table, the
  section) and chapter 6.1 (the workbench as a second caller) gain their rows in the same commit as the code.
- **Not predicted:** the time a large profile takes through the workbench.

## 6 Measured

Appended after the run.

## 6 Measured (2026-11-07, keyless)

- **P1 ✔.** G1–G4: 11 Python guards green (`tests/test_wp119_source_in_workbench.py`, red by import at `37b2813`);
  G5: 3 Vitest cases green (`Source.test.tsx`, red by import at `da838e7`). Whole suite with no key reachable (the
  worktree has no `.env`, `ANTHROPIC_API_KEY` unset): 1618 passed, 6 skipped; `ruff check --no-cache` clean; bare
  `mypy` clean (70 files); `tsc --noEmit` clean; `vitest run` 37 passed; `npm run build` built.
- **P2 ✔ on SQLite, PostgreSQL not done.** Byte-identity holds for both producers against the commands on the SQLite
  fixture (G2, G3). The hand check on vault-dev's PostgreSQL copy was not made: the session had no source URL for
  it (none in the checkout's `.env`), and looking for the database password was not pursued. Open for the owner:
  `VAULT_AGENT_SOURCE_URL` set in the workbench's `.env`, the Source section read once against the `person` schema
  and one table profiled, both files compared with the commands' (`cmp`).
- **P3 ✔.** No password in any answer: G1's sweep with a URL carrying `reader:secret@` over all four routes; the
  recorded commands carry no `--url`. The driver-missing answer shows the URL as `hidden_url` renders it.
- **P4 ✔ locally, CI pending.** `vault_agent.ui` coverage 95 % locally (floor 85); manual 6 (the workbench as the
  second caller of both commands) and 14.2 (two route rows, the Source section) in `efdf013`.
- **Deviations from §2, recorded:** the error types carry the house's `Error` suffix (`SourceDriverMissingError`,
  `SourceUnreachableError`, `UnknownSchemasError`, `UnknownTablesError`, `UnknownChecksError`; ruff N818), and the
  project's file entry carries `command` (rule 3 said the project records it; G2 was updated to expect it in the
  same commit). **Found on the way:** an unknown `--table` answered „The schemas hold: nothing" — the command listed
  the tables that matched, not those the schemas hold; both callers now list what the schemas hold.
- **Not predicted, not measured:** the time a large profile takes through the workbench.

## 7 Correction (2026-11-07) — `.env` did not reach the lookup; G6

Found before the first live use, when the owner asked for the workbench to be started on PostgreSQL: §2 rule 1 and
manual 6 say the URL lives in `.env`, but the routes (and the three commands before them) read `os.environ` only.
`config.Settings` reads `.env` for its own fields; `VAULT_AGENT_SOURCE_URL` is none of them, so a URL in the file
answered `state: unset` (reproduced with a `.env` in a temporary working directory). G6 committed red (`d02bbae`), then
`config.source_url_from_environment()` — the process environment first, then `.env` in the working directory —
used by the four routes and by `source-schema`, `infer-keys` and `profile`. Suite 1620 passed / 5 skipped with no key
reachable; ruff, bare mypy clean. §6's P3 is unaffected; its claim „the workbench reads `.env`" was untrue until this
commit.
