---
type: memo
status: not-measured
updated: 2026-10-30
---

# The C1 experiment — requirements drafted from the catalogue against the analyst's documents, written before the run

**Date:** 2026-10-30 · **Status:** pre-registered, not run · **Commissioned by:** the owner, 2026-10-30 („mach das
experiment aus C1 mit abgeleiteten anforderungen") · **Author:** Claude · **Backlog:** C1 (the ADR candidate for a
source-driven mode), C27 stage 4.

## 1 The question, as C1 states it

*How a derived-requirements run on AdventureWorks compares with the owner-written chain (constructs, review load), and
what a deterministic derivation makes of AdventureWorks' associative tables (`BusinessEntityAddress`,
`ProductProductPhoto`).* The „owner-written chain" is the arm-B chain on the five documents a blinded analyst agent
wrote from the schema alone (WP30 §2.4a) — the same five files the owner's workbench build of 2026-10-22 used
(`demo/workbench-adventureworks`, byte-identical, checked today).

## 2 The two arms, one difference

- **Arm T (treatment):** `adventureworks_drafted_incremental` — the arm-B chain, every step the authored case with
  exactly one file exchanged: `requirements.md`, drafted deterministically from the catalogue by
  `eval/adventureworks/draft_requirements.py` (rules in its docstring: relationship / subtype / entity by how the
  foreign keys cover the primary key; the natural key where Microsoft declared an `AK_*` that is not the GUID, else
  the surrogate; columns in words, never by physical name; one requirement per described column, one per foreign
  key; no analyst's sentence anywhere). Schema and golden are byte-identical copies.
- **Arm A (control):** `adventureworks_incremental`, the twenty-second normal chain — run **today, on the same
  commit**, because the generator has changed since the last recorded chain (WP86–WP99) and a comparison across
  generators would measure two things at once (the WP30.2 lesson). It enters the review record as every normal
  chain does; arm T never does.

Both unattended (`accept: True` at every checkpoint, as the chain always runs), both with `--keep-outputs`, both on
the models of `config.py` today. Cost: two chains, about 9–10 USD together, 45–50 minutes in parallel.

## 3 Predictions, and what falsifies each

Counted from the step-5 model (`dv_model.yml`) and the step results; „more" means strictly more.

- **P1 Subtypes stay subtypes.** The drafted document says *every employee is a person, identified by the same
  business entity id* (the subtype rule). Prediction: arm T builds **no hub** for `Employee`, `Vendor`, `Store`,
  `SalesPerson`, `Person` — as arm A does not (the demo's finding). Falsified by any hub whose source entity is one
  of those five. `Password`, the sixth subtype by the rule, is reported, not predicted.
- **P2 Relationships become links.** Every table the rule classifies as a relationship — 12 across the five areas
  (counted by the instrument before the run: 2 in Person, 5 in Production, 1 in Purchasing, 4 in Sales; the
  two C1 names among them) — is modelled as a **link, not a hub**
  in arm T. Falsified by any relationship-classified table with a hub in arm T. For arm A the same count is
  reported, not predicted.
- **P3 Surrogate keys.** Arm T keys **more hubs on an `…id` column** than arm A (the drafted document names the
  primary key as the identifier wherever Microsoft declared no natural key; the analyst chose business keys).
  Counted as hubs whose `business_key`, normalised, ends in `ID`. Falsified if arm T's count ≤ arm A's.
- **P4 More constructs.** Arm T has **more hubs and more satellites** than arm A at step 5 (a document that lists
  every column and every table yields more to model). Falsified if either count is ≤ arm A's.
- **P5 Review load.** Arm T has **more review decisions** than arm A, summed over the five steps (more constructs,
  more mappings). Falsified if arm T's sum ≤ arm A's. Direction stated with the least confidence of the five: the
  analyst's documents carry „clarification needed" items that become gaps and flags, the drafted ones carry none.
- **P6 Gates.** Both arms end green (`validation_gate` 1.0 on every step, `existing_construct_preservation` 1.0,
  `project_self_contained` 1.0). Falsified by any red step; a red step in arm T only would be the finding C1 warns
  of (the gates assume constructs chosen from the business's words).
- **P7 Natural keys found.** `mapping_coverage` (did the mapper find Microsoft's natural-key columns?) is **not
  lower** in arm T than in arm A on any step — the drafted document names those keys as identifiers. Falsified by
  a step where arm T is lower.
- **Reported, not predicted:** cost and wall-clock per arm; cross-domain links per step; the mapper's category
  distribution; what each arm built for the five associative tables C1 names, construct by construct.

## 4 What the result can and cannot say

It can say what a deterministic draft does to the model and the review load, against the analyst's documents, on
one landscape, once (a shape, not a distribution — the chain's own rule). It cannot say whether a human-corrected
draft (C1 option 3) lands anywhere near the analyst's document: nobody corrects anything here. It does not decide
C1; it is the evidence C1 asked for before deciding.

## 5 Record

Results: `eval/results/<stamp>` for both arms, mirrored to `tank`; the comparison in `docs/log.md` with the counts
per prediction and the associative tables construct by construct. The instrument and the drafted cases are
committed before the run — this memo's commit is the pre-registration's date.

## 6 Results (2026-10-30, appended after the run — the predictions above are unedited)

Both arms ran on commit `9ce7a87`, in parallel, unattended. Arm A: stamp `20261030T184653194084Z`, 23.0 min, 109
calls. Arm T: stamp `20261030T184653223619Z`, 18.5 min, 104 calls. Computed by `eval/c1_compare.py`; the kept
outputs and both result files are mirrored to `tank`.

| | arm A (authored) | arm T (drafted) | prediction |
|---|---|---|---|
| step-5 hubs / links / satellites | 40 / 50 / 87 | 39 / 46 / 84 | **P4 falsified** — T has fewer of each |
| review decisions per step, sum | 16, 8, 27, 8, 32 = **91** | 21, 12, 49, 16, 48 = **146** | P5 held (+60 %) |
| review items, sum | 159 | 215 | — |
| gates, every step | all 1.0 | all 1.0 | P6 held |
| `mapping_coverage` per step | 1.0, 0.75, 1.0, 1.0, 1.0 | 1.0 on every step | P7 held |
| own hubs for the six subtypes | `hub_national_id` from `Employee` | none | P1 held for T; A's extra hub is a finding |
| relationship tables with an own hub / read by a link | 0 / 12 of 12 | 0 / 12 of 12 | P2 held |
| hubs keyed on an `…ID` column | **29 of 40** | **14 of 39** | **P3 falsified, inverted** |
| cross-domain links | 24 | 22 | reported |
| mapping categories | 292 exact_name, 4 comment_grounded | 292 exact_name, 4 llm_semantic | reported |
| link proposals by category | 12 same_name, 6 renamed, 8 relationship | 5 same_name, 6 renamed, **7 translated**, 8 relationship | reported |
| `BusinessEntityAddress` | one link, no satellite | one link, one satellite | reported |
| `ProductProductPhoto` | one link | one link | reported |

**The inversion of P3 is the result.** C1 warned that a draft from the catalogue would make surrogate keys
business keys. The opposite happened: the draft names Microsoft's own `AK_*` natural keys as identifiers
(`ProductNumber`, `CardNumber`, the `Name` of every reference table), and arm T keyed 21 hubs on them where arm A,
from the analyst's prose, keyed the same hubs on `ProductID`, `CreditCardID`, `DepartmentID`, … The catalogue's
declarations carried the natural keys; the analyst's documents lost them. The 7 translated proposals in arm T are
the consequence: with hubs keyed on natural keys, the declared foreign keys that reference surrogates need WP36's
translation — the drafted arm exercised that path seven times live, the authored arm never.

**P4 and P5 together say what a draft costs:** not more constructs — fewer, by one hub, four links and three
satellites — but more review: 55 more decisions, mostly the per-column requirements becoming mapping and
contract questions. Arm A built one hub arm T did not, `hub_national_id` on `Employee.NationalIDNumber`, with zero
satellites — WP34's invention symptom, within the baseline of 2, and the kind of construct a human would decline.

What this does not say: anything about a human-corrected draft (nobody corrected), or about a second landscape.
One chain per arm — a shape, not a distribution. The control arm is the twenty-second normal chain and **fails the
review clause of the record** (91 against a ceiling of 89.7); the cause split is in `docs/log.md` of this date.

## 7 The keyless builds (2026-10-30, appended after the run)

Both fifth projects were built on local PostgreSQL 16 against the AdventureWorks data copy, in fresh schemas, with
the generated projects unchanged. **Arm T does not parse:** five translation views project `NAME` twice (two hubs
keyed on `Name` in one link; backlog C33) — the drafted keys, by exercising 51 translated participations, found a
class the authored arm's three translation views never could. **Arm A does not parse either:** the carried
`sat_unit_measure_details` reads a stage renamed when its hub became multi-source (C34); with one documented hand
view of that name the project builds `PASS=389` of 396 in 27 s — the three errors are the two inferred stages the
run disclosed (`stage_refs_inferred` 2, the known class) and one feed stage hashing a payload column its relation
lacks (C35), the four skips their dependents. So: both arms green on every gate, neither buildable as written —
what the twentieth and twenty-first chains' builds found in their generation, this one found in the next.
