# WP1 — Four new validator gates

Status: Proposed · Size: S/M · Depends on: WP4 (ValidationIssue) · Blocks: WP8

## 1. Problem

Project review 2026-07-06, finding 4: four correctness holes in the validator
(`src/vault_agent/agents/validator.py`). All four are cheap deterministic checks; two of
them let the generator emit SQL that a warehouse will reject or that is silently wrong.

## 2. New gates [ENFORCE]

Follow the existing pattern exactly: issues via `_issue(...)`, error codes `E_*`, warning
codes `W_*`, stable and sorted output, one focused test per gate. Docstring at module top
and the CLAUDE.md "gates" wording must be updated to the new issue-code count.

### Gate 1 — `E_EFFSAT_DATE_ORDER` / `W_EFFSAT_DATE_ORDER_UNVERIFIED`

*Hole:* the generator takes `attributes[0]` as start and `attributes[1]` as end
(`code_generator._render_eff_sat`). An LLM emitting `["effective to", "effective from"]`
produces a silently inverted effectivity satellite. `rules.effectivity_date_pair()`
already classifies from/to tokens and is the single source of truth — reuse it, do not
re-implement token matching.

For every `sat.sat_type == "effectivity"` with exactly 2 attributes (the `!= 2` case is
already `E_EFFSAT_DATES`):

- `pair = effectivity_date_pair(sat.attributes)`
- `pair == (attributes[1], attributes[0])` (i.e. recognisably *reversed*) →
  `E_EFFSAT_DATE_ORDER`, message naming both attributes and stating the required order
  `(start, end)`.
- `pair is None` (tokens unrecognisable, order unverifiable) →
  `W_EFFSAT_DATE_ORDER_UNVERIFIED` — a warning, because a heuristic non-match must never
  hard-fail a legitimate model (same reasoning as `W_SAT_MAYBE_EFFECTIVITY`).
- `pair == (attributes[0], attributes[1])` → no issue.

### Gate 2 — `E_SAT_DUP_ATTR`

*Hole:* `_check_cross_construct` collects attribute owners into a `set`, so a duplicate
attribute *within one* satellite passes silently, and the generator emits a duplicate
payload column → Postgres rejects the model at `dbt build`.

For every satellite: flag when two attributes normalise to the same identifier
(`rules.normalize_identifier`) — this covers both exact duplicates and lossy-normalisation
duplicates (`"customer-id"` vs `"customer id"`). One issue per colliding identifier,
construct = the satellite, message naming the colliding labels and the resulting column.
Check `attributes + child_dependent_key` as one namespace (both end up as staging/payload
columns). Severity **error**: the generated SQL cannot build.

Note: the generator's `_collision_warnings` stays (defense in depth, different stage);
this gate makes the failure blocking *before* generation.

### Gate 3 — `E_HUB_HK_COLLISION`

*Hole:* the hub hash key derives from `source_entity`
(`code_generator._hub_hashkey` → `normalize(source_entity) + "_HK"`). Two hubs sharing a
`source_entity` (but different business keys) get the *same* HK column name and the *same*
staging model; the staging generator's per-name dedup then binds the second hub's HK to
the first hub's business key — silently wrong data.

Group hubs by `normalize_identifier(hub.source_entity)`; for groups > 1 whose members do
**not** all share the same normalised business key → `E_HUB_HK_COLLISION`, construct =
comma-joined hub names (sorted), message explaining the shared `X_HK`/staging collision.

### Gate 4 — `E_DUP_HUB`

*Hole:* `W_BK_COLLISION_RISK` fires only for the same BK across *different* source
entities. Same BK **and** same source entity on ≥ 2 hubs is the complementary case: the
same business concept modelled twice ("one hub per business key", DV_MODELING_RULES[0]).

Group hubs by `(normalize_identifier(business_key), normalize_identifier(source_entity))`
(skip empty BKs — already `E_HUB_NO_BK`); groups > 1 → `E_DUP_HUB`, construct =
comma-joined hub names (sorted). Severity **error**.

Gate 3/4 interplay: a pair of identical hubs trips **only** `E_DUP_HUB` (gate 3 excludes
same-BK groups by construction). Add a test pinning this.

## 3. Consistency fix (same WP)

The generator accepts eff-sats with `len(attributes) >= 2` and uses the first two
(`code_generator._render_satellite`), while the validator errors on `!= 2`
(`E_EFFSAT_DATES`). Align the generator to the validator: `len(sat.attributes) != 2` →
flag (`FlagKind.GENERATION_GAP`) and skip, message as today. Update the generator test
that covers the `< 2` branch to also pin the `> 2` rejection.

## 4. Modeler prompt [GUIDE]

Add one line to the rules injected into the modeler prompt (in
`rules.DV_MODELING_RULES`): effectivity satellites carry exactly two date attributes in
`(start, end)` order. (Do not mention the token heuristic — prompts state rules, not
implementation.)

## 5. Tests

`tests/test_agents/test_validator.py`, one test per gate + the interplay test + a
no-false-positive test (the existing happy-path model produces none of the four codes).
Reversed/unverifiable eff-sat fixtures; a satellite with `["customer-id", "customer id"]`;
two hubs sharing `source_entity`; two identical hubs. Generator alignment test in
`test_code_generator.py`.

## 6. Acceptance criteria

1. All four gates fire on their fixtures with the exact codes above; happy path unchanged.
2. `E_SAT_DUP_ATTR` makes the messy-model path fail *before* dbt would
   (`validation_report.passed is False`).
3. Bank demo guardrails untouched (its model trips none of the gates).
4. CLAUDE.md + `validator.py` module docstring reflect the new issue-code count.
5. Standard DoD.
