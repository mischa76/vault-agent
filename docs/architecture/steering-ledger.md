# Steering ledger — which prompt rules the harness still needs

Status: living document · Owner: maintainer · Introduced by WP16 (2026-07-22)

## Why this file exists

Parts of this harness exist because *the models of the day failed*. The CDK "key column, not
payload" line landed only after LLM steering failed 4/4 on `health_insurance` **even with the
validation error fed back**, and it needed a deterministic backstop
(`rules.attributes_without_cdk`) on top. WP9.1 added the FK-demotion backstop. The effectivity
two-dates line has a generator-side rejection behind it.

That is correct belt-and-braces engineering — but it is **model-compensation**, and until WP16
nothing could answer *"does the next model still need this?"*. Harnesses that only ever grow
are harnesses nobody re-reads (Karpathy, *LOOPS.md* rule VIII: delete the harness). This ledger
is where that question gets an evidenced answer, one row per rule.

**Scope boundary.** The **validator gates are the product**, not model-compensation: an
enterprise DV2.0 tool owes its users deterministic, auditable `E_`/`W_` gates regardless of how
good the model is. Nothing here proposes deleting a gate, and `eval.ablate` cannot ablate one.
The measurable, potentially deletable surface is exactly two things:

1. **prompt steering lines** — `rules.DV_MODELING_RULES` (`SteeringRule` registry), and
2. **pre-gate backstops** — deterministic repairs of LLM output *before* validation.

## The release protocol

Run this **on any model bump** (`config.heavy_model` / `primary_model` change, or a candidate
model probe). It is manual pre-release discipline, exactly like the eval gate — deliberately
not wired into CI.

1. Pick the matrix: **gated cases × rules that have a `backstop`** first — that is the cheap,
   high-signal subset (a backstop fire is an unambiguous "still needed"). Widen only if those
   come back clean.
2. Per cell, at least **3 repeats per arm**:
   ```bash
   uv run python -m eval.ablate --case health_insurance --drop cdk_not_payload --repeat 3
   uv run python -m eval.ablate --case bank --drop unit_of_work --model <candidate-model>
   ```
   Each invocation writes a comparison JSON under `eval/results/ablation/` (git-ignored) plus
   one LLM transcript per run (WP15) — read the transcript before believing a surprising
   result.
3. Verdict per row:
   - **any backstop fire in the dropped arm** → `keep`. The rule is still doing work.
   - **zero backstop fires AND no gated-score regression across N ≥ 3 repeats** →
     `candidate-delete`. A *human* then decides — read the `origin` column first: it records
     what the rule cost to learn.
   - anything in between (score noise, new validation error codes) → `keep`, and note why.
4. Deleting, when a human agrees:
   - deleting **prompt text** is cheap and trivially revertible — do it, record the date.
   - deleting a **backstop** requires the matching ablation evidence *and* keeping its
     `E_`-gate, which is what catches the failure if the deletion turns out to be wrong.
5. Update the row: model tested, date, the two arms' numbers, verdict.

## Ledger

Rule ids are `rules.dv2_rules.DV_MODELING_RULES[*].id` — the code is the source of truth; if
this table and the registry disagree, the registry wins.

| rule id | backstop | model last tested | ablation result (baseline → dropped) | verdict |
| --- | --- | --- | --- | --- |
| `cdk_not_payload` | `attributes_without_cdk` | sonnet-tier, 2026-07-16 (pre-instrument) | not yet ablated; known: steering **alone** failed 4/4 on `health_insurance` (E_SAT_DUP_ATTR, unrecoverable within MAX_MODELING_ATTEMPTS) — both halves were needed | keep |
| `effsat_two_dates` | `effsat_two_attributes` | — | not yet ablated | keep |
| `one_hub_per_key` | — | — | not yet ablated | keep |
| `hub_no_attributes` | — | — | not yet ablated | keep |
| `link_per_relationship` | — | — | not yet ablated | keep |
| `link_no_attributes` | — | — | not yet ablated | keep |
| `attributes_in_satellites` | — | — | not yet ablated | keep |
| `satellite_split_axes` | — | — | not yet ablated | keep |
| `no_object_link_confusion` | — | — | not yet ablated | keep |
| `unit_of_work` | — | — | not yet ablated | keep |
| `degenerate_attributes` | — | — | not yet ablated | keep |
| `effsat_driving_key` | — | — | not yet ablated | keep |
| `masat_source_table` | — | — | not yet ablated | keep |
| `bk_collision_code` | — | — | not yet ablated | keep |
| `role_qualified_participation` | — | — | not yet ablated | keep |
| `construct_naming` | — (gated by `E_BAD_NAME`) | — | not yet ablated; added WP20 (2026-07-28) so a deterministic naming formality never burns a modeling retry — the gate, not the steering, is the guarantee | keep |
| `attribute_one_satellite` | — (gated by `E_SAT_ATTR_OVERLAP`) | — | not yet ablated; added WP31/ADR-0012 (2026-07-30) after AdventureWorks `Sales` duplicated `ModifiedDate` across two satellites of ONE relation. Deliberately `backstop=None`: choosing *which* satellite keeps a duplicated column is a modelling decision, not a deterministic repair, so the gate refuses and the re-model loop fixes it. Its effectiveness is measurable directly — the WP31 §4.3 live `sales` run is the first datapoint, and the honest outcome if the loop still fails is a finding, not a weakened gate. **First datapoint (2026-07-30):** the `ModifiedDate` duplication did NOT recur and the run passed in one modeler attempt. Favourable, but **n=1 cannot separate a steering effect from sampling variance** — this is one datapoint, not a demonstrated effect. Ablate on `adventureworks_sales` before treating it as established. | keep |
| ~~`no_source_table_on_multi_source_hub`~~ **DELETED 2026-07-29** | — | measured ineffective: 0/3 live `bank_extension` runs prevented the shape | Lived less than a day. Added WP23 to steer the modeler away from `source_table` on a multi-source hub; the model kept emitting it because the shape is the correct answer to REQ-107, not a misreading. ADR-0011 then blessed the form (feed-naming binds the satellite to that feed), so the rule contradicted the product and was deleted by WP28. **The evidence is the point**: an ineffective rule whose target turned out to be legitimate — exactly the LOOPS rule-VIII case the ledger exists to catch, and the first entry retired on measurement rather than taste. | deleted (WP28) |

### Inventoried but not mechanically ablatable (v1)

The source mapper's steering lives in `src/vault_agent/prompts/source_mapper.md`, not in the
DV rules registry — it is mapping heuristics, not Data Vault canon, so it stays with its
prompt. It is listed here so the inventory is complete; ablating it means editing the prompt
file by hand and re-running `eval.run` on `messy_insurance`.

| prompt rule | backstop | evidence | verdict |
| --- | --- | --- | --- |
| FK-occurrence is not a second source — map to the entity-anchor table (source_mapper.md) | `fk_demotion` (`source_mapper._post_validate`) | WP9.1 (2026-07-13): without it, live `messy_insurance` mapping_accuracy sat at 0.870; with prompt + backstop, 0.972 mean over 5 repeats | keep — manual ablation only |
| Defer only across *different* source systems (source_mapper.md) | — (honest `unresolved`) | WP9.1; over-broad deferral was the failure it fixed | keep — manual ablation only |

| `preserved_reference_is_a_link` (modeler) | — (no deterministic repair exists) | WP30.1 (2026-08-09): arm B built **0 of 37** links spanning two domains; arm A built 16 of them from the same landscape. It invented `hub_sales_representative` where `hub_employee` stood in the vault inventory — the prompt already said *"never re-invent or rename a concept that already exists"*. The FK was in the schema, the requirement was explicit (§1.2 "Out of scope but referenced": *"these references must be preserved so the sales information can later be joined to those areas"*), and a resolver merge for `employee::EmployeeID -> hub_employee` was ratified at step 4. All four present, still zero links. | **unmeasured** — added 2026-08-09, not yet run |

## Reading the evidence

- **Backstop fires** per run land in each eval result JSON's `metrics.backstop_fires`
  (`{backstop_id: n}`) and in both arms of an ablation comparison. A backstop only fires when
  it *actually repairs something*, so `{}` across repeats is a real signal, not silence.
- **Transcripts** (WP15) sit next to the results as `*.trace.jsonl`. Before recording a
  verdict, grep the dropped arm's transcript for the modeler call and look at what the model
  actually emitted — a score delta without a mechanism is a hunch.
