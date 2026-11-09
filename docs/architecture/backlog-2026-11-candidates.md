---
type: backlog
status: proposed
updated: 2026-11-05
---

# Backlog candidates of November 2026

Status: **Proposed, not prioritised** (2026-11-05) · Owner: Mischa Eismann · Author: Claude.
Continues `backlog-2026-10-candidates-3.md` (C22–C44, all closed per its status note of 2026-11-05), append-only.
„C" stands for *candidate*: a finding or idea, not yet a work package.

## C45 — The workbench has three button kinds and no rule for when to use which; the „attach" controls do not read as buttons (owner, 2026-11-05)

**Observed by the owner** in the Project perspective, section Inputs: the three controls „attach requirements",
„attach schema", „attach profiling" are not recognisable at a glance as buttons; they disappear among the file rows
above them (mono file names, grey pills, the small bordered `delete` per file). Asked whether a concept governs when
a button looks like „Run the generator" (filled orange), like „delete project" (orange-red text and border) or like
the attach controls (grey border, white text).

**Read in the code (`frontend/src`, 2026-11-05, `1314107`):** `components/ui.tsx` `Button` has three kinds —
`primary` (`bg-accent text-bg`, filled, `--color-accent` #d97757), `danger` (`border-bad text-bad`, `--color-bad`
#e06c5b), `ghost` (`border-line text-ink`, the default text colour). Usage implies a rule — primary for the one action a
perspective exists for (Run the generator), danger for anything that destroys, ghost for the rest — but **it is
written down nowhere** (not in `docs/operations/14-workbench.md`, no ADR, no comment). The attach controls are not
`Button` at all: a hand-written `<label>` around a hidden file input (`perspectives/Project.tsx`, the Inputs
section), `border-line text-sm`, without `font-medium` — visually one step below ghost, and of the same family as
the per-file `delete` buttons and the pills, which is why they sink. Two more things seen on the way: `danger` and
`accent` differ little in hue (#e06c5b vs #d97757), so the owner reads delete as orange too; and the per-file and
per-run `delete` are bordered grey, not `danger`.

**Shape of a WP:** (1) write the rule — one short paragraph in the workbench chapter: primary at most once per
perspective, the step that moves the project forward; danger for every destructive action, at every size; a
secondary kind for actions that add something (attach, parse, record); ghost for navigation and toggles; (2) give
the attach controls that secondary look — e.g. accent outline or `accent-soft` fill, with an icon or „+" — through
`Button` (it needs an `as="label"` or a file-input variant so the hidden input keeps working); (3) decide whether
`danger` gets a hue clearly apart from the accent; (4) the per-file/per-run `delete` follow the rule. Guard first:
the existing `Project.test.tsx` queries by role and name (`getByRole("button", …)`); the attach controls are found
by `aria-label` on the input, which must survive the change.

## C46 — Reading the source catalogue and profiling from the workbench (owner, 2026-11-05)

**Asked by the owner** while driving the twenty-fourth chain: where in the workbench is the connection to the source
database configured, the catalogue read and the profile made — including the choice of what goes into the profile?
**Answer read in the repo (2026-11-05, `c8fd28c`): nowhere in the workbench.** Both producers are CLI commands only —
`vault-agent source-schema` (WP96, C27 stage 1: metadata, no row) and `vault-agent profile` (WP98, C27 stage 2: reads
rows; ADR-0008 #4's explicitly invoked, read-only, scoped step, note of 2026-10-30). The connection is
`VAULT_AGENT_SOURCE_URL` (manual 5, „the place for the password") or `--url`. The profile's scope is `--schema`,
`--table`, `--check` (range, lengths, patterns by default; examples; all; none), `--sample` (10 000) and `--examples`
(0). The workbench only takes the resulting files through „attach schema" / „attach profiling". The omission was
deliberate and recorded only in the two specs' „not done" lists: WP96 — „a catalogue step in the workbench is a
later increment under ADR-0015"; WP98 — „The workbench". No candidate carried it until now.

**Shape of a WP:** a „Source" section in the Project perspective, above Inputs: (1) the connection — dialect and
host/database shown, the password **not** entered in the browser by default; (2) „read catalogue": schema choice
(the catalogue's schema list offered once connected), views on/off, writes the project's schema input as the CLI
would, the provenance header included; (3) „make profile": schema and table choice (from the read catalogue),
checks as toggles with `examples` off and marked as the one that writes values, sample size, writes the profiling
input; (4) every action recorded as its CLI equivalent like the rest of the workbench, the URL in it with the
password hidden (`hidden_url`).

**Open before a spec:** (a) **where the password lives.** Today's rule: in the environment or `.env`, never in a file
or a shell history; the API key follows the same rule in WP113's settings (`anthropic_api_key_set` as a boolean,
never the key). A browser field would break it — the candidate shapes are the environment variable only (the
section shows „set / not set", like the API key), a per-project URL without password plus the password from the
environment, or a secret store; the owner decides. (b) **Consent for row reads.** WP96's spec tied profiling to
consent and sampling in `deployment-residency.md`; a button makes a row read one click away, so the section has to
say what is read and confirm it. (c) ADR-0015 (single-user tool, Option C) — whether it already settles (a), read
before the spec. (d) Long profiles: the CLI blocks; the workbench needs the run-style progress and cancel
(WP68/WP69) or a limit. Guard: the CLI's outputs for the same arguments as the byte-identity reference — the
workbench must write the same files the commands write.

**C46 (a) read against ADR-0015 (2026-11-06).** ADR-0015 does not name a source-database password, but it settles
the principle: its context lists „Secrets (the Anthropic key, Bedrock/Vertex credentials) are read from the
operator's `.env`", and the consequences of the accepted Option C say „Security stays simple: no listener beyond
`127.0.0.1`, secrets in the operator's `.env`". A second argument comes from the same ADR: the output is handed over
as a project in the customer's git, and WP92 made project folders relocatable for handover — a password stored per
project would travel with it. So, under ADR-0015, the password stays in the environment (`VAULT_AGENT_SOURCE_URL` or
`.env`); the section shows „set / not set" like the API key, and may at most store a URL **without** password per
project. A browser field that persists the password would need an amendment of ADR-0015; one that only passes it
for a single call without storing it is not excluded by the text, but would still put it into the request and
possibly the console log — not recommended. Left open by the ADR: several sources per engagement (one variable per
workbench process today).

## C46 — taken up as WP119 (2026-11-07)

On the owner's go, specified and built as WP119 (`backlog-2026-07/wp119-source-in-workbench-spec.md`): the connection
from the workbench's environment only, as the ADR-0015 reading above says; a per-project connection and progress for
long profiles stay out (its §3).

## C47 — Neutral type families in the house format; the rules decide on the family, the vendor spelling stays as evidence (owner, 2026-11-07)

**Found** while preparing a live chain with the catalogue read from PostgreSQL (WP119): the house format
(`source_schemas:`) is product-neutral in its structure but carries each column's type in the source's own spelling —
by WP96's rule „transcription, never interpretation". Every chain so far ran on `derive.py`'s transcription of
Microsoft's DDL (SQL Server spellings); none on a catalogue read from PostgreSQL (WP96 measured the reader, 68 tables
equal on every axis, the types a function over 47 spellings — `int → integer`, `nvarchar(n) → varchar(n)`,
`datetime → timestamp without time zone`, `money → numeric(19, 4)`, `uniqueidentifier → uuid`). Where the code
decides on a type it partly knows SQL Server's names only: `rules/dv2_rules.py` `json_type_for_sql` (WP63, the data
contracts' JSON type) maps `int`, `nvarchar`, `datetime`, `money`, `uniqueidentifier` but not `integer`, `timestamp`,
`uuid`, `boolean` — on a PostgreSQL catalogue the model would again choose the type WP63 took from it. The zero-key
sets (`NULL_SAFE_TYPES`, `ZERO_KEY_INCAPABLE_TYPES`, WP83/WP94) are mixed. Not swept completely.

**What the consumers expect, read 2026-11-07.** AutomateDV 0.11.4 (installed package, e.g.
`macros/supporting/ghost_records/create_ghost_record.sql`) and datavault4dbt (`macros/staging/derived_column_datatypes.sql`,
`macros/supporting/ghost_record_per_datatype.sql`) take no type as input: they read the columns of the warehouse
relation at dbt run time (`get_columns_in_relation`) and dispatch per adapter. TurboVault Engine
(`backend/engine/services/imports/domain.py`, read via its repository) holds an optional free-text `datatype` on
source columns and `target_column_datatype` on hub, link and satellite columns, no value set; its comment points to
a database import as the origin — presumably vendor spellings, not confirmed; its Excel format and minimal import
schema have no type column. So the neutral output towards dbt is the model and the project; the types matter for
this tool's own decisions (zero keys, contract types, staging casts) and, verbatim, for a TurboVault export
(ADR-0020).

**Shape (an ADR first, amending WP96's rule).** Each declared column carries two fields: `type` — verbatim as now,
for people, casts and an export — and `family` — neutral, `integer | decimal | string | datetime | date | time |
boolean | uuid | binary | other` (set to be fixed by the ADR), from SQLAlchemy's generic type affinity when the
catalogue reader has the type object (tried on vault-dev: PostgreSQL `INTEGER`/`VARCHAR`/`TIMESTAMP`/`UUID` and SQL
Server `INT`/`NVARCHAR`/`DATETIME`/`UNIQUEIDENTIFIER` fall into `Integer`/`String`/`DateTime`/`Uuid`; `MONEY` has no
affinity in either dialect), plus a small table for types without one (`money`, `xml`, `geography`, user-defined
aliases). Without a type object — `derive.py`, hand-written files — the loader derives the family from the text through
the same table and SQLAlchemy's per-dialect name maps, an approximation it marks. Every rule that reads a type reads
the family; a new source dialect is entries in the table, not code. SAP (C27 tier C) has no SQLAlchemy and supplies
the family itself.

**Possible first stage, small and separate:** extend the type-reading rules by the PostgreSQL spellings WP96
measured (the 47 pairs), guards first, so a chain on a PostgreSQL catalogue is not measuring this gap. Then the ADR
and the family field. **Open:** whether TurboVault evaluates `datatype` or passes it through, and which values its
database import stores — only a real export settles it (ADR-0020 defers that).

## C48 — The landing zone's load columns become payload: a catalogue read from a loaded table declares `load_datetime` and `record_source` as source columns (2026-11-07)

**Found** while clearing the live chain on the PostgreSQL catalogue, on the owner's question where dbt reads the
source data: the generated project reads landing tables in the warehouse (`sources.yml`, `raw`), which carry
`load_datetime` and `record_source` (WP110's loader adds them; a customer's landing zone has its own). A catalogue
read from there (WP96, WP119) transcribes them as ordinary columns; WP96 had measured against `aw_ddl`, a DDL-only
database without them. Reproduced keylessly: `unread_payload` lists them, the error gate `E_HUB_PAYLOAD_UNREAD`
(WP54) asks the loop for a satellite that reads them, and `load_datetime` in a hashdiff writes a new satellite row
per key per batch. **Taken up the same day as WP120** together with C47's first stage
(`backlog-2026-07/wp120-landing-zone-catalogue-spec.md`): the state drops the naming profile's technical columns
from the declared schemas, unless a declared key holds them, and records what it dropped.

## C49 — A print control on the workbench's diagrams (owner, 2026-11-07)

**Asked** by the owner during the twenty-fifth chain: can the Model perspective's diagrams be printed? Today the
tiles (`components/Mermaid.tsx`, WP88) offer zoom, fit and full screen; printing the page prints the whole
perspective in the dark theme, the diagram cut at the tile's width. **Feasible without a new dependency**, since the
component already holds Mermaid's SVG: (1) *print* — re-render the same source with Mermaid's light theme into a
print-only container, an `@media print` rule hiding everything else, `window.print()`, the SVG scaled to the page
(landscape suggested, a wide model may still need more than one page); (2) alongside, *save as SVG* — the same light
SVG as a download, which prints and scales without loss in any viewer. Points to settle: whether the PDF the browser's
print dialog writes is enough or a server-side export is wanted; the title and run stamp on the sheet; an area view
(WP88) printing the area, not the whole model. **Not decided**, no WP number — the owner prioritises; C45's button
kinds would govern the control's look.

## C50 — A project input a run has used is overwritten without a word (owner, 2026-11-07)

**Found** in the twenty-fifth chain: the owner read HumanResources' catalogue and profile in the Source section under
the default names `source_schema.yml` and `profiling.yml`, which the finished person run (`20261107T101620658215Z`)
had used; both were replaced. `ProjectStore.add_file` writes the file and replaces the entry of the same name, and
the attach controls and both Source routes reach it — no warning, no refusal. The run itself is safe (its state
carries the 13 tables, the extension reads the carried state), but `run.json` now names a file whose content is
another schema, and the run's CLI equivalent no longer replays. **Options:** (a) refuse a name a run of the project
references, answering 409 with the runs that use it, and offer a free name; (b) keep the old file under the run
(copy each input into the run folder at start, `inputs/` stays the scratch area) — the run is then self-contained and
replayable whatever happens to `inputs/`; (c) propose a step-specific default in the Source section (the schema's
name, `person_source_schema.yml`). (b) answers the cause, (a) and (c) the surprise; they combine. **Not decided**,
no WP number — the owner prioritises.

## C51 — The entity-resolution answer field: the default is invisible, the list is incomplete, the words are the CLI's (owner, 2026-11-07)

**Found** at the twenty-fifth chain's second resolution checkpoint (`employee::businessentityid` proposed IS
`hub_business_entity`, `exact_key`, 0.90). The answer is a free-text input with a datalist (`perspectives/Review.tsx`,
the resolutions and the unresolved section): its grey placeholder says „leave as proposed, or NEW / a construct", the
list offers `NEW`, `same_as_candidate`, `unresolved` (`ui/runs.py` `RESOLUTION_ANSWERS`, the CLI's `--resolve`
values). The answer space and the list do not map one to one: *keep the proposal* is the empty field and appears
in no list; *another existing construct* is a name to type; the three listed values mix an upper-case token with two
lower-case ones. **The owner's points:** one vocabulary — either the machine names consistently (upper case,
underscores) or human-readable text; *keep the proposal* offered explicitly and as the default; possibly a default
that depends on the confidence. **Proposal for when it is taken up:** a select with human-readable entries — „Keep
proposal (<construct>)" first and preselected, „New hub", „Same as candidate", „Leave unresolved", the existing
constructs by name (or „Other construct…" with a filtered list) — the machine value shown only in the CLI
equivalent; the unresolved section the same without „Keep proposal". On the confidence: ADR-0014 lets the UI decide
nothing an agent decides, and „Keep proposal" already is the agent's answer, so a default that changes with the
confidence would be a second decision rule in the UI; a hint below a threshold („check the evidence") would not.
**Not decided**, no WP number — the owner prioritises; the vocabulary question touches the link and bridge
sections and C45's controls too.

## C52 — A checkbox whose word is the state, not the label: bridge paths and link proposals read the wrong way round (owner, 2026-11-07)

**Found** at the twenty-fifth chain's sign-offs. Under „Bridge paths" each proposal is an unchecked checkbox with the
word „decline" beside it (`perspectives/Review.tsx`, the bridge section); checked, the word turns to „build". The
word is the current answer, not what ticking does — the owner first read „tick to decline", then saw the bridge not
built with the box empty, and only understood when the word flipped. The link proposals at the resolution checkpoint
use the same pattern (`build` / `allow` / `decline`, default checked). **Options:** (1) a two-part segmented control,
`[ Decline | Build ]`, both answers always visible, the chosen one filled, the default preselected (links `[ Build |
Decline ]`, licenses `[ Allow | Decline ]`); (2) a checkbox with a fixed action label („Build this bridge"), the box
alone carrying the state; (3) a switch with a fixed label. **Preferred (1):** it shows a choice between two named
answers, one shape for links and bridges despite their opposite defaults, no word that changes under the pointer.
Belongs with C45 (button kinds) and C51 (the resolution answer field) to one question: a small set of decision
controls for the checkpoint. **Not decided**, no WP number.

## C53 — Bridge proposals grow combinatorially and come back after a decline: 1, 7, 27 decisions per step (owner, 2026-11-08)

**Measured** in the twenty-fifth chain (PIT on, every bridge declined at sign-off): HumanResources 1 proposal,
Production 7, Purchasing 27 — 35 of the 89 decisions of the first four steps. `propose_bridge_paths`
(`business_vault_generator.py`, WP115 spec §2.2) emits one path per pair of links citing the same requirement and
sharing a hub, per arrival participation, per start participation of the first link, per exit of the second; a role
counts as its own participation (`hub_business_entity:person`, `:vendor`, `:employee`), so two links of three
participations around a role-played hub yield up to eight paths, and the set is not pruned for paths that only
differ in an end. A path back to its start appears (`hub_product,…,hub_unit_measure:size,…,hub_product`, Production).
And a declined proposal is proposed again on the next extension (the Address → StateProvince → CountryRegion path at
every step from the first): the decline is recorded in the run, not carried into the model the next step extends.
Each proposal is a `review_flag` decision (`bridge_proposal_flags`, `code_generator.py`). **Consequence:** the
decision count — the measure of review effort (C1, P8 of the twenty-fifth's pre-registration) — is inflated by
variants nobody chose, and the twenty-third chain's baseline (before WP115) no longer compares. **Options:** (a) group
the variants of one link pair into one decision (the pair and the shared hub; ends chosen only when building);
(b) drop paths whose start equals their end and paths an earlier step declined (carry declines like ratified
bindings, WP105); (c) propose only where the requirement names a traversal (both ends cited), not every shared
hub; (d) a disclosure count instead of decisions while no PIT/bridge was asked for at start. (a) and (b) keep the
WP115 evidence and cut most of the volume; they combine. **Not decided**, no WP number.

## C54 — A PostgreSQL `xml` column breaks its satellite: AutomateDV's ghost record is merged with `UNION`, and `xml` has no equality (2026-11-08)

**Found** in the twenty-fifth chain's build (`aw_source`, schema `vault`, PASS=413 ERROR=6): every satellite carrying
one of `aw_source`'s seven `xml` columns (`JobCandidate.resume`, `Person.additionalcontactinfo` and `demographics`,
`Illustration.diagram`, `ProductModel.catalogdescription` and `instructions`, `Store.demographics`) fails with *could
not identify an equality operator for type xml*; two PITs skip behind them. **Cause, read in the compiled SQL**
(`sat_job_candidate_details`): AutomateDV 0.11.4's satellite builds a ghost record (`CAST(NULL AS xml) AS resume`)
and merges it with the new records by `UNION`, which de-duplicates and so compares every column; PostgreSQL defines no
equality for `xml`. The hashdiff is not the problem — the stage casts the column `AS VARCHAR` before hashing. No
earlier build met the type: the `vault` copy holds these columns as `text`. **Options:** (a) the staging generator
derives a declared `xml` column as `text` on PostgreSQL (a derived column of the same name, the payload then a
string — the C47 family `string`); (b) leave ghost records off for satellites with such a payload (AutomateDV's
`enable_ghost_records`), losing the ghost row there; (c) refuse at generation with an attributable message. (a) is the
one that keeps the data and fits C47; the same check belongs to every type without equality (`json`, `point`, …).
**Not decided**, no WP number.

## C54 — taken up as WP121 (2026-11-08)

Option (a), on the owner's go: `backlog-2026-07/wp121-no-equality-types-spec.md`. The nine PostgreSQL types without
equality (measured) are cast to the platform's unbounded text in every bound stage; the twenty-fifth chain's fifth
project builds `PASS=420 ERROR=1 SKIP=4`, the five satellites and two PITs with it.

## C55 — The run form sent another requirements document than the one the owner saw selected (owner, 2026-11-08)

**Found** in the twenty-fifth chain: the false start `20261107T182113094743Z` was started with Production's schema and
profile, and the owner reports `production_requirements.md` selected; `run.json` records `hr_requirements.md` and the
trace's parser read the HR document („Business Requirements: Human Resources Data Warehouse"). The restart a few
minutes later, after a page reload, sent the right document. **Read, not resolved:** the form keeps its choices in
React state (`perspectives/Project.tsx`: `req` initialised to the first requirements file, changed only by the select
and by an upload), the select is controlled by that state — so what it showed should be what it sent; the HR run had
set `req` to `hr_requirements.md` before, and the Source section's reads re-render the perspective. Not reproduced.
**Options:** (a) reproduce in the browser (the Vitest harness cannot show what a browser displayed) — a run after a
Source read and a perspective switch; (b) whatever the cause, show the start's inputs before the run begins — the CLI
equivalent with the three file names, one confirm — and warn when the requirements document's stem and the schema's
differ (`hr_` vs `production_`); (c) clear the form's choices after a start. (b) catches the slip whatever the cause.
**Not decided**, no WP number.

## C53 — option (b) taken up as WP122 (2026-11-08); (a) stays open

The owner chose (b) now and (a) later with the checkpoint controls (C45, C51, C52):
`backlog-2026-07/wp122-bridge-declines-spec.md`. No path back to its own start; a declined path is written to
`metadata/bridge_decisions.yml` and not proposed again by an extension. Replayed on the twenty-fifth chain: 49 bridge
decisions instead of 89. **Open:** (a), one decision per link pair and shared hub (measured 25 with (b)).

## C56 — The AutomateDV findings of the chains, checked against datavault4dbt (owner, 2026-11-09)

**Asked** by the owner: since datavault4dbt (and TurboVault, which generates datavault4dbt code) may become a second
target (C47, ADR-0020), check whether what the chains found in AutomateDV 0.11.4 holds there too. **Probed the same
day** in a scratch dbt project (`/tmp/dv4x` on vault-dev; dbt-core 1.9.10, dbt-postgres 1.9.1, datavault4dbt 2.3.0
from the hub, PostgreSQL 16.15, `aw_source` plus probe tables in `dv4x_src`), two loads where it matters:

| Case | AutomateDV 0.11.4 (our chains) | datavault4dbt 2.3.0 (measured 2026-11-09) |
|---|---|---|
| Payload of a type without equality (`xml`, `json`, `point`) | fails — ghost record merged by `UNION`; vault-agent casts (WP121) | ✔ native types kept; ghost records by `UNION ALL`, hashdiffs compared |
| One hub in two roles (customer → person / store) | ✔ with role-qualified columns (WP8, the generator) | ✔ one hashed column per role, both resolve to the hub |
| A NULL participant (a customer with no store) | the row drops unless `null_columns` (WP83/WP94) | ✔ natively: the unknown key `0000…`, the hub's `-1` ghost record |
| A reserved column name (`group`) | ✔ with `escape: true` (WP79) | **✘** stage only with the vars `escape_char_left/right` (empty on PostgreSQL by default); **`sat_v0` on PostgreSQL never escapes its payload** (`postgres/sat_v0.sql` prints `source_cols` without `escape_column_names`, Snowflake/SQL Server/Databricks/Fabric do) |
| Effectivity across an ownership change | driving-key end-dating (bank demo) | ✔ `eff_sat_v0`: the old link row `is_active` false at the change, the new true |
| PIT | ✔ (WP91) | ✔ with `control_snap_v0/v1`; one row per snapshot and hub row, ghost keys included |
| Snapshot control, documented example | — | **✘** `control_snap_v1.md`'s example (`'yearly': {'forever': 'TRUE'}`) fails on PostgreSQL (`INTERVAL ' '`): the macros test `is true`, a string is not; the boolean `true` builds. Every adapter's macro tests `is true` (read, not built) |
| Bridge | AutomateDV has one; vault-agent renders its own (WP115) | no bridge macro in 2.3.0 |

**Two findings that are datavault4dbt's, reproducible from the scratch project:** the unescaped payload in
`postgres__sat_v0`, and the documented `forever: 'TRUE'` that no macro accepts. Material for the owner's decision on
Scalefree's community challenge (an issue each); nothing filed. **Not decided**, no WP number: whether datavault4dbt
becomes a target is ADR-0020's question.

## C56 — second round (2026-11-09): key translation, NULL into date/uuid keys, a two-source hub, a transactional link

Same scratch project, the owner's go for points 1–4; AdventureWorks shapes in small (`dv4x_src.product`,
`order_line`, `vendor`), two to three loads:

| Case | AutomateDV 0.11.4 / vault-agent | datavault4dbt 2.3.0 (measured) |
|---|---|---|
| Key translation — the line carries `productid`, the hub is keyed on `productnumber` | vault-agent's own translation model (WP36, WP116) with its tests | ✔ `prejoined_columns` in the stage: the line's product key equals the hub's. **But** a dangling reference (product 9 does not exist) becomes the unknown key `0000…`, the same as a line with no product — the difference between „none" and „points nowhere" is lost, nothing flags it |
| NULL participant into a `date`-keyed and a `uuid`-keyed hub | needed WP94's gate (a zero key cannot be cast into `date`/`uuid`) | ✔ the link takes the unknown key; the hubs' ghost rows are typed (`0001-01-01`/`8888-12-31`, `NULL` for `uuid`) |
| One hub, two sources (`business_entity` and `vendor`, key 20 in both) | WP10, one stage per feed | ✔ same key, same hash from both stages; one row per key, the first source's `rsrc` kept |
| Transactional link with payload (`nh_link`, `qty`) | `t_link` (WP8 found the generator calling `nh_link`) | ✔ re-delivery `INSERT 0 0`; a new line inserted; a corrected quantity on an existing line **is not** — first wins, as a non-historised link should, silently |

No further bug in this round. The dangling-reference collapse is a design observation for the comparison, and the
place where vault-agent's translation tests would say more than the package does.

## C56 — third round (2026-11-09): late and out-of-order data, deletes, a multi-active satellite

Same scratch project, the owner's go for points 5–6; three loads (A 2026-03-01, B with a row stamped 2026-02-15 —
older than A — and a changed phone at 2026-03-05, C 2026-03-10 with a key deleted at the source and a phone removed):

| Case | datavault4dbt 2.3.0 (measured) | vault-agent / AutomateDV |
|---|---|---|
| A late row (stamped before the satellite's newest load) | **dropped silently by default**: `sat_v0`'s high-water mark loads only `ldts >` the target's maximum (`postgres/sat_v0.sql:51`), `INSERT 0 0`; with `disable_hwm: true` it is inserted and `sat_v1`'s timeline is right (bronze 02-15…02-28, gold from 03-01); a later re-delivery equal to the newest version inserts nothing | not measured — no chain ever delivered out of order |
| A key deleted at the source | the record-tracking satellite (`rec_track_sat`) shows its last delivery (03-05) and nothing after; the descriptive satellite keeps the last version as current — no delete flag of its own | neither record tracking nor delete detection is generated — a gap of vault-agent's own |
| Multi-active satellite (phones per contact, key `phonetype`) | ✔ a changed number re-versions the whole group (2 rows); a removed phone ends the group, the next holds one row; the unchanged contact untouched | AutomateDV `ma_sat` generated (sat_type multi-active), not measured against changes |

**Summary of C56 over three rounds:** on the data cases that cost work in AutomateDV — payloads without equality, NULL
participants, `date`/`uuid` keys — datavault4dbt is the more robust package; it has two bugs of its own (an unescaped
`sat_v0` payload on PostgreSQL, a documented `forever: 'TRUE'` no macro accepts) and two silent behaviours worth
knowing (a dangling reference becomes the unknown key; a late row is dropped under the default high-water mark).
**For vault-agent itself** two gaps surfaced that do not depend on the package: no record tracking / delete detection,
and no measurement of out-of-order loads. **Not decided**, no WP number.

## C56 — fourth round (2026-11-09): correctness against an independent oracle — two hashing defects on PostgreSQL

The owner pointed out that the rounds so far checked behaviour by eye on a few rows, not the correctness of what the
package builds. **An oracle** (`/tmp/dv4x/dv4x_oracle.py`, Python + psycopg2, outside the package) recomputes from
the source tables and the scripted load history: hub keys, link combinations, one satellite row per change,
`sat_v1` end dates, PIT loads per snapshot, multi-active groups — and every hashkey and hashdiff from the hash rules
the package documents (its global variables: trim, cast to text, the quote / null-placeholder / concat tokens,
`||`, `^^` for NULL, hashkey upper-cased, hashdiff case-sensitive, MD5). A collision probe (`dv4x_src.nasty`) adds
values that would collide under naive concatenation. **Result 23 of 28:**

- **Reconciles:** hub keys = the source's distinct keys (+ two ghosts), every hashkey = the oracle's; the two-source
  hub = the union; link combinations = the deliveries, link hashkeys = the oracle's; one satellite row per change
  as delivered; `sat_v1.ledts` = next `ldts` − 1 µs, the last open; PIT = the latest satellite load at or before each
  of 939 snapshot rows; multi-active groups per load as delivered; the payload equal to the source; no collision of
  `a||`+`b` with `a`+`||b`, `^^` as a value distinct from NULL, blanks trimmed, all-NULL key = unknown key.
- **Defect 3 — the hashdiff is case-insensitive unless the root project sets the variable.** The package's
  `dbt_project.yml` and the macro's default say `hashdiff_input_case_sensitive: TRUE`; the compiled stage upper-cases
  the hashdiff input (`Same` = `same`). Setting `datavault4dbt.hashdiff_input_case_sensitive: true` in the root
  project makes it sensitive. **Consequence, measured end to end:** the source changes `gold` → `Gold`, the satellite
  inserts nothing, and its current version reads `gold` while the source reads `Gold` — wrong data, silently.
- **Defect 4 — PostgreSQL's `regexp_replace` without the `g` flag.** The stage escapes the first backslash, replaces
  the first quote character, and removes the first `\n`, `\t`, `\v`, `\r` of the whole hash input only (PostgreSQL
  replaces one match without `g`; checked directly). The oracle reproduces all 22 hashdiffs (9 probe, 13 `xml`
  rows) only under that model. **Consequence:** `ab` and `a⏎b` share a hashdiff, so do `ab⏎c` and `abc`, while
  `a⏎b⏎c` differs from both — a text that gains or loses a line break is not historised, and inconsistently so.
  Reproduced on PostgreSQL only; the other adapters' functions were not checked for the same behaviour.
- **Observed, not a defect:** a source `timestamp` arrives in the satellite as `timestamptz` (equal values under a
  UTC session; a non-UTC session would read the naive value as local time).

Together with the first round's two (unescaped `sat_v0` payload, `forever: 'TRUE'`), four datavault4dbt defects,
two of them silent wrong data. **The oracle itself** is the reusable part: the same reconciliation and hash checks
could guard vault-agent's own builds (AutomateDV's rules in place of these) — not decided, no WP number.

## C56 — the probe and the oracle kept in the repo (2026-11-09)

On the owner's word the scratch work moved to `eval/datavault4dbt/`: the dbt project (with `models/defects/` for
defects 1 and 2), `scenario.py` replaying the sources and four loads from nothing, `oracle.py`, `hashing.py` (the
documented and the as-built hash rules) and a README with the result; the as-built model pinned keylessly against
the warehouse's hashes in `tests/test_c56_datavault4dbt_hashing.py`. Exit 0 means every check holds except the
recorded defects — a defect that disappears after a package upgrade fails the run, so it is noticed.

## C57 — TurboVault Engine run, not read: a vault-agent model in, datavault4dbt code out, checked by C56's oracle (owner, 2026-11-09)

**Asked** by the owner after C56: TurboVault has so far only been read (ADR-0020, the repository at `2dd2d98`,
version 0.21.0, 2026-10-31), never run. **Plan:** (1) install it in its own environment outside this repo (AGPL-3.0:
running it is use; none of its code comes into this repository); (2) give it a model of this project — the
twenty-fifth chain's person step (13 tables, roles, foreign keys, several sources) — once through the round-trip
project JSON by ADR-0020's recorded mapping and once through the MCP proposal schema, so that what each loses is
**measured** rather than read; (3) let it generate datavault4dbt code, build it in `aw_source`, and check it with
C56's oracle (`eval/datavault4dbt/`). **Why:** evidence for ADR-0020 and C47 (does „vault-agent models, TurboVault
generates" carry?), and material for Scalefree's community challenge, which names TurboVault. **Not decided**
beyond the probe; no WP number; ADR-0020 stands (a probe is no exporter).

## C57 — first step (2026-11-09): the published 0.23.0 does not install into a working state

TurboVault Engine is at **0.23.0** now (`a9feeb3`, PyPI 0.23.0), two minors past ADR-0020's 0.21.0. Installed into
its own environment (`/tmp/tv-venv`, outside this repository; telemetry off by `TURBOVAULT_DISABLE_TELEMETRY=1`,
honoured at `engine/cli/utils/telemetry.py:116`, and by `disable_anonymous_usage_stats: true` in the workspace).
**Defect T1:** `turbovault workspace init` fails with `ModuleNotFoundError: No module named
'engine.services.generation.renderers'`. `pyproject.toml` lists its packages one by one (`[tool.setuptools]
packages = [...]`), and `engine.services.generation.renderers`, added with the SQLMesh output (`8f9c2ba`, #220,
released in 0.23.0), is not in the list; the wheel on PyPI has no `generation/renderers` (checked in the
downloaded `turbovault_engine-0.23.0-py3-none-any.whl`). The documented install (`pip install turbovault-engine`)
therefore stops at the first command. No issue or PR names it (searched 2026-11-09). **Worked around** for the probe
with an editable install from the clone; with it the workspace initialises and Scalefree's own TPC-H example
generates 109 files with „No issues". Next: a vault-agent model in.

## C57 — second step (2026-11-09): the person step through both import shapes, generated, built and compared

The twenty-fifth chain's person step (7 hubs, 4 links, 17 satellites; `hub_business_entity` with five sources, a
role `person` in `link_business_entity_contact`, two multi-active satellites) converted by throwaway scripts (on
vault-dev `/tmp/wp119/tv_mcp.py`, `tv_rt.py`; not an exporter, ADR-0020 stands), the sources given as a round-trip
JSON holding only `sources` (as an Excel template would). Generated with TurboVault 0.23.0 (editable install, T1),
built on datavault4dbt 2.3.0 in `aw_source`:

| | MCP proposal schema (`model import-json`) | round-trip project JSON (`project init --source`) |
|---|---|---|
| Import / validate | 7 / 4 / 17 imported; first **invalid** — „Link has no source tables — set a source_table on the link" while the schema's doc has no such field (`LinkImport` in code has `source_table`, `hub_source_columns`, `payload_columns`, `dependent_child_keys`); with them „valid — no issues found" | „valid — no issues found" |
| Role (`hub_business_entity` as `person`) | **lost silently**: `hub_source_columns` is a dict hub → column, so two participations of one hub cannot be told apart; the link keeps `hk_business_entity_h` (from `personid`) and the contact type — which company a person is a contact for is not in the vault (909 = 909 rows only because person and type are unique in AdventureWorks) | ✔ with `link_column_name` = the hub's key and the role's own `source_column_name` and alias (TPC-H's own `HK_CUSTOMER_DUPLICATE_H` pattern); my first mapping named the link column `personid` and the importer **dropped it without a word**, the link model then referenced a hashkey no stage computed (build error) |
| Several hub sources | **lost**: one `source_table` per hub; the six satellites fed by Person, EmailAddress, PersonPhone, Password fail (`column "hk_business_entity_h" does not exist`) — validation and generation said nothing | ✔ five hub source tables |
| Build | PASS=106 ERROR=6 SKIP=18 | **PASS=131**, nothing failed |
| Content | — | equal to the source **and** to vault-agent's AutomateDV vault for every construct counted (hubs 20 777 / 19 614, the three links, person name, both multi-active satellites); the role link answers all 909 company–person pairs; the `xml` satellite builds |

**Inherited, not fixed:** TurboVault's dbt output sets no `hashdiff_input_case_sensitive`, so its projects carry
C56's defect 3 (every hashdiff of the person stage upper-cased); the setting exists only under `output.sqlmesh`.
**Findings for TurboVault:** T1 (the wheel), T2 the model import schema's doc lags its code (link `source_table`
etc.), T3 an invalid link column is dropped on import without a warning, T4 the MCP schema cannot hold a role or a
second hub source and validation passes the loss; plus defect 3 inherited on the dbt path. **For ADR-0020:**
measured, its reading holds — the MCP schema loses exactly what it said; the round-trip JSON carries this step
whole and builds to the same content as vault-agent's own vault.

## C58 — Positioning against TurboVault Engine: vault-agent finds the model, TurboVault renders one it is given (owner, 2026-11-09)

**Asked** by the owner after C57, on the question whether TurboVault transforms a source schema into a Data Vault by
rules. **Read 2026-11-09** (TurboVault 0.23.0, README and docs): it does not. It ingests source metadata (Excel,
a database catalogue, its JSON export — tables and columns), takes the **model as declared** (the Excel template's
`standard_hub` sheet „defines standard hubs and maps their business keys to source columns"; links and satellites
likewise, row by row; its README's „maps metadata into a consistent Data Vault domain model" is that translation, not
an inference), validates it and renders datavault4dbt / SQLMesh code from Jinja templates — deterministic, but only
after a human, or an AI assistant through its MCP server (`list_sources` → `commit_model`), has decided the hubs,
keys, links and satellite split. It names its target „Data Vault 2.0".

| Step | vault-agent | TurboVault Engine |
|---|---|---|
| Finding the model from requirements and the catalogue | agents under a rule set, gates, human ratification | a human (Excel, admin) or an external LLM via MCP, without gates |
| Checking the model | the validator's gates (bindings, translations, grain, keys, …) | validation rules — which passed the role and hub-source losses of C57 (T4) |
| Rendering code | AutomateDV | datavault4dbt / SQLMesh |

**The positioning this suggests** (for the owner to decide; touches ADR-0015's product statement and ADR-0020):
- *Complementary* on the round-trip path: vault-agent supplies the modelling TurboVault lacks, TurboVault the
  datavault4dbt rendering vault-agent lacks — measured lossless for the person step (C57: PASS=131, content equal to
  source and to vault-agent's own vault).
- *Competing* with TurboVault's MCP path: both put an LLM on the modelling step; vault-agent's case is the rule set,
  the gates and the human ratification around it, and that its model survives the hand-over (the MCP schema measurably
  does not — C57, T4).
- Evidence on hand for either message: C56 (datavault4dbt's defects, the oracle), C57 (both import paths measured).

**Not decided**, no WP number; no wording is published.
