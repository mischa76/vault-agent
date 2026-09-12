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

### Added
- Surrogate→natural-key translation for FK-derived links (WP36, ADR-0013 accepted 2026-09-12):
  a foreign key that references a surrogate while the hub is keyed on the natural key is now a
  proposal (`declared_fk_translated`) instead of a skip; a ratified one renders a translation
  model (LEFT JOIN through the referenced relation, with `not_null`/`relationships` tests) that
  the link's stage reads, a `link_translation` review item, and a gate branch. Keyless-only.
- The modeler's tool schema no longer exposes the proposer-owned `LinkHubRef` fields
  (`source_key_column`, `key_translation`), and `E_LINK_TRANSLATION_UNRATIFIED` refuses a
  translation no ratified proposal produced — added after a paid run showed the modeler filling
  the field the moment it could see it.
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
