# Kick-off WP9.1 — Mapping remediation (review findings 2026-07-13)

You are a senior data engineer fixing three review findings in the WP9 mapping
implementation. This kick-off is self-contained (spec inline — the fix is small and
precise); do not expand scope. Requires a live API key (.env) for the re-measurement —
run locally.

## Read first
1. `CLAUDE.md` (canon; note its WP9 milestone paragraph — you will correct part of it).
2. `docs/architecture/backlog-2026-07/wp9-mapping-spec.md` §10.2/§10.5 (the acceptance
   criteria in dispute) and `spike-mapping-results.md` (the D4 band + trap autopsy — the
   spike's variant B mapped `partner number` → `VICTOR_PARTNER.PARTN_NR` 5/5 *while
   `TVERTRAG.PARTN_NR` existed as an FK*; that is the behaviour to restore).
3. `src/vault_agent/agents/source_mapper.py` (all), `src/vault_agent/prompts/source_mapper.md`,
   `tests/test_agents/test_source_mapper.py`, `eval/datasets/messy_insurance/source_schema_enriched.yml`.

## The findings

**F1 — Over-broad multi-source deferral (blocks §10.2).** The prompt rule "a business key
with MORE THAN ONE legitimate source column → unresolved" is applied by the model to
**FK occurrences inside the same source system** (bank: `NATIONAL_CUSTOMER_ID` in
`raw_customer` + the `raw_account_customer` relationship table; messy: `PARTN_NR` in
`VICTOR_PARTNER` + `TVERTRAG` whose comment literally says "FK to VICTOR_PARTNER.PARTN_NR").
An FK reference is NOT a second source: the hub's feed is the entity-anchor table. Effect:
live messy accuracy 0.870 vs. the spike band [0.98–1.00] (§10.2 violated), and on realistic
schemas EVERY hub key parks in `unresolved`, so the §6 auto-binding never fires.

**F2 — `rebind_staging` leaves artifacts inconsistent.** It refreshes only
`state.artifacts.staging_models`; `automatedv_yaml["staging"]` metadata and the scaffolding
(sources.yml expected-columns doc, README inputs) keep the pre-rebind bindings.

**F3 — Milestone misstates F1 as a success.** CLAUDE.md's WP9 paragraph celebrates
"correctly detected BOTH hub keys as multi-source (present in the hub table AND the
account_customer link table)" — that detection is the F1 bug, not a feature.

## The fixes

1. **Prompt (`prompts/source_mapper.md`):** replace the multi-source rule with:
   defer (`unresolved` + candidates in evidence) ONLY when a business key is anchored in
   entity tables of **different source systems** (e.g. VICTOR vs. CRM). A column that is a
   **foreign-key reference** to another candidate's table (comment marks it FK, or it sits
   in a relationship/transaction table referencing the entity) is NOT a second source —
   map to the **entity-anchor table**. Keep the never-guess rule for genuine ambiguity.
2. **Deterministic FK-demotion in `_post_validate` (belt and braces, keyless-testable):**
   when the proposer returns `unresolved` for a `business_key` with ≥2 `TABLE.COLUMN`
   candidates in evidence AND all but one candidate's `SourceColumn.comment` marks it as an
   FK referencing the remaining candidate's table (case-insensitive: comment contains "FK"
   or "foreign key" AND the anchor table's normalised name), auto-resolve to the anchor
   candidate: category per the normal `_category` tiers, evidence extended with
   `"fk-demotion: <demoted candidates>"`. No comments / genuinely cross-system → stays
   `unresolved` (honest). Post-validation still never invents a column.
3. **`rebind_staging`:** apply the full `build_staging` result — `staging_models`,
   `automatedv_yaml["staging"]` metadata, and `scaffolding` — not just the models. Add a
   keyless test: after a rebind, metadata source_model and sources.yml agree with the
   re-bound staging.
4. **CLAUDE.md:** correct the WP9 paragraph (F3) and append a dated WP9.1 paragraph with
   the re-measured numbers. Do not silently rewrite history — state what was wrong.

## Re-measurement (acceptance)

- `messy_insurance` live eval (≥5 repeats): `mapping_accuracy` back in the spike band —
  gate ≥ 0.95; the synonym concept may stay unresolved (scorer-acceptable per memo
  thin-evidence #4); gap_detection stays 1.000; the statistics trap stays correct
  (PARTN_NR, never PARTN_GUID — verify per run).
- `bank` live eval: both hub keys resolve (`national customer ID` → customer table,
  `account number` → account table); recall 6/6; staging auto-binds both without `--map`.
- Keyless: new FK-demotion tests (resolve case, no-comment stays unresolved, cross-system
  stays unresolved), rebind-consistency test; full suite + ruff + mypy green; ungrounded
  byte-identity guards untouched.

## Out of scope
WP9 §10.7 (opacity probe) and §10.8 (Postgres re-verify) remain open items of WP9 proper —
do not fold them in here unless trivially convenient. WP10 unchanged.

## Definition of Done
All fixes in; re-measurement numbers pasted into the final report AND recorded in
CLAUDE.md; conventional commits referencing this kick-off. Report format: findings fixed
(met/not-met + evidence), measured tables, anything still open.
