# WP30 — An independent semantic axis, and the domain-partitioning experiment

Status: **Approved** (2026-07-29, Mischa — with two amendments from the review: §2.4a
blinded requirements authoring, §2.7 the arm-B chaining machinery made explicit) ·
Owner: Mischa Eismann · Date: 2026-07-29
Depends on: WP23 (brownfield mode, Accepted and proven), WP13/WP14 (scale cases and the
column-based scorers). Eval-only — **no `src/vault_agent/` change is in scope.**

## 1. Problem

Two defects in our measuring instrument, both recorded and neither fixed.

**(a) The synthetic generator does not scale semantics.** `scale-test-findings.md` Candidate #5
measured it: at 100 and at 300 tables the requirements document contains **exactly 87 distinct
sentence templates**; of 296 distinct entities at 300 tables, 200 are index variants of an
existing archetype (`extra_aufgabe_3 … _8`). Table *count* scales linearly, business *semantics*
do not scale at all beyond a fixed vocabulary. Above the 30-table step, `scale_100`/`scale_300`
measure tolerance for repetitive boilerplate. **The pipeline is verified at ~30 tables of real
semantic variety and unverified above it.**

**(b) Every realistic case is author-written.** `bank`, `health_insurance` and
`messy_insurance` — schema, requirements and golden — come from the same author as the prompts
and the rules. The entity-resolution spike memo §4 already names this confound and its blinded
probe only partially mitigates it. We have never once measured this pipeline against a schema
somebody else designed.

Both defects converge on the question this project's architecture already answers by assertion
rather than measurement: ADR-0010 Option C and the incremental-extension charter state that
"nobody models 300 tables in one pass; they model domain by domain into a growing vault."
**That claim has never been tested.** It cannot be tested with the current instrument, because
the synthetic landscape has no real domains and no real semantic growth.

## 2. Target design [ENFORCE]

### 2.1 The instrument: AdventureWorks

Source: `microsoft/sql-server-samples`, OLTP install script. **MIT licensed** — verified in the
repository's `license.txt`, which grants use, copy, modify, merge, publish, distribute. This is
the reason it is chosen over TPC: TPC-DI matches our scenario (18 source tables across trading,
HR, CRM and external feeds) but its EULA forbids derivative works absent express permission and
permits publishing measurements **only as an audited TPC Benchmark Result**, with Fair Use rules
declaring comparisons from derived workloads invalid. The one thing we wanted it for — an
independent, citable number — is the thing its rules forbid. ACORD is member-gated; BIAN is a
service taxonomy, not a physical data model; OMOP CDM is permissively licensed but is a
standardised *target* model, not an operational source.

**MIT attribution is a deliverable, not an afterthought:** derived assets carry the Microsoft
copyright notice and licence text, in a `NOTICE` file beside them.

### 2.2 The partitioning is GIVEN, never drawn by us

AdventureWorks ships five OLTP schemas — `Person`, `HumanResources`, `Production`,
`Purchasing`, `Sales` — which are subject areas designed by someone else. **Redrawing these
boundaries, merging them, or excluding a schema to make a case tidier is forbidden**: the entire
value of this WP is that the domain partitioning is not ours. If a boundary turns out to be
awkward, that is a finding to record, not a thing to fix.

### 2.3 Types AND comments — taken verbatim, never authored (corrected 2026-07-29)

**This section originally asserted the opposite and was wrong.** It claimed the install script
carries no `MS_Description` extended properties. It carries **440 column descriptions** and 69
table descriptions across the five business schemas. The error survived two verifications that
both failed in the same direction: a WebFetch summary of a truncated markdown conversion, and a
grep for the named-parameter form `@level2type=N'COLUMN'` when the script uses positional
arguments. Recorded rather than quietly fixed, because "verified" appeared in the original text.

The correction makes the instrument stronger, not weaker: AdventureWorks supplies the full
ADR-0008 precondition (c) — clean names, types **and** documentation — **none of it ours**. The
prohibition therefore stays, and it prohibits what it always meant to: **authorship**. Comments
are transcribed VERBATIM from `sp_addextendedproperty`; a column Microsoft left undescribed
stays undescribed (25 of 465 do). Nothing is written, extended or paraphrased by us.

The case's position in the input-quality space, restated:

| case | names | comments | what it tests |
|---|---|---|---|
| `messy_insurance` | cryptic DACH abbreviations | rich, ours | mapper reasoning under bad names, good docs |
| WP9 §10.7 opacity probe | masked | stripped | honest degradation with no signal |
| **AdventureWorks** | **clean, English** | **rich, INDEPENDENT** | **semantic breadth, zero author bias in either channel** |

Two trap classes come for free and must be preserved rather than tidied away: Microsoft's own
`AK_*` unique indexes declare the natural keys (which is why the golden mappings are defensible
rather than our modelling opinion), and beside them sit `AK_*_rowguid` indexes — a perfectly
unique technical GUID next to the true business key, i.e. the GUID-shadow trap `messy_insurance`
had to synthesise, occurring here organically.

State plainly in the case files what this does **not** exercise: the cryptic-legacy-naming trap
classes. It complements `messy_insurance`; it does not replace it.

### 2.4 Cases

One case per subject area plus the two experiment arms:

- `adventureworks_<schema>` — greenfield, one subject area, five of them.
- `adventureworks_full` — arm A: all five schemas declared, one pass.
- `adventureworks_incremental` — arm B: the same five, sequentially, each run consuming the
  previous run's `metadata/dv_model.yml` via `existing:` (the WP23 input the CLI's `--existing`
  provides).

Requirements documents are authored **from the schema**, one per subject area. This is the
weakest link and must be handled honestly: write them from the tables and relationships as they
are, and **do not write a golden DV model first and then requirements that lead to it.** The
confound is reduced, not eliminated — say so in the case files.

Arm B's order is derived from the FK graph (a schema referencing another comes later), computed
and **recorded in the spec's results section before the first run**, so the order is not chosen
after seeing an outcome.

### 2.4a Blinded authoring (review amendment 2026-07-29)

The requirements documents are authored in a SEPARATE session/agent that is given ONLY the
DDL-derived schema of one subject area — no access to the pipeline's prompts, steering rules,
scorers, or the other cases. This is the cheap blinding measure the entity-resolution spike's
blinded probe established: it does not remove the author confound (§1b names why nothing fully
can), but it removes the specific channel where it matters most — requirements phrased in the
vocabulary the prompts reward. Record in each case file HOW its requirements were authored
(session, inputs given), so the mitigation is checkable rather than claimed.

### 2.5 What is gated, and what is only reported

The scorers that key on free-form LLM names (`construct_f1`, and hubs/satellites generally) stay
**ungated** — `eval/README.md` already records that name-keying is safe only for hand-written
cases, and a hand-authored golden here would re-import our own modelling opinion. Ship
`golden: {}` and let the WP18 loader do its job: it will refuse to gate a scorer the golden
declares nothing for.

Gated, because each is structural and defensible from the DDL:

| scorer | gate | why it is defensible |
|---|---|---|
| `mapping_coverage` | ≥ 0.8 | pair-based (WP14), and the true `TABLE.COLUMN` for every business key is readable straight out of the DDL |
| `false_friend_hits` | 1.0 | declared from real same-named-different-meaning columns, not invented |
| `pipeline_health` | 1.0 | no error flags |
| `existing_construct_preservation` | 1.0 | arm B only — this is the promise brownfield mode makes |

`validation_gate` is **reported, not gated**, on first introduction: an independent schema may
legitimately trip gates we have never exercised, and pre-committing to a pass would pressure the
next person to weaken a gate rather than record a finding.

### 2.6 The experiment, with the prediction written down first

Run both arms, ≥ 3 repeats, and compare:

- review items and rendered review lines (the human-workload measure that actually binds),
- unresolved / gap rate from the mapper,
- validation outcome and issue codes,
- construct counts,
- wall clock and token cost.

**Hypothesis under test (the charter's claim):** arm B produces a materially lower per-step
review load and a comparable or better model than arm A, at comparable or lower total cost.

**It must be falsifiable, and the falsifying outcome must be written down before running:** if
arm A yields comparable review load and validation at lower total cost, the charter's
"domain by domain" claim is weakened and that is the finding — record it, do not re-run until it
comes out the preferred way, and do not quietly retire the arm that lost.

Note the one asymmetry to keep honest: arm B pays LLM cost five times over the *growing*
inventory (each extension prompt carries the existing model), so a total-cost tie is a win for
arm B on the review axis and a loss on the token axis. Report both; do not collapse them into
one number.

### 2.7 Arm-B chaining machinery (review amendment 2026-07-29 — the real implementation effort)

The spec's `existing:` so far means a STATIC case input (`bank_extension` ships a checked-in
`existing_vault.yml`). Arm B needs something new in the runner: a CHAINED case, where step N+1
consumes step N's `metadata/dv_model.yml` **output**. Make it explicit rather than implied:

- `EvalCase` (or a new `ChainSpec`) declares the ordered step list; `eval.run` executes steps
  sequentially in one repeat, threading each step's output directory into the next step's
  `existing` input. One repeat = one full chain; repeats re-run the whole chain.
- **Mid-chain HITL semantics, stated up front:** every step auto-resumes with the standard
  `AUTO_RESUME_DECISION` (accept, no owners) — the same unattended behaviour every eval run has.
  This means arm B measures the pipeline WITHOUT human ratification quality; say so in the
  writeup, because it biases arm B's review-load numbers upward (unratified mappings carry
  forward), which is conservative for the hypothesis, not flattering.
- A step failing fails the chain's repeat at that step (WP14.1 semantics: completed steps'
  results are already persisted); `existing_construct_preservation` is scored PER STEP against
  that step's input model, not only at the end.
- Keyless tests for the chaining: output→input threading, attributable error on a missing
  predecessor output, per-step scoring shape.

## 3. Tests (keyless)

1. `load_eval_case` accepts each new case; the loader's existing refusals (gating a scorer with
   no golden evidence) are exercised by at least one case, not just asserted.
2. The five subject-area cases and the two arms appear in the shipped-case list pin.
3. Arm B's `existing:` chain resolves — each step's declared existing model is the previous
   step's output path shape, and a missing one is an attributable error.
4. Schema-derivation is deterministic: re-deriving `source_schema.yml` from the checked-in DDL
   extract produces byte-identical output (the WP13 determinism property).
5. The `NOTICE` file exists and is non-empty beside the derived assets.

## 4. Acceptance criteria

1. **The instrument is independent**: no boundary, entity or relationship in the derived schema
   was invented by us; every table traces to the AdventureWorks DDL. Spot-checkable.
2. Five subject-area cases run green on their gated scorers, or their failures are recorded as
   findings with the trace quoted (WP15 §2.4 protocol).
3. **Both arms run ≥ 3 repeats and the comparison is written up**, including the prediction as
   stated in §2.6 and whether it held.
4. Arm B holds `existing_construct_preservation` = 1.0 at every step. Anything less is a defect
   in brownfield mode, not a quality signal — stop and file it.
5. The cross-schema overlap (`Person` referenced from both `Sales` and `HumanResources`) is
   **identified and documented** as the natural entity-resolution case. It is *not* measured
   here — WP29's resolver is unbuilt, and coupling this WP to it would block both.

## 5. Out of scope

- Any `src/vault_agent/` change. If the experiment exposes a product defect, it becomes its own
  WP; this one only finds it.
- Authoring column comments (§2.3) — deliberate.
- A hand-authored golden DV model (§2.5) — deliberate.
- Loading AdventureWorks *data* or building it on PostgreSQL. This WP measures modelling from
  schema + requirements; a warehouse build is a separate question already answered by the demos.
- WP29 entity resolution (§4.5).
- Retiring or relabelling `scale_100`/`scale_300`. Candidate #5 proposes it; it is a separate
  decision and doing it here would bundle an admission with an unrelated deliverable.

## 6. Budget

Estimate from measured data: `scale_100` cost ~$6.35 for 137 calls at 100 tables. AdventureWorks
is ~70 tables, so arm A ≈ $4–5 per repeat; arm B is five smaller runs over a growing inventory,
plausibly similar or somewhat higher per repeat. **Three repeats of both arms plus the five
subject-area cases is on the order of $40–60.** Set a ceiling before starting and stop at it —
the WP13 §4 abort discipline applies. The per-case runs are the cheap and informative part; run
them first.

## 7. Results

### 7.1 Arm B step order — RECORDED 2026-07-29, before any live run

Derived from the extract's 90 foreign keys, not chosen: a subject area follows every area it
references. Cross-area FK references (`eval.adventureworks.derive --help` reprints this):

| subject area | references |
|---|---|
| `Person` | *(none — the root)* |
| `HumanResources` | Person |
| `Production` | HumanResources |
| `Purchasing` | HumanResources, Person, Production |
| `Sales` | HumanResources, Person, Production |

Topological order, resolving ties by name so the result is reproducible:

**`Person` → `HumanResources` → `Production` → `Purchasing` → `Sales`**

Note `Person` is the root *and* the area both `Sales` and `HumanResources` reference — the
cross-domain overlap §4.5 flags as the natural WP29 entity-resolution case (a person who is
both a customer and an employee). Recorded, not measured here.

### 7.2 The instrument as derived

| subject area | tables | columns | with a verbatim comment | natural keys (golden) | false friends |
|---|---|---|---|---|---|
| HumanResources | 6 | 40 | 40 | 4 | 1 |
| Person | 13 | 70 | 69 | 4 | 7 |
| Production | 25 | 169 | 147 | 9 | 6 |
| Purchasing | 5 | 49 | 47 | 2 | 1 |
| Sales | 19 | 137 | 137 | 5 | 11 |
| **total** | **68** | **465** | **440** | **24** | **26** |

The golden holds **only Microsoft's own single-column `AK_*` natural keys** — never a column we
judged to be one. So `mapping_coverage` on these cases answers one sharp question, *did the
mapper find the real natural-key columns?*, and deliberately nothing else. False friends are the
`rowguid` columns: perfectly unique, indexed as unique keys, never a business key.

### 7.3 Run results

#### Smoke run — `adventureworks_purchasing`, 1 repeat, 2026-07-29

The first live run of this pipeline against a schema it did not author. Purchasing was chosen
because it is the smallest area (5 tables, 49 columns), i.e. the cheapest way to learn whether
the instrument runs at all before committing the budget.

**All three gated scorers passed, first attempt:** `mapping_coverage` 1.000 (2/2 golden
natural-key pairs bound), `false_friend_hits` 1.000 (the `rowguid` column was watched and not
bound), `pipeline_health` 1.000 (no error flags). Model: 6 hubs, 5 links, 8 satellites.

`validation_gate` — reported, not gated (§2.5) — **also passed**, with 3 warnings inside
tolerance. §2.5 pre-committed to the possibility that an independent schema would trip gates we
have never exercised; on this area it did not. One area is not five, and the larger ones
(Production at 25 tables, Sales at 19) are where that prediction is actually at risk.

Cost and load, as the baseline the arm comparison needs: 11 calls (3 Opus, 8 Sonnet), 46,832 in
(35% cache-read), 29,371 out, 307 s wall clock, **15 review items / 23 rendered lines**. At list
prices that is ≈ $1.60. The `mapping_coverage` detail also records `34 proposal(s) outside the
golden column set, unscored` — expected WP9.2/WP14 semantics, not a defect: the golden is
deliberately only Microsoft's own natural keys (§7.2), so everything the mapper proposes for
descriptive attributes is out of universe by construction.

#### The five subject areas — 1 repeat each, 2026-07-29/30 (acceptance #2)

One repeat per area (the §7.3 budget finding below is why not three). Total **$11.97**, 100 calls,
2,376 s wall clock.

| case | tables | `mapping_coverage` | `false_friend_hits` | `pipeline_health` | `validation_gate` (reported) | constructs (h/l/s) | review items / lines | calls | cost |
|---|---|---|---|---|---|---|---|---|---|
| `purchasing` | 5 | **1.000** (2/2) | 1.0 | 1.0 | PASS (3 warn) | 6 / 5 / 8 | 15 / 23 | 11 | $1.62 |
| `humanresources` | 6 | 0.750 (3/4) | 1.0 | 1.0 | PASS (3 warn) | 4 / 3 / 8 | 12 / 25 | 11 | $1.14 |
| `person` | 13 | 0.000 (0/4) | 1.0 | 1.0 | PASS (3 warn) | 9 / 7 / 16 | 24 / 31 | 20 | $1.92 |
| `sales` | 19 | 0.000 (0/5) | 1.0 | 1.0 | **FAIL** | 15 / 19 / 17 | 128 / 50 | 26 | $3.59 |
| `production` | 25 | 0.000 (0/9) | 1.0 | 1.0 | **FAIL** | 15 / 14 / 24 | 101 / 52 | 32 | $3.69 |

`false_friend_hits` and `pipeline_health` hold at 1.0 everywhere: **no run ever bound a `rowguid`**
— the GUID-shadow trap, occurring organically here, was resisted on all five areas — and no run
raised an error flag. `mapping_coverage` fails its 0.8 gate on three areas and `validation_gate`
(reported, not gated — §2.5) fails on the two largest. §2.5's prediction that an independent
schema would trip gates we have never exercised **held**, and the instrument earned its keep on
day one: three distinct findings, two of them product defects, one of them the class that
produces wrong *data*.

**Finding 1 — a wrong-data defect in the source mapper (WP24 class). Own WP.** Reproduced
keylessly, so it needs no further live runs:

```
hubs sharing the business-key label "Name": hub_phone_number_type (PhoneNumberType),
                                           hub_address_type      (AddressType),
                                           hub_contact_type      (ContactType)
SourceMapperAgent._concepts  -> [('Name', 'PhoneNumberType')]        # ONE concept asked
source_overrides             -> {'PHONE_NUMBER_TYPE': 'PhoneNumberType',
                                 'ADDRESS_TYPE':      'PhoneNumberType',   # <-- wrong table
                                 'CONTACT_TYPE':      'PhoneNumberType'}   # <-- wrong table
```

`_concepts` de-duplicates the work-list on `normalize_identifier(concept)` **alone, ignoring the
entity**, so hubs whose business keys share a generic label are asked about once; two of the three
hubs above are never asked at all. `source_overrides` then looks the answer up **by label alone**,
so the single proposal's table is applied to *every* hub carrying that label — `stg_address_type`
is bound to `PhoneNumberType` and hashes `ADDRESS_TYPE_HK` from the wrong relation's rows. It is
silent: no flag, no warning, and the SOURCE_BINDING flag that would have said "inferred" is
*cleared* by the re-bind. This is the WP24 defect class (wrong data, not a wrong message), and the
shape is not exotic — reference tables keyed on `Name`/`Code`/`Description` are ubiquitous, and
`Person` alone supplies three. The entity is available at both sites (`_Concept.entity`,
`Hub.source_entity`); the fix is to key concept identity on (label, entity) rather than label.
Whether the mapper's *tool schema* — one decision per concept, keyed under
`additionalProperties` — can express two same-labelled concepts is the part that makes this a WP
and not a one-liner.

**Finding 2 — `E_SAT_ATTR_OVERLAP` fails on an organic schema shape. Needs a decision, not a
patch.** Both validation failures trace to the same cause. Replaying the stored traces through the
validator at zero API cost (the 2026-07-28 method) gives, on `production`:

```
E_SAT_DUP_ATTR      sat_product_cost_history / sat_product_list_price_history
E_SAT_ATTR_OVERLAP  hub_product  x4
  sat_product_cost_history        (source_table=ProductCostHistory)       StartDate, EndDate, StandardCost
  sat_product_list_price_history  (source_table=ProductListPriceHistory)  StartDate, EndDate, ListPrice
  sat_product_current_price_cost  (from Product)                          StandardCost, ListPrice
```

The modeler produced three modeler responses (the full `MAX_MODELING_ATTEMPTS` budget) and never
converged, on both `production` and `sales` — the signature of a gate asking for something the
schema cannot give. AdventureWorks carries per-entity history tables (`ProductCostHistory`,
`ProductListPriceHistory`), and WP7's `source_table` is exactly the feature that makes modelling
them correctly possible: two satellites on one parent, each from a *different* relation. Their
`StartDate`/`EndDate` columns are then different attributes that merely share a generic name, and
nothing collides — the satellites are separate tables, so the gate's stated rationale ("what would
collide on the parent is the generated column") does not apply across satellites the way it does
within one. State the counter-argument fairly rather than assuming the gate is simply wrong:
`StandardCost` in both `sat_product_current_price_cost` and `sat_product_cost_history` **is**
duplicated payload in the DV2.0 sense, so part of what fired here is a real modelling smell. The
two cases need separating, which is a modelling decision (an ADR, like ADR-0011 narrowing the
WP24 gate) and not a quick fix. Note the asymmetry the current shape creates: a false-positive
*error* burns the whole re-model budget and ends the run, whereas the same signal as a warning
would have surfaced for a human.

**Finding 3 — the gate conflates mapper quality with modeler key choice (instrument calibration,
NOT to be fixed by weakening it).** `mapping_coverage` was built (WP14) to be concept-decoupled,
and it is — it matches `(source_table, source_column)` pairs. But the *universe it can bind from*
is still the modeler's concept list, so the score is bounded by the modeler's business-key
choices. Person's four misses split into two different stories:

| golden pair | what happened | reading |
|---|---|---|
| `ADDRESSTYPE.NAME`, `CONTACTTYPE.NAME` | hub modelled correctly, never asked about | Finding 1 — a real defect |
| `COUNTRYREGION.NAME` | modeler chose `CountryRegionCode` — the table's PK and a defensible business key | legitimate disagreement with Microsoft's `AK_*` |
| `STATEPROVINCE.NAME` | modeler chose `StateProvinceID` — a **surrogate** | a real modelling weakness, against our own `[GUIDE]` rules |

So a 0.000 here does **not** mean "the mapper failed", and the number must not be quoted as if it
did. The honest statement of what these cases measure is narrower than §2.5 claimed: *did the
pipeline, having chosen its own business keys, bind the real natural-key columns?* — with three
distinguishable failure modes folded into one number. §2.5 pre-committed to not weakening a gate
under pressure from a bad result, and that stands: **the 0.8 gate stays**, and the split above is
the finding. Separating the three modes properly (e.g. reporting coverage against the golden pairs
the modeler's key choice *made reachable*, alongside a business-key-choice score) is its own eval
WP; inventing it in reaction to this run is how the WP9.2/WP14 mistakes happened.

Cross-cutting observation for the arm comparison, recorded now because it is the axis §2.6 is
about: review load grows steeply and super-linearly in area size — 12/15 items for the 5-6 table
areas, 101 and **128** for Production and Sales. Rendered lines grow far more slowly (23 → 52), so
WP5's aggregation is doing real work at this size.

#### Re-measured after WP31 / ADR-0012 — `production` and `sales`, 1 repeat each, 2026-07-30

Finding 2 was fixed (WP31, ADR-0012 Accepted) and the two failing areas re-run. Both now pass
validation, in **one modeler attempt** instead of exhausting all three:

| case | `validation_gate` | `mapping_coverage` | review items / lines | modeler attempts | calls | out tok | wall | cost |
|---|---|---|---|---|---|---|---|---|
| `production` | 0.000 → **1.000** | 0.000 → 0.222 | 101 → **45** / 52 → 48 | 3 → **1** | 32 → 31 | 75.8k → 65.6k | 668 → 589 s | $3.69 → $3.02 |
| `sales` | 0.000 → **1.000** | 0.000 → 0.600 | 128 → **50** / 50 → 44 | 3 → **1** | 26 → 25 | 71.3k → 62.4k | 640 → 580 s | $3.59 → $3.05 |

The three `hub_product` overlaps are now `W_SAT_ATTR_OVERLAP_CROSS_SOURCE`, each naming its
satellites' relations, and `Sales` produced the same shape on `SalesQuota`
(`sat_sales_quota_history` vs its current-value satellite) — the *legitimate* case, correctly
reported rather than blocking. Both runs raise zero `E_SAT_ATTR_OVERLAP`.

**A correction to Finding 3 as written above, and it matters.** `production` and `sales` scored
`mapping_coverage` 0.000 on 2026-07-29 because **the mapper produced zero proposals** — WP25
deliberately routes a model that fails validation to the checkpoint *without* running the source
mapper, since mapping the concepts of a model that may be discarded spends LLM calls on output
that may never be used. So those two zeros were a downstream consequence of Finding 2, not a
measurement of mapping quality at all, and reading them as one would have been wrong. Finding 3's
analysis stands as written **for `person`**, which did validate and did produce 27 proposals; the
table there is Person's. With the models now valid, the two areas score 0.222 and 0.600.

**Finding 1 is now quantified, which turns it into a prediction.** Every remaining coverage miss
on both areas is a `<TABLE>.NAME` pair — `CULTURE.NAME`, `LOCATION.NAME`, `PRODUCT.NAME`,
`PRODUCTMODEL.NAME`, `PRODUCTSUBCATEGORY.NAME` … (7 of production's 9, 2 of sales' 5) — and each
run made **exactly one** proposal for a concept labelled `Name`:

```
production: 74 distinct concepts, 1 concept "Name" -> ProductCategory.Name
sales:      61 distinct concepts, 1 concept "Name" -> Store.Name
```

That is Finding 1's concept collision, at scale: reference tables keyed on `Name` are the norm in
this schema, the modeler correctly hubs each one, and the mapper asks about the label once. So the
prediction to test when Finding 1 is fixed — written down now so it cannot be adjusted afterwards
— is that `production` rises from 0.222 toward ~0.78 (7 of 9 recoverable) and `sales` from 0.600
to ~1.000, without any change to the mapper's reasoning quality. If it does not, the residual is
modeler key choice and belongs to Finding 3.

**Budget finding, recorded because it changes the plan rather than the result.** Extrapolating
from this run by column count (465 total vs Purchasing's 49) and requirements size (263 KB total
vs 17 KB), the full §4 acceptance list at 3 repeats — five areas plus both arms — lands at
roughly $80-110, i.e. **above the §6 ceiling of $40-60**. The ceiling holds and the plan gives
way: the choice is fewer repeats on the subject-area cases (they are diagnostic, and their gates
are structural rather than sampling-sensitive) or fewer repeats on the arms (which is where
repeats actually matter, since §2.6 compares distributions). Recommended split: **1 repeat per
subject area (~$12-15) plus 3 repeats of each arm (~$35-50)**, and stop at the ceiling per the
WP13 §4 abort discipline.
