# WP24 — Multi-source hub composition correctness

Status: Proposed · Size: S/M · Depends on: — · Source: project review 2026-07-29,
findings 2 + 3

## 1. Problem

Two feature combinations produce silently wrong output. Both were reproduced against the
current code; neither is covered by a test or a gate.

**(2) A link or `source_table` satellite hashes a different column than its multi-source
hub does.** `rules.canonical_hub_key_column()` is the declared single source of truth for a
hub's staging key column (WP10 §2.2), but only two call sites use it
(`staging_generator.py:144` for the hub's own per-source specs, `code_generator.py:141` for
`src_nk`). Link participations (`staging_generator.py:175`), a `source_table` satellite on a
hub parent (`:205`), and one on a link parent (`:213`) still use
`_to_column(hub.business_key)`. When a multi-source hub's feeds *agree* on a physical column
name that differs from the business-key label, the two disagree:

```
stg_customer_crm_customer:  CUSTOMER_HK <- CUSTOMER_KEY   # canonical (the hub)
stg_account_customer:       CUSTOMER_HK <- CUSTOMER_ID    # the link's FK
```

The FK can never match the hub's hash key — wrong data, no error. Every existing test and
the WP10 Postgres verification use the *disagreeing* feed case, where canonical coincides
with `normalize(business_key)`, so the suite is blind to it.

**(3) WP7 + WP10 emit a dbt project that cannot build.** A satellite declaring
`source_table` on a multi-source hub takes the `source_table` branch in
`collect_staging_specs` (`staging_generator.py:191`) — one staging model, carrying the
hashdiff — while `code_generator.py:455-478` ignores `source_table` on the multi-source path
and emits one satellite per source reading `stg_<entity>_<source>`. Result:
`sat_customer_details_{crm,victor}` reference `CUSTOMER_DETAILS_HASHDIFF`, which only the
orphaned `stg_customer_details` computes. `dbt build` fails; `state.flags` is empty.

## 2. Target design [ENFORCE]

### 2.1 One helper for every hub-key hash

Every place that hashes or stages a hub's business-key column goes through
`canonical_hub_key_column(hub)` — never `_to_column(hub.business_key)` directly. Concretely
in `staging_generator.collect_staging_specs`: the link-participation loop (the `role_bk_column`
input), the `source_table`-satellite branch for a hub parent, and the same branch's link-parent
path. The single-source case is unchanged by construction (`canonical_hub_key_column` returns
`normalize_identifier(business_key)` when `sources` is empty), so ungrounded/single-source
output stays byte-identical — pin that with the existing staging regression fixture before
changing anything.

Role qualification composes unchanged: `role_bk_column(canonical_hub_key_column(hub), role)`.

### 2.2 Reject the unsupported WP7 + WP10 combination — never emit unbuildable SQL

A satellite that declares `source_table` **and** hangs off a hub with `sources` has no
defined semantics (one finer-grain relation cannot be the payload source of two independent
feeds whose rows are distinguished by `record_source`). Handle it the way the neighbouring
unsupported case already is (`code_generator.py:461`, non-standard sat type on a
multi-source hub): flag `FlagKind.GENERATION_GAP` with the satellite as `asset`, generate
nothing for it, and — the part that branch is missing — make sure the staging generator
agrees, i.e. `collect_staging_specs` must not emit the orphaned `stg_<sat base>` model for a
satellite the raw-vault generator skips.

Plus a validator gate so the human is told **before** generation and the re-model loop gets
the feedback: `E_MASAT_MULTI_SOURCE_PARENT` (error) — satellite declares `source_table`
while its parent hub declares `sources`. Message names both. (Name it for what it checks,
not for the WP.)

### 2.3 The composition matrix is the deliverable, not the two fixes

Add a test module (`tests/test_agents/test_feature_composition.py`) that exercises the
cross-product of the three model features that touch staging naming and hashing — WP7
`Satellite.source_table`, WP8 role-qualified participations, WP10 `Hub.sources` — with one
assertion per cell: either it generates and the hash inputs agree across every model that
references the same target column, or it is flagged/gated. The two defects above are two
cells; the point of the WP is that the empty cells stop being empty. State in the module
docstring which cells are deliberately "flagged, not generated".

Hash-input agreement is checkable deterministically: for one model, collect
`{target_column: {hash inputs}}` across all staging specs and assert every target has
exactly one input set. That single invariant catches finding 2 and any future repeat.

## 3. Tests (keyless)

1. Byte-identity guard FIRST: `tests/fixtures/staging_ungrounded_baseline/` and the bank
   demo guardrails unchanged (single-source path untouched).
2. Multi-source hub with *agreeing* feed column names + a link to it → the link's FK hashes
   the canonical column (the probe above, as a pinned test).
3. Same, with a `source_table` satellite on a link parent whose hub is multi-source.
4. Role-qualified participation on a multi-source hub → `COUNTERPARTY_<canonical>`.
5. `source_table` satellite on a multi-source hub → `E_MASAT_MULTI_SOURCE_PARENT` from the
   validator, `GENERATION_GAP` flag from the generator, no `sat_*` model, **and no orphan
   staging model**.
6. The invariant test of §2.3 over every fixture model in the suite.

## 4. Acceptance criteria

1. No generated model can hash the same target column from two different inputs (invariant
   test, over every fixture model).
2. No feature combination emits SQL that cannot build without a flag naming it.
3. Single-source output byte-identical (fixtures + demo guardrails untouched).
4. Standard DoD; the composition matrix module lists every cell with its expected outcome.

## 5. Out of scope

Giving the WP7+WP10 combination real semantics (per-source finer-grain payloads) — that
needs a modelling decision and an ADR, not a bug fix. Same-as links, and any change to
`canonical_hub_key_column`'s policy (WP10 §2.2 stands).
