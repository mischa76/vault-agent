---
type: spec
status: not-measured
updated: 2026-11-16
---

# WP140 — Keys are inferred from the workbench, and the checkpoint shows an inferred key as what it is (C74)

Status: **Approved and in progress** (2026-11-16, on the owner's decision of that day: of C74's options the
third, as an action a human starts, not an automatic one) · Owner: Mischa Eismann · Author: Claude. Candidate
C74. The owner asked for one check first — whether the workbench's checkpoint can take the single yes an
inferred key needs. It can, and it shows the key wrongly (§1.2); that is repaired here.

## 1 What is wrong

C74: a link takes a hub that no key of its relation leads to — `WorkOrderRouting` carries `ProductID`, the
catalogue declares no foreign key to `Product`, the modeler takes `hub_product` into the link all the same.
Since WP136 the product has a complete path for that case: `vault-agent infer-keys` finds the key in the data,
the resolution checkpoint asks, a yes binds the link and licenses the translation, and the project builds
without a hand view (WP136 P5). Two things keep a workbench user from that path.

1. **The command exists on the command line only.** The workbench reads the catalogue and makes the profile
   (WP119); it cannot infer keys. A user has to leave it, know that the command exists and that it has to run
   before the run, and upload the file it writes. The disclosure `link_key_missing` (WP136) names the command
   — after the run.
2. **The checkpoint shows an inferred key as allowed and declines it.** Read in the code, then pinned by a
   guard (§4 G6): the Review perspective lists every pending proposal under „Declared keys — … proposed from
   the source's own foreign keys" with its box checked („allow" / „build"), and sends an answer only for a box
   someone touched. An inferred key is declined by the bulk answer unless a human names it (ADR-0018 §4,
   `apply_link_decision`). So an inferred licence stands on the screen as „allow" and is declined; to accept
   it a user has to clear the box and set it again. The API's entry carries the provenance only as the first
   words of a note, no typed field.

## 2 The rules

1. **One core, two callers** — WP119's rule, for the third producer. The body of `vault-agent infer-keys`
   moves into `key_inference.produce_inferred_keys(url, schema_file, *, candidates)`: the file text, the
   counts and the warnings, typed refusals (`SourceDriverMissingError`, `SourceUnreachableError`). The command
   keeps its exit codes and messages; the workbench maps the types to statuses.
2. **The route.** `POST /api/projects/{id}/infer-keys {schema, name, candidates, reads_rows}` — `schema`
   names a schema input of the project, `name` the file to write (default: the same file, as the manual's
   example writes it), `candidates` the tier (default `name`). The file is stored as a schema input through
   the store's own path and is **byte-identical to the command's** for the same arguments; the entry records
   that command, without a URL. **`reads_rows` must be `true`** or the answer is 422 — the command reads
   rows, and the request acknowledges it as the profile's does (ADR-0008 #4: an explicitly invoked,
   read-only, scoped step). The answer carries what the database refused or did not hold (WP139's warnings,
   collected). Statuses as WP119: source unset 409, driver missing or unreachable 502 without a password,
   unknown project or input 404, an input that is no schema 422.
3. **The section.** In „Source", beside the catalogue and the profile: „infer keys" with a choice among the
   project's schema inputs, the file name, and a confirmation that says rows are read before the request goes
   out. The name tier only; the type tier stays the command's (never measured against real data). The file
   it writes is handed to the run form as the schema input.
4. **The checkpoint says what a key is.** The API's entry for a pending proposal gains the typed field
   `provenance` (`declared` | `inferred`). The Review perspective shows inferred keys in a section of their
   own, **unchecked — declined, as the bulk answer declines them** — and a checked one is sent as the yes
   (`--link`). Declared proposals are shown and sent as before.

**Unchanged.** The pipeline holds no connection (ADR-0008 #4; ADR-0015: the URL from the workbench's
environment, never a password in an answer). The inference itself, the proposer, the orchestrator's rule for
the bulk answer. A run started without inferred keys: nothing differs; no byte-identity fixture moves.

## 3 Not built

- **Nothing automatic.** The workbench does not infer keys when a catalogue is read or a run starts — that
  would read rows without anyone asking for it, and needs the owner's amendment of ADR-0008 #4. C74's text
  said option (c) touches that decision; the explicit action does not, the automatic one would.
- **No gate** (C74's option (b)): the link is not refused. `ProductID` is part of `WorkOrderRouting`'s primary
  key; the link is one the data carries, and what is missing is in the catalogue.
- **The shipped demo is not regenerated** — a paid chain, with one yes at a checkpoint; the owner's.
- **No progress or cancel** for a long inference: synchronous, as the profile (WP119 §3).

## 4 Acceptance (keyless)

`tests/test_wp140_infer_keys_in_workbench.py` and two Vitest files, committed red before the change:

- **G1** the route writes the command's file: the catalogue read through the workbench, keys inferred into a
  second file — byte-identical to `vault-agent infer-keys` over the same input; kind `schema`; the command
  recorded; the counts in the answer. Without `name` the input is replaced.
- **G2** without `reads_rows: true` → 422 and no file written or changed.
- **G3** refusals: source unset 409; unknown project 404; an input the project does not hold 404; a
  requirements file 422; an unknown tier 422; an unreachable source 502 and no password in the answer.
- **G4** a column the database refuses is named in the answer, the rest of its table inferred (WP139, through
  the route).
- **G5** the pending list carries `provenance` for a declared proposal, an inferred licence and a
  relationship table.
- **G6** (Vitest, `Review.test.tsx`) an inferred licence is shown unchecked in a section of its own; ratifying
  sends no yes for it; checking it sends `links: {key: true}`. The declared licence beside it stays checked.
- **G7** (Vitest, `Source.test.tsx`) „infer keys" offers the project's schema inputs, asks before the row
  read, posts the choice with `reads_rows: true`.
- **G8** WP99's command tests unchanged and green — the refactor keeps exit codes and messages.

## 5 Pre-registration

- **P1** G1–G8: red before (the Python guards by the missing route and field, G6 by the checked box, G7 by the
  missing button), green after. Suite with no key reachable, ruff, bare mypy; `tsc`, Vitest, the build.
  `vault_agent.ui` coverage at or above CI's floor.
- **P2** (local PostgreSQL, by hand, read-only): the route over the full AdventureWorks catalogue against the
  data copy writes the file the command writes (`cmp`), and that file is WP139's — 68 of 68 tables read, 68
  inferred unique keys, 4 inferred foreign keys, the seven `xml` columns in the answer's `refused`.
- **P3** (zero cost, the stored chain): the pending list of the production step read with that file carries
  2 entries of provenance `inferred`, one of them `WorkOrderRouting.productid`; every other entry `declared`.
- **P4** the Source section in a real browser against the data copy, if the browser the end-to-end walk uses
  is installed here; otherwise recorded as not done.
- **Not predicted:** how long the inference takes through the workbench on a large source.

No paid run: nothing here touches a model call. That a human finds the action and gives the yes in a live
chain is the next chain's to show.

## 6 Measured (2026-11-16)

No model call. Evidence: `eval/results/kept-outputs/wp140-20261116/`.

- **P1 held.** Six Python guards and four Vitest cases red at `683b3de`, green with the change; WP99's command
  tests, WP119's and WP139's guards unchanged and green. Suite 1865 passed, 3 skipped with no key reachable;
  `ruff check --no-cache` and a bare `mypy` clean; `tsc` clean, Vitest 47 passed, the bundle built;
  `vault_agent.ui` coverage 95 % locally (floor 85). No byte-identity fixture changed. **One guard was wrong as
  committed:** G4 expected no inferred unique key beside the refused column; `Product.Name` is one with or
  without the refusal. The number was corrected with the change (1), the assertion's point — the table of the
  refused column is still read — is the inferred reference from it.
- **P2 held.** The route over the full AdventureWorks catalogue against the data copy (PostgreSQL,
  read-only): 422 without `reads_rows`, then 201 in 3.5 s — 68 of 68 tables read, 68 inferred unique keys, 4
  inferred foreign keys, the seven `xml` columns in `refused`. The file equals the command's byte for byte
  and, with the connection masked on both, WP139's kept file.
- **P3 held.** The API's pending list over the five steps of the second chain of 2026-11-15, each increment
  read with that file: 13, 7, 30, 12 and 42 entries; the two of provenance `inferred` are in the production
  step (`TransactionHistoryArchive.productid`, `WorkOrderRouting.productid`). What the page sends, applied by
  the real `apply_link_decision`: nothing for an untouched box — both declined, the 28 declared accepted; a
  check on `WorkOrderRouting.productid` — that one accepted, the other declined.
- **P4 done.** A real Chromium against the built bundle, the data copy and stub agents (every agent that
  calls a model stubbed; orchestrator, link proposer and both checkpoints real): „infer keys" disabled while
  the project holds no schema input; the Production catalogue read (25 tables, 28 declared foreign keys);
  the confirmation shown; 25 of 25 tables read, 13 inferred unique keys, 2 inferred foreign keys, three `xml`
  columns named, 1.4 s; the run paused at the resolution checkpoint with 27 boxes checked under „Declared
  keys" and the two inferred ones unchecked in their own section; after one check the button read „Ratify
  the rest, allow 1 inferred, and build the model" and the run recorded `resume … --link
  WorkOrderRouting.productid --accept`.
- **Seen on the way, in a real browser only:** a button inside a folded `<details>` has no accessible role
  until the block is opened — jsdom finds it either way; the walk opens the block first, as a user does.
- **Not measured.** A live chain in which a human finds the action and gives the yes; the time on a large
  source; the page with many inferred keys or on a small viewport; a database other than PostgreSQL and
  SQLite.
