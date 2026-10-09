# Changelog

All notable changes to vault-agent. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/) and stay below 1.0 until the first live
Databricks build (see the 0.9.0 release notes). The detailed, dated record of every work package,
measurement and correction is `docs/log.md`; this file is the summary a user of the tool reads.

**One version, three places that must agree:** `pyproject.toml` (the source, bumped with
`uv version X.Y.Z`), the git tag `X.Y.Z` (no `v` prefix), and the section heading here.
`tests/test_release.py` fails when they drift; the release workflow refuses a tag whose version
is not the project's.

## [Unreleased]

### Fixed
- The source mapper's re-bind rebuilt staging without the vault being extended, so a brownfield
  run renamed a grandfathered `stg_<entity>` to `stg_<entity>_<source>` and rebound it, while the
  raw-vault hub still read `stg_<entity>` — a vault that cannot build. Replayed from a recorded
  paid run of the brownfield case; live since 2026-09-17.
- A tool answer that double-encodes an object-valued field (the value as a JSON string) is
  decoded instead of crashing the run; each repair is counted as a backstop in the trace. One
  paid run was lost to this before the backstop existed.
- In brownfield mode the modeler's links to existing hubs, and satellites on existing hubs or
  links, were dropped while parsing its answer: only hubs the delta itself emitted counted as
  known, although the extension prompt asks for links to existing hubs by name. The defect
  dates from the brownfield merge (2026-07-29). Existing hubs and links now count; a reference
  to a hub in neither the delta nor the vault is still dropped.
- A chain's `validation_gate` and `pipeline_health` read the final step only, so a red step under
  a green last step scored a healthy chain (WP52). Both are now the minimum over all steps, as
  preservation already was; the details name every step and the worst.
- A satellite the key gate refused and the modeler re-emitted unchanged was always dropped into a
  review decision, although its remedy had named the parent whose key the relation carries. With
  exactly one such parent it now moves there (`retired_reparented`, a disclosure; WP52).

- A chain resumed with `--resume-chain` scored its resumed steps from reconstructed states that
  carry only the model, so the chain's `validation_gate` read 0.0 (WP52's minimum over steps)
  and its review counts summed only the steps actually run (42 of 127 on the seventh chain).
  Resumed steps now take their scores and counts from their persisted result files
  (2026-10-07).
- A connection dropped while an answer was streaming surfaced as a raw `httpx.ReadError` and
  ended the run unretried: the SDK wraps transport errors only around the initial request. The
  retry loop now catches `httpx.TransportError` beside `APIConnectionError` (2026-10-07, the
  seventh chain's step 5).

### Changed
- The WP34 §6 review clause judges a chain's decisions against a distribution (WP53): the
  one-sided 95 % prediction bound over the recorded normal chains before it, the run itself and
  later ones excluded, instead of one chain's number (148). Six chains are recorded; fewer than
  three cannot judge. The sixth chain (156) still fails against its five predecessors (151.9).
- `extension_conflict` — the merger refusing a delta that re-states an existing hub's key, an
  existing link or an existing satellite — is an advisory flag, not an error (WP52). The vault is
  kept unchanged as before and the flag stays a review decision; a run no longer fails
  `pipeline_health` on it, because nothing in the generated vault is wrong.

### Added
- `FORCED_TOOL_CHOICE=false` (WP60): the LLM client asks for its tool with `tool_choice: auto`, a
  strict schema and an instruction line, retrying a text-only answer — the mode Opus 5.5,
  Sonnet 5.5 and Fable 5.1 need, which return a 400 on forced tool use. The default (forced)
  request is unchanged.
- The modeler's retry is a repair, not a new draft (WP57): the payload carries the previous
  attempt's model (`previous_model`, the delta) beside the validation issues, and a steering line
  (`repair_not_redraft`) asks for exactly the changes the issues name. Until now every attempt was
  drawn afresh and a fix could vanish in the next attempt.
- `hub:role` in a link's `connected_hubs` is read as a role-qualified participation (WP58), the
  notation `driving_key` already used; two links written that way had been dropped as unknown hubs.
- A satellite without a `source_table` whose attributes are all columns of exactly one declared
  table reads that table (WP56): on a collapsed one-hub link it moves with the inferred relation
  instead of being dropped; on a hub a relation other than the hub's own is set
  (`relation_inferred`, a disclosure; backstop `satellite_relation_inferred`). A lone timestamp
  infers nothing.
- A link with one known hub is collapsed into that hub (WP55): its satellites that declare a
  relation move to the hub (`link_collapsed`, a disclosure; backstop `one_hub_link_collapsed`)
  instead of the link and its satellites being dropped as two `dropped_record`s and the payload
  lost for the attempt.
- A gate for the lost payload (WP54): `E_HUB_PAYLOAD_UNREAD` refuses a hub built from a declared
  table of the increment whose payload columns no satellite reads, naming the columns and the
  parent to hang them on. Until now a hub without any satellite on its table raised only the
  `W_HUB_NO_SAT` warning, and two tables' descriptive columns vanished from a live chain unseen.
  Verified keyless and on PostgreSQL (`demo/fk_links_postgres`, four satellites added: PASS=134).
- A link's relation resolved by more than its name (WP42): a link used to be tied to its source
  relation by its construct name, and the modeler names links freely — over six recorded chains the
  name bound 84 of 348 links, leaving the rest invisible to every key repair and every link gate.
  The relation is now found by name first and otherwise by the single declared relation whose
  offer — the hubs built from it plus the hubs its single-column foreign keys resolve to, counted
  with multiplicity — covers the link's participations; two fitting relations bind nothing. Replayed
  over those chains: role warnings 18 → 5, repaired participations 103 → 199, and three links whose
  name never matched a table are now refused for hashing a hub from another entity's key
  (`link_store_sales_representative` from `Store.BusinessEntityID`). A link bound this way also
  stages from that relation instead of an inferred `raw_<name>`: over the same chains the number of
  link stages left to an inferred binding fell from 185 to 47 — 45 ambiguous or unbindable, 2
  sharing a hub's stage, which the hub's binding decides. Built on PostgreSQL (`demo/fk_links_postgres`,
  `link_bom`) and verified in a paid chain (2026-09-17): role warnings 4 → 0, no link stage left
  inferred while one declared relation offers it.
- Role columns from declared keys (WP41): a role-qualified link participation takes its key from a
  ratified foreign key — the only key into its hub, or the one whose column its role names
  (`component` → `ComponentID`) — instead of demanding `ROLE_<key>`. Same-named and renamed keys
  are derived, translations projected under the role column, so `hub_product` as assembly and
  component through one table stays two columns; link satellites follow per participation. A
  ratified key also repairs the `E_LINK_KEY_WRONG_COLUMN` shape instead of refusing it. Built on
  PostgreSQL (`demo/fk_links_postgres`, every link row joining the right entities); no live run.
- `E_LINK_KEY_WRONG_COLUMN`: a link participation is refused when its stage would hash the hub's
  key from a same-named column of the link's source table while that table declares its foreign
  key into this hub on a different column — `hub_person` from `BusinessEntityContact.BusinessEntityID`
  (the organisation), where the table declares `PersonID → Person`. Such a link builds and joins the
  wrong entity. Grounded runs with declared foreign keys only. Replayed on five recorded
  AdventureWorks chains it refuses exactly that link, in step 1 of three. A greenfield step has no
  checkpoint to ratify the alias, so expect that step's gate to fail unless the modeler changes the
  link. Keyless; no live run.
- Key licenses (WP40): a declared foreign key into a table of the same increment that has no hub
  yet is a `Table.Column` decision at the link checkpoint instead of a skip. Resolved after
  modelling, a ratified license — and a ratified translated or renamed link proposal — repairs the
  staging of links and satellites the modeler built from that table, never building one; link
  satellites carry per-participation translations. Built on PostgreSQL and live once
  (2026-09-15): 27 and 16 licenses, all resolved.
- Two-hop translation (WP39): a foreign key into a table that has no hub of its own, whose key is
  itself a declared foreign key (`SalesOrderHeader.SalesPersonID → SalesPerson → Employee`), is
  translated through the end table; the nearest hub always decides. Subtype feeds (WP38) also
  cover tables keyed on the subtype's key (`SalesPersonQuotaHistory`). Keyless, replayed on a
  recorded chain, built on PostgreSQL (`demo/fk_links_postgres`); no live run.
- Translated subtype feeds (WP38): a ratified same-as whose join the source schema declares
  (`SalesPerson.BusinessEntityID → Employee`, `hub_employee` keyed on `NationalIDNumber`) no
  longer prompts an own hub; the subtype table's satellites on the supertype hub are staged
  through the WP36 translation view, with `E_SAT_TRANSLATION_UNRATIFIED` and
  `E_SAT_KEY_NOT_IN_SOURCE`. Built on PostgreSQL (`demo/fk_links_postgres`) and live once
  (2026-09-15): no `hub_sales_representative`, two translated satellites on `hub_employee`.

### Added
- Every inferred staging binding carries a typed reason (WP47): `none` (nothing declares the
  relation), `ambiguous` (two or more declared relations offer the link's participations — a
  review decision), `shared` (the stage is a hub's). `PipelineFlag.reason`, part of the flag's
  identity; `flag_reasons` in eval results. A chain variant `adventureworks_incremental_cumulative`
  hands each step the catalogue of the steps before it (`chain.cumulative_schema`).
- Composite foreign keys are read per component (WP46): a component whose referenced column is
  itself one declared single-column key onward is a key into that table and licenses the same
  translations a declared single key would; components without an onward key stay a typed
  `composite_key` skip naming them. `E_SAT_KEY_NOT_IN_SOURCE` now carries a remedy naming the
  parents whose key the relation carries, and retires the satellite's shape: an unchanged copy in
  a later attempt is dropped into a `retired_orphan` decision. Built on PostgreSQL in
  `demo/fk_links_postgres` (`link_sales_order_line`, `PASS=130`).
- The eval persists each run's and each chain step's review queue (`…review-queue.md`) and its
  typed flags, issues, retirements and roled queue items (`…review.json`) beside the result JSON,
  so a paid run is re-analysable from disk.
- Composite business keys (WP45). A hub names its key columns in `business_key_columns`; the
  stage hashes the list, the hub's `src_nk` is the list, satellites and unqualified link
  participations hash the same list from their relations, and the key gates read it. The
  multi-source, role, alias and translation shapes are refused by the new gate
  `E_HUB_COMPOSITE_UNSUPPORTED` rather than staged from one column. The modeler's `A + B`
  notation is typed by the backstop `composite_key_split` when every part is declared. Built
  on PostgreSQL in `demo/fk_links_postgres` (`hub_currency_rate`, `PASS=113`).

### Fixed
- A dropped hub's payload moves to its kept twin (WP51): the retirement records the hub the remedy
  kept, and the memory re-parents the dropped hub's satellites and re-points its link participations
  there instead of orphaning them; a link the twin already takes part in is dropped. On the fifth
  chain of 2026-10-06 the kept twin had ended without a satellite and seven payloads as decisions.
- `E_LINK_KEY_WRONG_COLUMN` carries a remedy with memory against the second hub of one person (WP50):
  when the relation's declared key for the hub is a ratified key resolving to another hub and the
  modeler's hub is built from the table that key references, the remedy names the ratified hub and
  retires the second one by shape. On the fourth chain of 2026-10-06 `hub_sales_person` beside
  `hub_employee` had kept step 5 red for three attempts.
- The repair memory retires a hub by its shape — source entity and key — beside its name (WP49):
  on the third chain of 2026-10-05 the modeler re-emitted a retired duplicate under a new name on
  the last attempt and the name-keyed memory let it through. The retry payload now forbids the
  shape, and `drop_retired` drops a renamed copy with the links naming it.
- `E_SAT_ATTR_OVERLAP` carries a remedy with memory (WP48): the rule names the satellite that keeps
  the attribute (an existing one, else the first by name) and retires it on the others; a
  re-emitted copy loses it again. On the cumulative chain of 2026-10-05 one such overlap, left
  unrepaired by the loop, had made four steps red by inheritance.
- `W_HUB_NO_SAT` fired once per link for the last hub instead of once per satellite-less hub —
  WP45's link loop had captured the per-hub check (55 warnings for one hub on the paid chain of
  2026-10-04); back in the hub loop, guarded by `tests/test_validator_hub_no_sat_once.py`.
- The re-model loop no longer loses a repair it was given (WP44). A hub the `E_HUB_HK_COLLISION`
  remedy retired is refused if a later attempt re-emits it, with the links and satellites that
  named it; the construct is a `retired_reemitted` disclosure, an orphaned dependent a
  `retired_orphan` decision, and each fire is a `backstop` trace event. On 2026-09-17 step 5 had
  dropped `hub_shopping_cart_item` as told in attempt 2 and brought it back in attempt 3.

### Changed
- `eval.wp34_check`'s review clause reads `review_decisions` against 148 (the 2026-10-04 chain)
  instead of the signal count against 619, which had fallen by construction when WP43 took the
  extension inventory out of the queue; the signal count is reported beside it, unjudged, and a
  pre-WP43 result without a decision count cannot satisfy the clause. WP34 spec §11.
- The review queue tells decisions from disclosures (WP43). Every item carries a typed role: a
  *decision* needs an answer (assign, accept/discard, ratify, fix); a *disclosure* states what was
  assumed, inferred, dropped or declined. All three renderers list every decision before every
  disclosure, the status line counts both, and the WP5 aggregation now also collapses validation
  warnings of one code. The extension inventory is emitted as `I_EXISTING_EXTENDED` with the new
  severity `info` (was the warning `W_EXISTING_EXTENDED`) and is no longer a review item — read
  it in `extension-diff.md` or the report's Extension section. Eval results gain
  `review_decisions` and `review_disclosures`. On the saved 2026-09-17 chain this is 532 → 373
  items, of which 120 decisions (pre-registered from the saved counts, not re-run).
- `E_SAT_KEY_NOT_IN_SOURCE` now refuses every satellite with a declared `source_table` whose
  relation lacks its parent's key column(s), not only translated ones. Such a stage could never
  build; the refusal moves the failure from `dbt build` into the re-model loop. Expect runs that
  passed validation before to fail it now: replayed on four recorded AdventureWorks chains it
  refuses 2 to 11 satellites each.
- `eval.wp34_check`: the named-regression half of §6's invention clause is reported, not
  failing — `hub_sales_representative` is the outcome WP29's ratified same-as prompt
  prescribes ("keyed differently: model it as its OWN hub"), not an invention. Recorded as a
  correction of a pre-registered criterion (`docs/log.md` 2026-09-14). WP38 is the planned
  answer to the hub itself.

### Fixed
- WP37's applier re-used the resolution of a pending relationship participation from an
  earlier modelling attempt; when the re-model loop dropped that hub, the link was built to a
  hub no longer in the model (`E_LINK_UNKNOWN_HUB`) and the next attempt re-created the hub.
  A pending participation is now resolved against each attempt's merged model
  (`Participation.resolved_by_applier`).
- The translation view's generated `schema.yml` (WP36) rendered `to: {{ ref('x') }}` — not
  valid YAML, so dbt refused to parse every project that carried a translated link. Found by the
  first `dbt build` of one (2026-09-13); now `to: ref('x')` / `to: source('a', 'b')`.
- A link with two translated participations (a WP37 relationship link such as `ProductVendor`)
  got one translation view, the last translation overwriting the first, and its stage hashed a
  natural key the view never projected. A stage now carries a list of translations, rendered as
  one view with one LEFT JOIN each (`stg_<link>_via_<a>_and_<b>`); `automatedv.yml` records
  them under `key_translation.joins`.

### Added
- The re-model feedback for `E_HUB_HK_COLLISION` now carries a `remedy` that names the hub
  to drop (`rules.hub_collision_remedy`: an inherited pair is unrepairable, an existing hub
  stays, the higher-ranked business-key candidate stays, a key that references another hub's
  entity is dropped) and the modeler is told to apply it. Keyless; replayed over the day's
  recorded attempts with `eval.replay_collision_remedy`; no live datapoint yet.
- `eval.run --resume-chain <stamp>`: a chain step now leaves its model beside its result, and
  a chain that died mid-way is continued from the first step without one instead of being
  bought again (`metrics.resumed_from` says what was reused).
- `demo/fk_links_postgres/`: the keyless, runnable capture of WP36 and WP37 — a translated link
  and a three-way relationship link built green on local PostgreSQL through the real proposer,
  applier and generator (`tests/test_demo_fk_links_postgres.py` guards it).
- Relationship-table links (WP37): a declared table with two or more single-column foreign
  keys and no hub of its own is proposed as the link among the tables it references — one
  `Table.*` decision at the checkpoint, participations pending on this increment's own tables
  are resolved after the modeler ran, translations (WP36) per participation, a
  `link_relationship_incomplete` review item where a participation cannot be resolved. The
  applier now finds a hub by the table it was built from (`source_entity`, WP10 feeds), not only
  by name, so `hub_purchase_order` built from `PurchaseOrderHeader` counts as that table's hub.
  Measured live over five chains (2026-09-13 to 15): 16, 16, 16, 17, 21 cross-domain links
  against arm A's 16. The fifth — with the brownfield parser fix, WP38 and the collision
  remedy — passed every gate and held all four clauses of WP34 §6 as originally written. The
  sixth, with WP39 and WP40, held them again at 23 links.
- Surrogate→natural-key translation for FK-derived links (WP36, ADR-0013 accepted 2026-09-12):
  a foreign key that references a surrogate while the hub is keyed on the natural key is now a
  proposal (`declared_fk_translated`) instead of a skip; a ratified one renders a translation
  model (LEFT JOIN through the referenced relation, with `not_null`/`relationships` tests) that
  the link's stage reads, a `link_translation` review item, and a gate branch. Keyless-only.
- The modeler's tool schema no longer exposes the proposer-owned `LinkHubRef` fields
  (`source_key_column`, `key_translation`), and `E_LINK_TRANSLATION_UNRATIFIED` refuses a
  translation no ratified proposal produced — added after a paid run showed the modeler filling
  the field the moment it could see it.

### Fixed
- `eval/adventureworks/extract.py` read only the first constraint of a multi-constraint
  `ALTER TABLE`; 44 of AdventureWorks' 90 foreign keys were missing from every derived schema.
  Re-derived; one pre-registered step-order edge (Person↔Sales) is now a recorded cycle.

### Measured
- Fifth normal chain (`20261006T032619166848Z`, ≈ $6.79): **the second all-green chain**, and the first
  the repair memory made green — step 2's third attempt re-emitted two retired hubs, which were
  dropped with three links and four satellites (seven orphan decisions). WP34 §6 failed only on the
  invention clause, one of the three satellite-less hubs being the kept twin whose payload went to a
  decision. `docs/log.md` 2026-10-06.
- Fourth normal chain (`20261005T234048650821Z`, ≈ $6.24): steps 1–4 green, WP34 §6 all four clauses
  held, step 5 red on `E_LINK_KEY_WRONG_COLUMN` — the modeler built `hub_sales_person` beside
  `hub_employee` and the ratified key for `Store.SalesPersonID`, resolved to `hub_employee` before
  modelling, repaired nothing on the new hub. The two-hubs-on-one-person defect from the key side;
  two deterministic answers proposed. `docs/log.md` 2026-10-06.
- Third normal chain (`20261005T160357535338Z`, ≈ $6.50): steps 1–4 green, step 5 red on a duplicate
  hub the modeler re-emitted under a new name after the remedy had retired the old one — the WP44
  memory keys hubs by name; it must key them by shape. WP47's reasons live (`ambiguous` 6 of 189),
  WP48's remedy followed in four steps with no backstop fire. `docs/log.md` 2026-10-05.
- Cumulative-catalogue chain (`adventureworks_incremental_cumulative`, `20261005T092147230544Z`,
  ≈ $9.36): three of five predictions failed — 227 calls, 193 contract owners, four red steps on an
  inherited `E_SAT_ATTR_OVERLAP` — because the pipeline reads a declared schema as this increment's
  tables (contracts, proposals, grounding) and a red step skips the mapper where links bind. The
  catalogue's binding effect stays estimated by the offline replay (154 → 21). `docs/log.md` 2026-10-05.
- Arm A (`adventureworks_full`, one pass over 68 tables, `20261004T171256542998Z`, ≈ $7.10): 134
  review decisions against arm B's 135 and 148 — the charter claim's review axis is a tie as measured;
  disclosures 21 against 218–230; cross-schema links by one rule 13 against 15; gate green. WP34 spec §12,
  `docs/log.md` 2026-10-05.
- Chain `20261004T140130528908Z` (2026-10-05, one repeat, ≈ $6.62): **the first all-green chain** —
  `validation_gate` 1.0 in all five steps, WP34 §6 all four clauses (22 cross-domain links), review
  353 items / 135 decisions. Three steps went to a second attempt and the modeler followed every
  remedy (two collisions dropped, the `WorkOrderRouting` satellite re-parented onto
  `hub_work_order`); the WP44 memory and the WP45 backstop were never needed. `docs/log.md` 2026-10-05.
- Chain `20261004T013339024833Z` (2026-10-04, one repeat, ≈ $6.44): WP43/44/45 live. No hash-key
  collision in any step (the modeler built the cart item as a link); the modeler filled
  `business_key_columns` for `hub_currency_rate` itself; the composite-key errors are gone;
  steps 3 and 5 red on a different class (a link satellite whose product participation has no
  declared key to translate through); WP34 §6 all four clauses held (22 cross-domain links);
  review 378 items corrected, 148 decisions. `docs/log.md` 2026-10-04.
- WP30 arm-B rerun (2026-09-12, one repeat, ~$17): 7 cross-domain links (was 2), review load 519
  (< 619), all gates green; WP34 §6 not met (7 < 8, `hub_sales_representative` returned). One
  translated link built live; three of four blocked by the applier's near-hub rule.
- `LLM_PROVIDER=anthropic|bedrock|vertex` selects the route to Claude — the data-residency
  switch from `docs/architecture/deployment-residency.md`, now wired: one client factory,
  construction-time validation naming the missing variable, optional extras `bedrock` and
  `vertex`. Keyless-only: no run has gone through Bedrock or Vertex yet (manual 5.5).
- The route is reported: `llm route:` in the run summary, an `llm_route` header event in every
  trace segment, and a `client` field on every call event naming the SDK client that carried it.

### Security
- Dependabot alerts 34–41 (`pypdf` < 6.19.0, eight high: long runtimes or large memory on crafted
  PDFs) closed by a lock-only upgrade to 6.19.0; `pyproject.toml` (`pypdf>=6.15.0`) unchanged.
- Dependabot alerts 23, 24 (`anyio`), 27–29 (`urllib3`), 30 (`PyJWT`) and 31–33 (`tornado`) closed
  by a lock-only upgrade: anyio 4.15.1, urllib3 2.8.0, PyJWT 2.15.1, tornado 6.5.10 (`uv lock
  --upgrade-package`, no change to `pyproject.toml`). Alerts 25 and 26 (`oauthlib` < 4.0.0) stay
  open: `databricks-sql-connector` caps oauthlib below 4 up to its current 4.6.0, which is why the
  Dependabot update of 2026-10-01 found no resolution (`docs/log.md`, 2026-10-03).

## [0.9.1] - 2026-09-12

### Changed
- The two dbt extras `demo` (dbt-core 1.9, dbt-postgres — the line verified on PostgreSQL) and
  `demo-databricks` are declared mutually exclusive (`[tool.uv] conflicts`) and resolved as
  separate forks; `demo-databricks` moves to dbt-databricks 1.12 / dbt-core 1.11, whose
  connector admits `thrift >= 0.24`. `uv sync` installs one or the other, never both.
- Versioning and release process: `pyproject.toml` is the single source of the version,
  `vault-agent --version` reports it, this changelog exists, a test pins tag/code/changelog
  agreement, and pushing a tag `X.Y.Z` builds the package and publishes the GitHub release.

### Security
- Dependabot alerts 20–22 (`thrift 0.20.0`, transitive via the Databricks adapter) closed by the
  extras split; alert 16 (`sqlparse 0.5.5`) dismissed as not reachable — the affected
  `ReindentFilter` is never instantiated on this project's call graph (`docs/log.md`, 2026-09-12).

### Documentation
- Corrections recorded, not rewritten: the Postgres line is live-verified many times over
  (`dbt build` green since 2026-06-23); "live" now has to say which live — a paid LLM run
  verifies modelling, a keyless `dbt build` verifies the warehouse output (`CLAUDE.md`,
  definition of done).

## [0.9.0] - 2026-09-12

The first tagged state: a requirements document in, a reviewed, runnable AutomateDV/dbt project
out — hubs, links (including role-qualified self-referencing and transactional), standard,
multi-active and effectivity satellites, the staging layer with every hash key and hashdiff, data
contracts with dbt tests, an ADR. Ten agents as a LangGraph state machine, bounded self-correction,
a persisted human checkpoint with `resume`, source-schema grounding (ADR-0004), business↔source
mapping with ratification (ADR-0008), brownfield mode (`run --existing`), Databricks as a
selectable target platform (`--target-platform`). Full notes: the GitHub release.

Verified: both Postgres demos build green on PostgreSQL 16 without an API key; 891 keyless tests.
Open: no live Databricks build yet — that is what 1.0 waits for.

> Recorded for honesty: the tag `0.9.0` points at `6eeac6b`, whose `pyproject.toml` and
> `__version__` still said `0.1.0`. The version in code was not bumped for this release. From
> 0.9.1 on, tag and code agree, and a test and the release workflow enforce it. The tag was not
> moved — a published tag stays where it is.

## [0.1.0] - 2026-06-11

Project start. Everything between here and 0.9.0 is in `docs/log.md`, entry by entry.

[Unreleased]: https://github.com/mischa76/vault-agent/compare/0.9.1...HEAD
[0.9.1]: https://github.com/mischa76/vault-agent/compare/0.9.0...0.9.1
[0.9.0]: https://github.com/mischa76/vault-agent/releases/tag/0.9.0
