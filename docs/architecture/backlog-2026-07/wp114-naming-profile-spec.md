---
type: spec
status: not-measured
updated: 2026-10-31
---

# WP114 — A `NamingProfile` in `rules/` beside the platform profile (C3, the naming half)

Status: **Approved and in progress** (2026-10-31, the owner's word: the old backlog) · Owner: Mischa Eismann ·
Author: Claude. C3's second half; the settings half is WP113.

## 1 What is missing

The physical names the generator writes are six module constants in `rules/dv2_rules.py` — `stg_`, `_HK`,
`_HASHDIFF`, `LOAD_DATETIME`, `RECORD_SOURCE`, `APPLIED_DTS` — plus the convention that technical names are
upper snake case; 34 sites in the code generator, 17 in the staging generator, one each in the contracts, the
validator, the extension diff and the subject areas read them, and two sites spell `stg_` as a literal. A client with
a house style (`load_dts`, `_hk`, lower case) cannot have it without editing the package; and nothing records which
style a vault was generated under, so an extension could be generated under another and miss its own tables.

## 2 The rules

1. **One typed profile.** `rules/naming.py`: `NamingProfile` (pydantic, frozen) — `staging_prefix`, `hashkey_suffix`,
   `hashdiff_suffix`, `load_datetime`, `record_source`, `applied_dts`, `technical_case` (`upper`/`lower`) — with
   `stage(construct)`, `hashkey(base)`, `hashdiff(base)` and the three column names folded to the case. `DEFAULT_NAMING`
   is today's house style, and the six constants in `dv2_rules` become its values (kept as names, so nothing else
   moves). Construct prefixes (`hub_`/`link_`/`sat_`) stay the modeler's and `E_BAD_NAME`'s: the profile names what the
   generator writes, not what the model is called. CamelCase and case-sensitive names stay deferred (C3: they need
   quoting everywhere and a build per platform).
2. **Threaded, never global.** `VaultAgentState.naming` (default the house style, persisted with the checkpoint like
   `target_platform`); the code generator reads it from the state and hands it to every renderer; `build_staging(…,
   naming=)` hands it to the specs, the stage names, the zero-key view, the seed types and the README; the contracts'
   dbt model name, the validator's prefix strip, the extension diff's owner match, the subject areas and the mapper's
   stage lookup take it from the state; `stage_model_name(construct, naming)` and the carried tier of
   `resolve_link_relation(…, naming=)` take it from the caller. Defaults everywhere are the house style, so every
   existing call renders as before.
3. **Persisted with the vault, adopted by an extension.** `write_outputs` writes `metadata/naming.yml` when the
   profile is not the default (the greenfield manifest stays frozen); `load_existing_naming(path)` reads it, the house
   style when absent. A `run --existing` adopts the vault's profile; a `--naming-profile` that disagrees with it is an
   attributable error before any model is called (the generated names would miss the tables that hold history).
4. **Chosen per run and per project.** `run --naming-profile FILE` (YAML with the fields; a bad value is the loader's
   message, exit 1). The workbench: `ProjectSettings.naming`, a run writing `<out>/naming-profile.yml` when not the
   default so its CLI equivalent (`--naming-profile <that file>`) reproduces it, `run.json` recording `naming`; the
   Settings section gets the seven fields. `StartRun.naming` for parity with the CLI option.

## 3 Not this WP

Renaming an existing vault (a migration this project never performs); construct prefixes; CamelCase or quoted
identifiers; a per-construct override; the eval cases (house style).

## 4 Acceptance (keyless)

`tests/test_wp114_naming_profile.py`, committed red (import): the default equals the house style and renders
byte-identically (an explicit equality beside the frozen fixtures); a lower-case profile through the generator — hub
`src_pk`/`src_ldts`/`src_source`/`source_model`, the satellite's hashdiff, the effectivity satellite's `src_eff`, every
staging model under the prefix with the folded hash columns and technical columns, the README, the seed types, the
contracts' model name, the extension diff's owner; the state carrying the profile; `write_outputs` persisting a
non-default one only; the CLI taking a file, an extension adopting its vault's profile, a disagreeing file refused,
a bad value refused; the workbench storing it, validating it, a run recording and carrying it with the equivalent.
`Project.test.tsx`: the naming fields saved.

## 5 Pre-registration (keyless)

- **P1** Every byte-identity guard unchanged — the greenfield manifest, the ungrounded and Databricks baselines, the
  WP7/WP10/WP23 fixtures, the bank demos — with the constants now read from the default profile.
- **P2** The lower-case bank project written to disk parses with dbt (`project_check.dbt_parse`, the throwaway
  profile): the names agree across staging, raw vault and contracts, so no `ref()` or column name dangles.
- **P3** Suite, ruff, bare mypy, `tsc`, `vitest`; WP82's parity guard gains `naming_profile` → `naming`.

## 6 Measured

Appended after the run.
