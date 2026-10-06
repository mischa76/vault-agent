---
type: spec
status: not-measured
updated: 2026-10-06
---

# WP52 — Three small corrections before the next run: honest chain metrics, the refused satellite's home, and a conflict that is a decision

Status: **Approved and in progress** (2026-10-06, user: „1 + 2 + 3 umsetzen", and on 3: „wenn es
keinen Fehler für das generierte Model erzeugt, aber eine Entscheidung benötigt um zu vermeiden
dass etwas verlorengeht dann ist es kein Fehler sondern eine Entscheidung") · Owner: Mischa
Eismann · Author: Claude. Touches `eval/run.py` (WP30 §2.7 scoring), the repair memory (WP46,
WP51), the merger (WP23). No prompt change; no model call.

## 1 Problems, measured

1. **The chain's `validation_gate` and `pipeline_health` read the final state only.** Only
   preservation is aggregated as the minimum over steps (`score_chain`, 2026-07-30). On the fifth
   chain step 4 scored `pipeline_health` 0.0 and the chain reported 1.0; a chain whose step 3 is
   red and step 5 green would report a green gate. The same „four times out of five" the
   preservation clause refuses.
2. **A satellite re-emitted in the shape the key gate refused is orphaned** although the remedy
   (WP46) already computed the parents whose key the relation carries. When there is exactly one,
   the payload has a known home — the WP51 pattern, not yet applied here.
3. **`extension_conflict` is an error-severity flag.** The merger refuses a delta that re-states
   an existing hub's key or an existing link, keeps the vault unchanged, and flags — with severity
   `error`, so `pipeline_health` scores the step 0.0 (three of five chains, step 4). Nothing is
   wrong with the generated model; what is needed is a human's answer to „did you mean a new
   satellite?" so nothing the modeler wanted is lost. By WP43's rule that is a decision, not a
   failure.

## 2 The rules

1. `score_chain` aggregates `validation_gate` and `pipeline_health` as the **minimum over all
   steps**, details naming every step and the worst, exactly as preservation is aggregated; the
   other scorers stay on the final state (they measure the vault that exists at the end).
2. `E_SAT_KEY_NOT_IN_SOURCE`'s remedy names its candidates; when exactly one exists the issue
   carries it as `retires_into`, the retirement as `kept_twin`, and `drop_retired` re-parents a
   satellite re-emitted in the refused shape to that parent (`retired_reparented`, a disclosure)
   instead of dropping it; with zero or several candidates the orphan decision stands.
3. The merger's two `extension_conflict` flags are advisory. Their kind is already a decision in
   the review queue (WP43); the merger still refuses the re-statement and keeps the vault
   unchanged. `pipeline_health` no longer fails a step on them.

## 3 Guards before the change

1. A three-step chain whose middle step fails validation and carries an error flag while the
   final step is clean scores `validation_gate` 0.0 and `pipeline_health` 0.0, naming the step.
2. On WP46's routing fixture, a retirement carrying `kept_twin = hub_work_order` re-parents the
   re-emitted satellite there with one `retired_reparented` flag and no orphan; without a twin
   the orphan decision stands; the validator records the single candidate as `kept_twin`.
3. A delta re-stating an existing link yields an `extension_conflict` flag of severity
   `advisory`, the vault unchanged, and `pipeline_health` 1.0.

## 4 Pre-registration

On the next chain: `pipeline_health` and `validation_gate` are the minimum over steps (a red step
anywhere is a red chain); no step scores 0.0 health on an `extension_conflict` alone; a refused
satellite re-emitted unchanged lands on its single candidate parent when the shape occurs. The
September and October result files are not re-scored; their chain-level health/gate values are
read with this entry in mind.

## 5 Not in this WP

Re-scoring archived results; the attempt budget; the mapper's re-bind on the failed path.

## 6 Results

*(appended after the change)*

**2026-10-06 — built, keyless.** Commits `063b96e` (guards, failing: four of five) and `ed3f4df`
(the change). `score_chain` aggregates `validation_gate` and `pipeline_health` as the minimum over
all steps, details „min over N step(s), worst <step>“; `E_SAT_KEY_NOT_IN_SOURCE` carries its
single candidate as `retires_into`, the retirement as `kept_twin`, and `drop_retired` re-parents
the re-emitted satellite there (`retired_reparented`) — on WP46's routing fixture
`sat_work_order_operation_detail` lands on `hub_work_order`; the merger's two `extension_conflict`
flags are advisory, the brownfield tests' two severity assertions updated in the same commit.
Guards 1–3 pass; 1138 tests, ruff, mypy. §4 is **not yet measured live**.

**2026-10-06 — sixth live chain** (`20261006T172859787765Z`, `docs/log.md` 2026-10-06): rule 1 live — chain
`validation_gate` and `pipeline_health` reported as „min over 5 step(s)“, all 1.0; rule 3 live —
step 5's `extension_conflict` on `link_customer_person` is advisory and the step scored health 1.0;
rule 2 half live — the validator recorded `kept_twin = hub_work_order` on step 3's refused
satellite, the modeler then followed the remedy, so the re-parenting had no case (untestable, not
failed). §4 met on everything that arose.
