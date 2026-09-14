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
- In brownfield mode the modeler's links to existing hubs, and satellites on existing hubs or
  links, were dropped while parsing its answer: only hubs the delta itself emitted counted as
  known, although the extension prompt asks for links to existing hubs by name. The defect
  dates from the brownfield merge (2026-07-29). Existing hubs and links now count; a reference
  to a hub in neither the delta nor the vault is still dropped.

### Added
- Translated subtype feeds (WP38): a ratified same-as whose join the source schema declares
  (`SalesPerson.BusinessEntityID → Employee`, `hub_employee` keyed on `NationalIDNumber`) no
  longer prompts an own hub; the subtype table's satellites on the supertype hub are staged
  through the WP36 translation view, with `E_SAT_TRANSLATION_UNRATIFIED` and
  `E_SAT_KEY_NOT_IN_SOURCE`. Built on PostgreSQL (`demo/fk_links_postgres`) and live once
  (2026-09-15): no `hub_sales_representative`, two translated satellites on `hub_employee`.

### Changed
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
  remedy — passed every gate and held all four clauses of WP34 §6 as originally written.
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
- WP30 arm-B rerun (2026-09-12, one repeat, ~$17): 7 cross-domain links (was 2), review load 519
  (< 619), all gates green; WP34 §6 not met (7 < 8, `hub_sales_representative` returned). One
  translated link built live; three of four blocked by the applier's near-hub rule.
- `LLM_PROVIDER=anthropic|bedrock|vertex` selects the route to Claude — the data-residency
  switch from `docs/architecture/deployment-residency.md`, now wired: one client factory,
  construction-time validation naming the missing variable, optional extras `bedrock` and
  `vertex`. Keyless-only: no run has gone through Bedrock or Vertex yet (manual 5.5).
- The route is reported: `llm route:` in the run summary, an `llm_route` header event in every
  trace segment, and a `client` field on every call event naming the SDK client that carried it.

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
