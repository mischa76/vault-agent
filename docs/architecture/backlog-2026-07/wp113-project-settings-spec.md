---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP113 — Project settings in the workbench: platform, model ids, base URL (C3, the settings half)

Status: **Approved and in progress** (2026-10-31, the owner's word: the old backlog) · Owner: Mischa Eismann ·
Author: Claude. C3 (2026-10-21) has two halves: a per-project settings tab, and a `NamingProfile` in `rules/`. This WP
is the first; the naming profile is WP114, its own spec, because it threads through every renderer and needs the
byte-identity guards on their own.

## 1 What is missing

A workbench run takes the environment's models (`PRIMARY_MODEL`, `HEAVY_MODEL` from `.env`, WP62's defaults) and the
first-party endpoint; the only per-run choice is the target platform, typed into every start. A consultant running
two clients' projects on one machine — one on a proxy endpoint, one on the first-party API; one on Databricks, one on
PostgreSQL — has nothing per project. The SDK honours `ANTHROPIC_BASE_URL` from the environment; the client is built
with the key alone, so a per-project URL has no way in. And `resume` rebuilds the agents from `.env`, so a run started
under one model could be resumed under another without a trace.

## 2 The rules

1. **`LLMOptions`, typed, travelling with the run.** `config.LLMOptions(primary_model, heavy_model,
   anthropic_base_url)`, each optional — `None` means the environment's value. `graph.default_agents(options)` hands the
   models to the six model-calling agents (the modeler the heavy one) and the base URL to every `ForcedToolCaller`,
   which builds its client from the settings with that URL (`Settings.anthropic_base_url`, env `ANTHROPIC_BASE_URL`,
   `make_client` passing it to the SDK; `None` keeps the SDK's own default). `pending.json` carries the options
   (`llm`), `_resume_pipeline` and `_continue_pipeline` read them back and build the same agents; a pointer without
   the key is the default (every older run).
2. **The CLI has the same three flags** — `--primary-model`, `--heavy-model`, `--anthropic-base-url` on `run` — so a
   workbench run's CLI equivalent is a command that reproduces it (C4's parity), and a terminal run can be pinned to
   a model or an endpoint without editing `.env`. `resume` and `continue` take no flags: the pointer says.
3. **Per project: `settings.json`.** `GET /api/projects/{id}/settings` answers `settings` (what is stored, empty by
   default), `effective` (the stored over the environment: platform, the two models, the base URL) and `environment`
   (the provider route and whether the key is set — `anthropic_api_key_set: true|false`, never the value; secrets stay
   in `.env`). `PUT` stores a validated body (`ProjectSettings`: a known platform, non-empty model ids or none, a base
   URL with an `http`/`https` scheme or none; blank strings clear a field). A run the project starts takes the stored
   platform unless the start body names one, and the stored models and URL always; `run.json` records `llm` beside
   `target_platform`, and the CLI equivalent carries the flags.
4. **The tab.** A „Settings" section in the Project perspective: the platform (the start form's default follows it),
   the two model ids, the base URL, a save button; the route and „API key: set / not set" as text. Nothing here ever
   shows a secret.

## 3 Not this WP

The naming profile (WP114). An OpenAI-compatible endpoint (a different protocol behind the caller — its own ADR, as
C3 says). Per-run model overrides in the start body (the project decides; the CLI pins per run). Settings for the
eval harness (its cases say what they measure).

## 4 Acceptance (keyless)

`tests/test_wp113_project_settings.py`, committed red (import): a new project's view (empty settings, the environment
showing through, the key as a boolean, never the value, 404 for an unknown project); a body stored, validated (422 for
an unknown platform or a scheme-less URL), read back and cleared by blanks; a run taking the settings into
`run.json`, the CLI equivalent and `pending.json`, the body's platform winning; `default_agents(options)` handing the
models and the URL to every caller; the client built with the URL; the pointer carrying and returning the options;
the CLI's flags recorded in the pointer and a `resume` rebuilding its agents from it. `Project.test.tsx`: the settings
shown from the API and saved as typed.

## 5 Pre-registration (keyless)

- **P1** The nine Python guards and the Vitest test green; every older test green — the default path (`build_graph()`
  with no agents) is byte-for-byte the previous one, so the stub-patched workbench and CLI suites run unchanged.
- **P2** A CLI run with the three flags and a resume without them: the resume's agents built from the pointer's
  options (the guard); a workbench run's first CLI equivalent reproduces the settings.
- **P3** Suite, ruff, bare mypy; `tsc`, `vitest`; the manual's run options (6) and the workbench API table (14.2)
  gain the rows; `vault_agent.ui` stays at or above the floor.

## 6 Measured

Appended after the run.

## 6 Measured (2026-10-31, keyless)

- **P1 ✔.** The nine Python guards and the Vitest test green; the suite 1544 passed, 5 skipped. Two guards updated
  deliberately with the change, the reason in the commit: WP82's parity guard gained the three `run` options and their
  `StartRun` fields (the body may pin the models and URL per run, over the project's setting, over the environment —
  without them the guard would have called the new options unreachable from the workbench), and the client-factory
  guard sees `base_url` on the first-party client (`None` keeps the SDK's default). One of this WP's own guards was
  corrected before the change landed: the default path of `default_agents` builds no caller at all — each agent makes
  its helper lazily from `.env` when first used — so the guard asserts exactly that.
- **P2 ✔.** `vault-agent run --primary-model … --heavy-model … --anthropic-base-url …` records the three in
  `pending.json`; `resume --owner …` on that run rebuilt its agents with the same options (the guard counts two builds,
  both with the pointer's options); a workbench run on a project with settings carries
  `--target-platform databricks --primary-model … --heavy-model … --anthropic-base-url …` in its first CLI equivalent,
  `llm` in `run.json` and in its pointer; the body's own platform wins.
- **P3 ✔ with one claim left to CI.** ruff, bare mypy, `tsc --noEmit`, `vitest run` (32); manual 6 (the option row) and
  14.2 (the two routes, the Settings section) gained their rows. The `vault_agent.ui` floor was not re-measured here;
  CI measures it on the push, and the new routes and store methods are covered by the new guards.
- **One design decision made while building, recorded:** the agents' helper classes (`Anthropic…Extractor`, `…Enricher`,
  `…Proposer`) take the options, not the agents — the agents take a helper, as the keyless suite has always injected
  one; `default_agents(options)` builds the helpers with the models and URL and the default path is byte-identical.
