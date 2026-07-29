# WP26 — ADR completeness and determinism

Status: Proposed · Size: S · Depends on: — · **Land before WP23's delta-ADR** (both edit
`adr_author._render`; the extension case is easier to express on a complete renderer) ·
Source: project review 2026-07-29, finding 4

## 1. Problem

The generated ADR is the pipeline's human-facing architecture record — the artifact a
reviewer, an auditor, or a prospect actually reads. It omits most of what the last six work
packages taught the model to express:

- **`Link.driving_key` is not rendered at all.** CLAUDE.md states the opposite ("State
  carries Link.driving_key … for the ADR trail, which the adr_author surfaces when
  present"); `grep driving_key src/vault_agent/agents/adr_author.py` returns nothing. The
  driving key is the one decision that determines how an effectivity satellite end-dates —
  the least obvious and most consequential thing in the model.
- **`Hub.sources` is not rendered.** A hub integrating VICTOR_PARTNER + CRM_ACCOUNT reads
  exactly like a single-source hub, so WP10's integration decision — the canonical DV2.0
  decision — is invisible in the record. The reader cannot see that two systems were merged
  onto one key, nor which physical columns feed it.
- **`Satellite.sat_type` / `child_dependent_key` are not rendered.** A multi-active or
  effectivity satellite is indistinguishable from a standard one.
- **The ratified business↔source mappings (WP9) do not appear.** They exist only in
  `mappings.review.yml`, so the ADR cannot answer "where does this attribute come from?".
- **Determinism claim vs. behaviour.** The module docstring promises "Same state in,
  byte-identical ADR out" while `date.today()` (`adr_author.py:63`) makes that false across
  midnight.

## 2. Target design [ENFORCE]

Deterministic rendering only — the ADR author stays LLM-free (that is what makes the
architecture record non-hallucinated), so every addition below is a projection of typed
state.

### 2.1 Constructs render what they are

- Hub line: when `hub.sources` is non-empty, append the feeds —
  `integrated from N source(s): crm_customer.cust_id, victor_partner.partn_id` — and name
  the canonical staging key column via `rules.canonical_hub_key_column(hub)` (one source of
  truth; do not re-derive the name).
- Link line: when `driving_key` is non-empty, append
  `Driving key: hub_account (counterparty)` — rendered through
  `Link.resolve_driving_refs()` so the role qualification reads the same as the
  participation list, and unresolvable entries simply do not appear (the validator's
  `E_DRIVING_KEY_NOT_IN_LINK` owns that complaint).
- Satellite line: name the type for anything other than `standard`
  (`multi-active satellite, child dependent key: address_type`; `effectivity satellite`),
  and the `source_table` when declared (WP7).

### 2.2 A mappings section (conditional)

When `state.mappings` carries proposals, add a **Source mappings** section: one line per
proposal (`concept → TABLE.COLUMN`, its category and ratification status), then the gaps
("no in-scope source — Business Vault / marts") and the unresolved concepts. Omit the whole
section when the mapper was inert (ungrounded runs), so an ungrounded ADR stays
byte-identical to today — pin that.

### 2.3 Determinism made true

Keep `today` injectable; make the default explicit about what it costs. Either state the
claim precisely ("byte-identical for a given state **and** date") or take the date from the
state/run rather than the clock. Decide one and make docstring, CLAUDE.md, and the WP2
determinism test agree — the current mismatch is exactly the kind of small false claim this
project otherwise does not tolerate.

### 2.4 What must not change

Per-output numbering (always ADR-0001, WP2), status `Proposed`, the existing section order
and wording of the untouched lines, the `GENERATION_GAP` caveat logic (matched on
kind/asset, never message text), and the sole-writer property (`state.adrs = [adr]`).

## 3. Tests

1. Driving key, multi-source feeds, satellite type + CDK, and `source_table` each render;
   a model without them renders byte-identically to today (fixture-pinned).
2. Ungrounded run (no mappings) → no Source mappings section, ADR byte-identical.
3. Grounded run with proposals + gaps + unresolved → all three appear, with categories.
4. Role-qualified driving key renders like the participation list.
5. Determinism: same state + same injected date → byte-identical (existing test extended).

## 4. Acceptance criteria

1. Every typed field the model carries that changes how the vault behaves is visible in the
   ADR, or deliberately listed here as omitted.
2. The CLAUDE.md driving-key claim becomes true (or is corrected in the same commit).
3. Ungrounded/simple models produce a byte-identical ADR (regression fixture).
4. Standard DoD.

## 5. Out of scope

Any LLM involvement in the ADR, repo-level ADR numbering (WP2 stands), the delta/"Extends"
framing for brownfield runs (WP23 §2.8 owns it — this WP only makes the base renderer
complete enough for it), and rendering the data contracts (they are their own artifact).
