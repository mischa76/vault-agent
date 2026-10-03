---
type: spec
status: not-measured
updated: 2026-10-03
---

# WP43 — Decisions and disclosures: the review queue counts answers, not signals

Status: **Approved and in progress** (2026-10-03, user: „sehr gut, mach es so" on the analysis
below; „triff Entscheidungen insofern selbst solange sie nicht gegen definierte Paradigmen
verstossen") · Owner: Mischa Eismann · Author: Claude. Touches ADR-0006 (the queue), WP5 §5.1
(one presentation source for three renderers), WP23 (the extension inventory), WP30 §2.7 and
WP34 §6 (the review-load clause). No prompt change, no new model call.

## 1 Problem, measured

The user's words (2026-10-03): „was mir noch negativ auffällt ist die hohe Zahl an Review-Fällen
… man könnte schnell zum Schluss kommen, dass man es dann gleich komplett selbst erledigen
könnte." The number in question is `review_items_total` = **532** on the last AdventureWorks
chain (`20260917T181755061438Z`, `docs/log.md` 2026-09-17).

The queue is a flat list: one item per validation issue and one per agent flag, summed over the
five checkpoints of the chain (WP30 §2.7, deliberately — a human reviews every increment). The
render-time aggregation of WP5 collapses repetitive *lines*; it never changes the *count*. So
the count measures how many signals the pipeline emitted, not how many questions it asked.

Composition of the 532, from the saved per-step metrics (`flag_kinds`, `validation_codes`):

| class | items | share | what it is |
|---|---|---|---|
| `source_binding` flags | 187 | 35 % | a stated assumption (the staging relation was inferred) |
| `W_EXISTING_EXTENDED` warnings | 159 | 30 % | the inventory of what the brownfield step added |
| `owner_placeholder` → `contract_owner` | 68 | 13 % | a required assignment, never guessed |
| `link_translation` + `sat_translation` | 42 | 8 % | one join through another relation each |
| other warnings and flags | 76 | 14 % | mixed |

Three classes make 78 %, and none of them is a modelling decision. `W_EXISTING_EXTENDED` was
*designed* to sit in the queue (charter Q5, WP23 §2.5: „the review queue's extension category")
— a reasonable choice when the queue was the only place a human looked. Since WP23 §2.7 the same
inventory is rendered as `extension-diff.md` and the report's Extension section, so the queue
restates, 159 times, what another artefact already lists as a table.

The `source_binding` count grows with the chain because each step receives only its own domain's
schema; stages of earlier domains are rebuilt without a declared relation, inferred, and flagged
again (1, 17, 25, 50, 94 across the five steps). That is the chain design and the subject of
§5, not of this WP.

## 2 The rule

**Every review item carries a typed role: it is a `decision` or a `disclosure`.**

- A **decision** is an item the human must answer before the model is agreed, and for which
  an answer exists in the decision vocabulary: assign (`--owner`), accept/discard (`--accept`,
  `--discard`), ratify (a mapping, a resolution, a license, a translation), or fix the model.
- A **disclosure** is provenance: the pipeline says what it assumed, inferred, dropped, or
  declined. Reading it is review; there is nothing to answer at the checkpoint.

The role is derived from typed fields only (invariant: never from message text):

| item kind | role | rule |
|---|---|---|
| `validation_error` | decision | severity `error` blocks agreement (ADR-0006) |
| `contract_owner` | decision | the placeholder owner must be assigned |
| `validation_warning` | disclosure | advisory by ADR-0006; no answer slot exists |
| `review_flag`, flag severity `error` | decision | typed severity wins over kind |
| `review_flag`, by `FlagKind` | see below | |

`FlagKind` → role (`REVIEW_FLAG_ROLES` in `orchestrator.py`, the code owns the table):

| decision | disclosure |
|---|---|
| `undetermined_type` (set the type) | `no_source_schema` (contract inferred from prose) |
| `mapping_unresolved` (ratify) | `source_binding` (relation inferred; §5 for the ambiguous subset) |
| `resolution_unresolved` (ratify) | `mapping_gap` (no in-scope source; belongs downstream) |
| `resolution_same_as` (ratify) | `link_proposal_skipped` (the proposer declined) |
| `link_translation` (ADR-0013 §3) | `dropped_record` (an invalid record was dropped, not guessed) |
| `sat_translation` (WP38) | `input_truncated`, `input_segmented` (size guard) |
| `extension_conflict` (merger refused) | `missing_input` (a stage ran without its upstream) |
| `generation_gap` (do it by hand) | |
| `column_collision` (rename) | |
| `link_relationship_incomplete` | |
| `generic` and any kind not in the table | |

A kind the table does not know is a **decision**. Hiding an unclassified item behind the
disclosure fold would be the one failure this WP must not introduce; the conservative default
costs a line, not a wrong model.

**The extension inventory is information, not a warning.** `ValidationIssue.severity` gains a
third value, `info`. The additive-extension check emits its inventory as
`I_EXISTING_EXTENDED` with severity `info` (renamed from `W_EXISTING_EXTENDED`: a code whose
prefix says *warning* for an item that is by its own doc „not a problem" is the kind of lie the
project's naming rule exists to prevent). Info issues stay in `validation_report.issues` — the
inventory is not lost, the scorers and `validation_codes` still see it — but the queue does not
derive items from them. Their home is the Extension section and `extension-diff.md` (WP23 §2.7),
which render the same delta as a table.

**Presentation.** All three renderers (markdown, console, HTML — WP5 §5.1, one source) show
decisions first, under the existing kind headings, every one individually; then one
`Disclosures` section, where the WP5 aggregation applies to *every* disclosure — advisory flags by
their group as today, validation warnings by their `code` — above `AGGREGATE_THRESHOLD`. The
status line says `N decision(s), M disclosure(s)`. `requires_signoff` is unchanged.

> **Amendment 2026-10-03, before the build.** „Every one individually" above is withdrawn for
> grouped decisions: the WP5 aggregation stays keyed by `REVIEW_FLAG_GROUPS` and applies to
> **both** roles, so 39 undetermined types still collapse to one line (finding #3 must not
> regress) while translations — not in a group, ADR-0013 §3 — stay individual. The roles
> partition and order; they do not change what collapses. Validation warnings, now
> disclosures, additionally collapse by `code`.

**Measurement.** `eval/run.py` adds `review_decisions` and `review_disclosures` beside
`review_items_total`, per step and summed over a chain exactly as the total is. The total keeps
its name and its sum-over-steps semantics; its *value* changes because info issues are no longer
items (§4 says by how much). `wp34_check` is not touched: its review clause is a pre-registered
record and reads `review_items_total` as before.

## 3 Guards before the change

Committed first, failing; then the change (`CLAUDE.md`, „Write the guard before the change"):

1. `ReviewItem.role` exists and `assemble_review_queue` assigns it per the table above, including
   the conservative default for an unknown kind and the severity-wins rule.
2. `HumanReviewQueue.decisions` / `.disclosures` partition `items`; `requires_signoff` unchanged.
3. An issue with severity `info` yields no review item; `validation_report.issues` still holds it.
4. The validator emits `I_EXISTING_EXTENDED` with severity `info` for a legitimate extension and
   `passed` stays true (the existing test, re-pointed at the new code and severity).
5. The markdown renderer puts every decision before every disclosure, keeps decisions individual,
   and collapses a group of more than `AGGREGATE_THRESHOLD` validation warnings of one code.
6. Parity: markdown, console and HTML list the same items in the same order (extends the existing
   parity tests). The pinned report fixture is updated deliberately in the change commit.
7. `run_metrics` carries `review_decisions` and `review_disclosures`; the additivity test's
   exhaustive key set grows by exactly those two.

## 4 Pre-registration — what the saved chain predicts

Computed by hand from the per-step `flag_kinds` and `validation_codes` of
`eval/results/adventureworks_incremental/20260917T181755061438Z-step*-run1.json`, applying §2's
table. No state was replayed (none is persisted); the next live chain is the measurement.

| step | items today | items under WP43 | decisions | disclosures |
|---|---|---|---|---|
| 1 person | 26 | 26 | 13 | 13 |
| 2 humanresources | 50 | 32 | 11 | 21 |
| 3 production | 136 | 77 | 40 | 37 |
| 4 purchasing | 97 | 79 | 16 | 63 |
| 5 sales | 223 | 159 | 40 | 119 |
| **chain** | **532** | **373** | **120** | **253** |

Decisions, by class: 68 owners, 33 link translations, 9 satellite translations, 5 unresolved
resolutions, 1 unresolved mapping, 4 validation errors (`E_HUB_HK_COLLISION` 1,
`E_SAT_KEY_NOT_IN_SOURCE` 3). Disclosures: 187 source bindings, 9 skipped proposals, 4 segmented
inputs, 4 mapping gaps, 2 dropped records, and 47 validation warnings (210 issues − 4 errors −
159 inventory).

**P1.** On the next live chain, `review_decisions` is within ±15 % of 120 if the modeler builds a
vault of the same shape (45 hubs, 62 links, 84 satellites at the end). The number that moves with
the model is translations (42 here); the number that moves with the chain design is bindings.
**P2.** `review_items_total` falls below 619 (the WP34 clause) by construction — 373 on this chain
— and that fall says **nothing** about the model. The clause's baseline was measured with the
inventory counted; it is not like-for-like any more and should be re-based on `review_decisions`
with a fresh baseline from the first post-WP43 chain. That re-basing changes a pre-registered
clause and is the owner's decision, recorded here as the recommendation, not made.
**P3.** `review_queue_lines` falls below 409 on a chain of this shape; the 159 inventory lines
vanish and the 47 warnings collapse to about 7 group lines. Not predicted to a number — it also
depends on the per-step mix.
**P4.** Nothing else moves: `validation_gate`, `pipeline_health`, `construct_f1`,
`existing_construct_preservation` are computed from the report and the model, not from the queue.
`max_validation_warnings` tolerances are only ever *easier* to meet (info is not a warning).

## 5 Not in this WP, and what it costs

- **Bindings are re-disclosed every step.** 187 of the 253 disclosures. Two routes, both a
  design decision for the owner: (a) an acknowledgement ledger beside the model — a disclosure
  with the same `identity()` that was presented at an earlier checkpoint is not presented again;
  the same persistence question as the WP29 resolutions (`memory`: `metadata/resolutions.yml`,
  undecided since 2026-07-31); (b) give each chain step the cumulative catalogue, which is what a
  real brownfield run has anyway — but it changes what WP30 §2.7 measures. Either one needs a
  typed `reason` on the `source_binding` flag (`none` / `ambiguous` / `shared`, the vocabulary
  `rules.resolve_link_relation` already returns), after which the `ambiguous` subset becomes a
  decision. Estimated effect on this chain: disclosures 253 → under 100.
- **Owners as a registry.** 68 decisions are one question per contract. A declared mapping
  source system → owner in the schema input (ADR-0004's `SourceTable` has no owner field today)
  is not invention; it would make this one question per domain with bulk apply. Small, keyless,
  a spec of its own.
- **Review by exception.** Where the pipeline has a preferred answer (a license on a
  `declared_fk_same_name`, a binding with exactly one offering relation), propose it and let the
  human object. That is WP29's ratification pattern applied to more kinds; it needs the WP29
  persistence first.

## 6 Results

*(appended after the change and after the next live chain)*

**2026-10-03 — built, keyless.** Commits `25de63c` (guards, failing) and `402f422` (change).
`ReviewItem.role`, `REVIEW_FLAG_ROLES` (every declared `FlagKind` classified, guarded),
`HumanReviewQueue.decisions`/`.disclosures`, `review_queue_layout` + `status_line` as the one
layout for markdown, console and HTML, `IssueSeverity` with `info`, `I_EXISTING_EXTENDED`,
`review_decisions`/`review_disclosures` in `eval/run.py`. Guards 1–7 of §3 pass; ruff, mypy,
pytest 1072 passed. Fixtures updated deliberately: `report_fixture.html`,
`greenfield_manifest.json` (`report.html`, `review-queue.md`). §4 is **not yet measured**: no
state of the 2026-09-17 chain is persisted, so the predicted 373 / 120 / 253 await the next live
chain. One deviation from `.claude/rules/records.md`, named rather than hidden: the amendment
in §2 was inserted into the section it corrects by a script (which the `Edit`/`Write` hook does
not see) instead of being appended here; it is dated and additive, and it is not repeated.

