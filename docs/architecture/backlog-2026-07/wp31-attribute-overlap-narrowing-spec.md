# WP31 — Narrowing `E_SAT_ATTR_OVERLAP` to one payload namespace

Status: **Approved** (2026-07-30, Mischa) · Owner: Mischa Eismann · Date: 2026-07-30
Implements: **ADR-0012** (Proposed → this WP's live measurement is its acceptance signal)
Origin: WP30 §7.3 Finding 2 — the independent AdventureWorks instrument failed validation on
its two largest subject areas, both on this gate.

## 1. Problem

`E_SAT_ATTR_OVERLAP` treats any repeated attribute label among the satellites of one parent as
an error. On a schema with per-entity history tables — Microsoft's `ProductCostHistory` and
`ProductListPriceHistory`, both hanging off `Product` — the correct model trips it: each
satellite declares its own `source_table` (WP7 §7.1) and each has its own `EndDate`, which is a
different column of a different relation. Nothing collides; the gate errors anyway, the modeler
burns all `MAX_MODELING_ATTEMPTS`, and the run ends at exit 3 with no valid model.

The same run set also produced a **true** positive of the same code (`Sales`: `ModifiedDate` in
two satellites drawn from one relation), which is why this is a narrowing and not a downgrade.
ADR-0012 holds the full evidence and the decision; this spec is the implementation contract.

## 2. Target design [ENFORCE]

### 2.1 One helper answers "which relation feeds this satellite?"

`rules.satellite_payload_relations(satellite, parent) -> frozenset[str]`, in
`rules/dv2_rules.py` beside `satellite_feed` / `source_table_on_multi_source_hub`, `Any`-typed
like them so `rules/` stays free of the state models. Normalised names throughout
(`normalize_identifier`), per ADR-0012's table:

- declares `source_table` → `{that table}`
- no `source_table`, hub parent, no `sources` → `{hub.source_entity}`
- no `source_table`, hub parent with `sources` (WP10) → every feed's table (the satellite splits)
- no `source_table`, link parent → `{"link:" + normalised link name}` — a marker, not a
  relation: a link's staging is derived from its participations and has no single source table.
  It only ever has to compare equal to itself.
- unresolvable parent → empty set, which makes the gate keep today's behaviour (see §2.2). A
  missing parent is `E_SAT_UNKNOWN_PARENT`'s complaint, not this gate's.

Effectivity satellites ignore `source_table` (they stage with their parent link — WP7), so the
helper must too, exactly as `satellite_feed` already does. Not a special case to remember: it is
the same one-line guard, and a test pins it.

### 2.2 The gate splits by namespace intersection

Grouping stays as it is (normalised label per parent, original labels reported — WP20 §2.5).
Each group of ≥ 2 owning satellites is then split:

- any two owners whose relation sets **intersect** → `E_SAT_ATTR_OVERLAP` (error), message
  byte-identical to today's for the same owner set. This is what keeps the `Sales` case failing.
- otherwise → `W_SAT_ATTR_OVERLAP_CROSS_SOURCE` (warning), message naming the relations, so the
  reader can see why it is only a warning.

**Empty relation sets intersect nothing**, which would silently turn an unresolvable-parent
overlap into a warning. Guard it explicitly: an owner with an empty set is treated as sharing a
namespace with every other owner in the group — an unknown relation must never *lower* a
severity. Pinned by a test.

Validator codes go 34 → 35 (the code stays the source of truth; the docstring carries no count).

### 2.3 Steering for the class that stays an error

One WP16 `SteeringRule` (`attribute_one_satellite`), `backstop=None`: a gate refuses, it does not
repair, and deciding *which* of two satellites keeps a duplicated column is a modelling decision,
not a deterministic repair. Name the audit-column trap explicitly — a last-modified timestamp
repeated in every satellite is what the live run actually produced. Regenerate
`tests/fixtures/steering/modeler_rules_pre_wp16.txt` and add the ledger row in the SAME commit,
asserting while regenerating that the pre-WP16 block is still a byte-identical prefix (the
WP20/WP28 precedent).

### 2.4 Out of scope, deliberately

- Whether audit columns (`ModifiedDate`, `rowguid`) belong in satellites at all. A denylist would
  make the `Sales` failure vanish without deciding anything (ADR-0012, alternatives).
- WP30 Finding 1 (the source-mapper concept collision). Separate defect, separate WP; bundling a
  wrong-data fix with a gate narrowing would make both harder to review.
- WP30 Finding 3 (`mapping_coverage` calibration) — eval-side, and explicitly not to be changed
  in reaction to a bad result.

## 3. Tests (keyless)

1. Two satellites on one parent, each with its own `source_table`, sharing an attribute label →
   **warning**, not error; the message names both relations.
2. Two satellites on one parent, neither declaring `source_table`, sharing a label → **error**,
   message byte-identical to the pre-WP31 text (the `Sales` shape; regression guard).
3. One satellite declaring `source_table` equal to the parent hub's own `source_entity`, the
   other declaring none → **error** (same relation written two ways).
4. WP10: a split satellite (no `source_table`) and a WP28 feed-bound satellite on the same
   multi-source hub, sharing a label → **error** (their relation sets intersect on that feed).
5. Two feed-bound satellites on the same multi-source hub, bound to *different* feeds → warning.
6. Unresolvable parent name → **error** (an unknown relation never lowers severity).
7. Satellites on a *link* parent, neither with `source_table`, sharing a label → error.
8. Effectivity satellite: `source_table` is ignored, so an eff-sat and a standard satellite on
   one link parent that share a label → error.
9. The helper itself, parametrized over the five rows of the ADR-0012 table.
10. Registry/ledger pins for the new steering rule (id present, `backstop is None`, fixture
    regenerated, ledger row exists).
11. Replay pin: the exact `Production` and `Sales` satellite shapes from the WP30 traces produce
    warning-only and error respectively — the measurement turned into a test so it cannot regress.

## 4. Acceptance criteria

1. All of §3 green; ruff + mypy strict clean.
2. **Primary (ADR-0012's own signal):** a live `adventureworks_production` run no longer raises
   `E_SAT_ATTR_OVERLAP` for the two history satellites, and its validation passes.
3. **Secondary, reported not gated:** a live `adventureworks_sales` run — the `ModifiedDate`
   error is *expected to stay* an error. Whether the re-model loop resolves it measures §2.3's
   steering rule, not this ADR. If it does not resolve, record the finding; do **not** weaken the
   gate that is right.
4. No greenfield regression: the staging baseline fixture, both demo guardrails and the WP24
   composition matrix pass untouched. This WP changes a validator severity and adds a rules
   helper — no rendered template changes, so a Postgres re-verification is not required and is
   not performed.
5. The gate catalogue (`docs/operations/08-validation-gates.md`) carries the narrowed meaning,
   the new warning row and the corrected count, and the dv2-rules cheatsheet agrees.

## 4a. Acceptance results — 2026-07-30

All five criteria **MET**. 700 tests green (+20), ruff clean, mypy strict clean (44 files); the
staging baseline, both demo guardrails and the WP24 composition matrix passed untouched, so no
Postgres re-verification was required (§4.4) and none was performed.

**Primary signal (§4.2) — met.** A live `adventureworks_production` run raises **zero**
`E_SAT_ATTR_OVERLAP`; the three `hub_product` overlaps are `W_SAT_ATTR_OVERLAP_CROSS_SOURCE`,
each naming its satellites' relations, and validation **passes**. It converged in **one** modeler
attempt rather than exhausting all three, so the fix also returns the re-model budget it was
wasting: 75.8k → 65.6k output tokens, 668 → 589 s, $3.69 → $3.02.

**Secondary signal (§4.3) — reported, and better than expected, with the caveat stated.** The
`sales` run also passes validation in one attempt, and the `ModifiedDate` duplication **did not
recur**. The plausible cause is §2.3's `attribute_one_satellite` steering rule, but **n=1 cannot
separate a steering effect from sampling variance** — the honest reading is one favourable
datapoint, not a demonstrated effect, and the ledger row records it that way. Note what is *not*
in doubt: had the duplication recurred, it would still have been an error, because the narrowing
does not touch that class (pinned by
`test_the_adventureworks_sales_shape_still_fails`).

Side effects worth recording, both consequences of a model that now validates:

- Review load collapsed — `production` 101 → 45 items, `sales` 128 → 50. Validation errors had
  been dominating both queues.
- `mapping_coverage` rose from 0.000 to 0.222 / 0.600, because on the failed path WP25
  deliberately skips the source mapper: the earlier zeros were **zero proposals**, not bad
  mapping. That correction is written into WP30 §7.3, where the misleading numbers live.

## 5. Budget

Two live runs at 1 repeat (`production` ≈ $3.70, `sales` ≈ $3.60) ≈ **$7.50**. WP30 has spent
$13.59 of its $40–60 ceiling; this comes out of the same envelope and leaves the arm comparison
affordable.
