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
