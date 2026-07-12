# Kick-off WP10 — Multi-source hub

You are a senior data engineer with deep Data Vault 2.0 expertise implementing exactly ONE
work package for the vault-agent project. Do not expand scope.

## Read first, in this order
1. `CLAUDE.md` — repo canon (binding).
2. `docs/architecture/backlog-2026-07/00-overview.md` — §Shared conventions + DoD.
3. `docs/architecture/backlog-2026-07/wp10-multi-source-hub-spec.md` — your spec.
4. `docs/architecture/backlog-2026-07/spike-mapping-results.md` Q6 + thin-evidence #5 —
   why the hub key MUST be harmonised (hash-identity across sources) and why satellite
   names stay source-faithful.
5. Code: `state.py` (Hub; the WP8 `LinkHubRef` union pattern to mirror),
   `rules/dv2_rules.py`, `agents/code_generator.py` (`_render_hub`),
   `agents/staging_generator.py`, `agents/validator.py`, WP9's ratification-file handling.
6. AutomateDV 0.11.4 docs for the `hub` macro's source_model **list** form — verify against
   the pinned version, not memory (the WP8 t_link incident is the cautionary tale).

## Preconditions
WP9 merged. If not: STOP and report.

## Order of work
1. Byte-identity guards for single-source hubs FIRST (model + staging + hub SQL).
2. `Hub.sources` + `HubSource` (union/normalisation per WP8 pattern) +
   `rules.canonical_hub_key_column` (business term only when sources disagree — decided
   policy, do not revisit).
3. Staging per HubSource with canonical-key `derived_columns` alias; `_render_hub`
   source_model list; sat-per-source with `record_source` split.
4. Validator additions (duplicate feed error; per-source grounding warnings).
5. Ratification `sources:` form (WP9 file) for resolving multi-candidate keys into
   `Hub.sources`.
6. Postgres proof (spec §4.1): same key value via both stages → ONE hub row, matching X_HK.

## Constraints
- The integration property is the point: assert hash-input identity across stages in a
  unit test AND row identity on Postgres.
- Same-as links stay out of scope — flag, never merge differing keys.
- Postgres available per the WP7/WP8 sandbox pattern, or deliver as documented open step.

## Definition of Done
Spec §4 acceptance criteria · pytest/ruff/mypy green · single-source byte-identity holds ·
CLAUDE.md milestone paragraph · conventional commits referencing the spec.

## Final report
Deliverables, verification tails incl. the Postgres query results, §4 checklist
(met/not-met + evidence), open human-verification steps.
