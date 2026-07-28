# WP20 — Construct-name gate and filesystem hardening

Status: Proposed · Size: S · Depends on: — · Source: project review 2026-07-28,
findings 4 + 5

## 1. Problem

**(4) LLM-derived construct names are trusted at the filesystem and dbt boundary.** No
gate validates name well-formedness. `write_outputs` does `models_dir / f"{name}.sql"`
with `name` from the model constructs, and `contracts_dir / f"{asset}.contract.yml"` with
the asset name (`cli.py:99-138`); a name containing a path separator or `..` writes
outside the output directory, and a name with spaces/uppercase produces dbt models that
cannot be referenced. `report.py` treats every state string as hostile; the write path
does not. Related inconsistency: a `source_table` satellite's staging name normalises the
base (`code_generator._sat_staging_model`) while every other staging name uses the raw
base (`staging_generator._staging_name`) — two naming paths that agree only for
well-formed names.

**(5) `E_SAT_ATTR_OVERLAP` matches raw strings.** `validator.py:367-371` keys the
cross-satellite overlap check on the raw attribute label while `E_SAT_DUP_ATTR` (within
one satellite) normalises: "Customer ID" in sat A and "customer_id" in sat B of the same
parent — the same generated column twice on one parent — passes the gate.

## 2. Target design [ENFORCE]

### 2.1 `E_BAD_NAME` validator gate

New rule constant in `rules/dv2_rules.py` (single source of truth, with the DV rationale
in a comment): `CONSTRUCT_NAME_PATTERN = ^(hub|link|sat)_[a-z0-9][a-z0-9_]*$` plus a
`is_valid_construct_name(name)` helper. Validator: every hub/link/satellite name that
does not match → `error, E_BAD_NAME, <name>`, message naming the offending characters and
the expected pattern. This blocks before generation (the re-model loop feeds it back),
mirroring how `E_SAT_DUP_ATTR` pre-empts the build error. Verify the demo/eval fixtures
and the WP10 per-source generated names (`_sat_source_name`, `multi_source_staging_name`
outputs are derived, not validated — but their *inputs* now are) all comply.

### 2.2 Steering line (registry entry, deliberate prompt change)

Add a `SteeringRule` `construct_naming` (text: names are `hub_`/`link_`/`sat_` +
lowercase snake_case, nothing else; `backstop=None`; origin: review 2026-07-28 finding 4,
gated by `E_BAD_NAME`) — steering avoids burning modeling retries on a deterministic
formality. NOTE: this changes the rendered modeler prompt, which
`tests/fixtures/steering/modeler_rules_pre_wp16.txt` pins. That fixture guards the WP16
*migration* (registry renders exactly what shipped); a deliberate rule addition updates
the fixture in the same commit and adds the rule's row to
`docs/architecture/steering-ledger.md`. State this in the commit body — a silent fixture
update is exactly what the pin exists to prevent.

### 2.3 `write_outputs` defense in depth

Before writing any artifact whose filename derives from state (model names, staging
names, contract asset names, ADR filenames): reject a component that contains a path
separator, `..`, or control characters — raise `ValueError` naming the artifact and the
offending name. **Refuse, never silently rename** (house rule: never silently guess).
With §2.1 upstream this should be unreachable for constructs; contract asset names come
from declared source tables or LLM entity names and get the same check.

### 2.4 Unify staging-name normalisation

Make `staging_generator._staging_name` (and the mirrored `code_generator._staging_model`)
normalise the base the way `_sat_staging_model` already does
(`normalize_identifier(base).lower()`). For every well-formed name this is byte-identical
(`normalize("account").lower() == "account"`); pin that with the existing
staging-regression fixture. One naming path, not two that happen to agree.

### 2.5 Normalise `E_SAT_ATTR_OVERLAP`

Key the per-parent attribute-overlap map on `normalize_identifier(attr)`; report the
original labels (the `E_SAT_DUP_ATTR` message pattern). Same-normalised variants across
two satellites of one parent now error.

## 3. Tests

1. `E_BAD_NAME`: space, uppercase, `../`, missing prefix each caught; all existing
   fixtures/demo models pass untouched.
2. Steering: rule id unique, prompt fixture updated, ledger row present (extend
   `tests/test_steering.py` pins).
3. `write_outputs`: hostile model name and hostile contract asset name each raise an
   attributable `ValueError`; nothing written outside `out_dir` (assert via tmp-path
   listing).
4. Staging-name unification: ungrounded bank output byte-identical
   (`tests/fixtures/staging_ungrounded_baseline/` untouched).
5. `E_SAT_ATTR_OVERLAP`: "Customer ID" vs `customer_id` across two sats → error; the raw
   exact-match case still errors; disjoint attributes stay clean.

## 4. Acceptance criteria

1. No LLM-derived string reaches the filesystem unvalidated (gate + write guard), and the
   guard refuses rather than renames.
2. Bank demo guardrails and the staging byte-identity fixture pass untouched.
3. The prompt change is explicit: fixture + ledger updated in the same commit, named in
   the commit body.
4. Standard DoD.

## 5. Out of scope

Renaming/migrating any existing generated output, Unicode normalisation beyond
`normalize_identifier`, and validator-count docstring drift (WP21 hygiene).
