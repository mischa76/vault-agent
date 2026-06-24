# Remediation Spec — Reality-test findings, batch 1 (#2 eff_sat gate, #3 review-queue noise)

> **Purpose.** Implement the two highest-leverage findings from the
> [reality test](../reality-test.md): an **effectivity-satellite consistency gate** (#2) and
> **review-queue aggregation** (#3). Both are deterministic (no LLM, no API key). Same
> `[ENFORCE]`/`[GUIDE]` discipline as the other specs; implementation by Claude Code.
>
> **Author of spec:** review pass, 2026-06-17. Keep `ruff` / `mypy --strict` / `pytest` green.
> Out of scope here: findings #1 (contradiction reconciliation), #4 (typed schema), #5 (multi-role
> pattern), #6 (minor) — tracked in `reality-test.md`.

---

## Finding #2 — Effectivity-satellite consistency gate [ENFORCE]

**Observed.** On the messy run, `sat_contract_partner_role_effectivity` was emitted as a **standard**
satellite (it has `src_hashdiff`, no `src_dfk`/`src_sfk`) whose payload is `[EFFECTIVE_FROM,
EFFECTIVE_TO]` — i.e. it is *named/intended* as effectivity but modelled as a plain sat, carrying a
from/to date pair as descriptive payload. Its sibling `sat_contract_policyholder_effectivity` is a
*real* eff_sat. No gate caught the slip.

**Intended behaviour.** The validator gains a heuristic gate that flags a **standard** satellite,
hanging off a **link**, whose payload looks like a from/to date pair — likely it should be
`sat_type="effectivity"` with the link's driving key. **Warning**, not error (it is a heuristic and
may false-positive on a legitimate sat that happens to carry two dates).

**Files.** `src/vault_agent/rules/dv2_rules.py`, `src/vault_agent/agents/validator.py`,
`src/vault_agent/prompts/dv2_modeler.md`, `tests/test_agents/test_validator.py`.

**Implementation.**

- In `rules/dv2_rules.py`, add the single-source-of-truth hint tokens for a from/to date pair,
  e.g. `EFFECTIVITY_FROM_TOKENS = {"FROM", "START", "BEGIN", "VALID_FROM", "EFFECTIVE_FROM"}` and
  `EFFECTIVITY_TO_TOKENS = {"TO", "END", "VALID_TO", "EFFECTIVE_TO"}` (matched against
  `normalize_identifier(attr)` via substring/stem — keep it simple and documented).
- In `validator.py`, inside the per-satellite loop (where `link_names` is already in scope), add
  gate **`W_SAT_MAYBE_EFFECTIVITY`** that fires when **all** hold: `sat.sat_type == "standard"` **and**
  `sat.parent in link_names` **and** the attribute set contains exactly one "from" and one "to" token
  match (a from/to date pair). Message: *"standard satellite on link `<parent>` carries a from/to
  date pair (`<from>`, `<to>`); model it as an effectivity satellite (sat_type=effectivity) with the
  link's driving key?"*.
- Keep it a **warning** (`severity="warning"`), so it never blocks; it surfaces in the review queue
  as a `validation_warning`.
- `dv2_modeler.md` `[GUIDE]` line: *"When a relationship on a link has an active period (from/to
  dates), model it as an effectivity satellite (sat_type=effectivity) declaring the link's driving
  key — not a standard satellite carrying the dates as payload."*

**Acceptance criteria.**
- A standard sat on a link with `[EFFECTIVE_FROM, EFFECTIVE_TO]` → `W_SAT_MAYBE_EFFECTIVITY` fires.
- A real `effectivity` sat (sat_type=effectivity) → does **not** fire (its dates are start/end,
  handled by the existing eff_sat gates).
- A standard sat on a **hub** (not a link) with two dates → does **not** fire (heuristic scoped to
  links).
- A standard sat with ordinary payload (no from/to pair) → does **not** fire.
- Existing eff_sat gates (`E_EFFSAT_*`) unchanged.

---

## Finding #3 — Review-queue aggregation & prioritisation [ENFORCE]

**Observed.** The grounded messy run produced **51 review items, 39 of them identical-shape
`data_contract: field <X> has an undetermined type …` flags**, which buried the 7 substantive
validation warnings (redundant grain, BK-not-in-source). The checkpoint became unreadable.

**Intended behaviour.** Routine, repetitive **advisory** flags are **aggregated** into a single
summarised line per category; **blocking** items (validation errors, contract-owner assignments)
and **validation warnings** stay individual and first. No data is lost — the per-item detail still
lives in the artifacts (e.g. the contracts); only the *headline queue* is summarised.

**Files.** `src/vault_agent/agents/orchestrator.py` (`assemble_review_queue` /
`render_review_queue_md` / `ReviewItem`), `src/vault_agent/cli.py` (`_print_checkpoint`),
`tests/test_agents/test_orchestrator.py`, `tests/test_cli.py`.

**Implementation.**

- Classify each `review_flag` ReviewItem into a **group** (a stable category derived from the
  message), e.g. `undetermined-type`, `no-source-schema`, `other`. Either add a `group: str = "other"`
  field to `ReviewItem` and set it in `assemble_review_queue`, or compute the grouping at render
  time — prefer the explicit field so both renderers (md + CLI) share it.
- In **rendering only** (`render_review_queue_md` and `_print_checkpoint`): within the advisory
  `review_flag` section, group items by `group`; when a group has more than a small threshold
  (e.g. `> 3`) items, render **one aggregated line** — *"N× undetermined field type (e.g.
  VICTOR_PARTNER.PARTN_NR, …) — review before agreeing"* — instead of N lines; smaller groups render
  individually as today.
- `requires_signoff` logic is **unchanged** (still driven by validation errors + unassigned owners);
  aggregation is presentation-only.
- Keep the kind ordering blocking-first (errors → contract owners → validation warnings → review
  flags) — already the case; ensure the aggregated review-flag block stays **last**.

**Acceptance criteria.**
- A queue with ≥ 4 `undetermined-type` flags renders **one** aggregated line with the count + a
  short sample, not one line each; the `review-queue.md` and the CLI checkpoint agree.
- Validation warnings and contract-owner items remain individual and ordered before the aggregated
  advisory block.
- `requires_signoff` and the item counts in `write_outputs`' returned `review_items` are unchanged
  (count reflects underlying items, not the aggregated display — or document the chosen semantics).
- With few flags (≤ 3 per group), behaviour is unchanged (no spurious aggregation).

**Note (complementary, out of scope).** The deeper fix for the *cause* of the 39 flags is a typed
source schema (reality-test finding #4) so types come from the source rather than being undetermined;
this spec only de-noises the presentation.

---

## Rollout order

1. **#2**: rules tokens → validator gate → modeler `[GUIDE]` line → validator tests.
2. **#3**: `ReviewItem.group` + classification → aggregated rendering in both renderers → tests.
3. Run `ruff` / `mypy --strict` / `pytest`; re-run the messy grounded example and confirm the
   checkpoint now reads cleanly (the 39 type flags collapse to one line; the substantive warnings
   are visible and first).

## Traceability

| Finding | Section | New code |
|---|---|---|
| #2 eff_sat consistency | above | `W_SAT_MAYBE_EFFECTIVITY` gate + rules tokens + modeler guide |
| #3 review-queue noise | above | `ReviewItem.group` + aggregated rendering (md + CLI) |
