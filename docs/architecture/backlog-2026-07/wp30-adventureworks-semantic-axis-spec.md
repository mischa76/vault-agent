# WP30 — An independent semantic axis, and the domain-partitioning experiment

Status: **Proposed** · Owner: Mischa Eismann · Date: 2026-07-29
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

### 2.3 Deliberately: types but NO column comments

The install script carries no `MS_Description` extended properties (verified) — AdventureWorks
gives clean English names and types, no documentation. **Do not author comments to fill the
gap.** Inventing the comment channel would put author bias exactly where the mapper is most
sensitive, which is the confound this WP exists to remove.

This makes AdventureWorks a genuinely new point in the input-quality space, complementary to
what we have rather than a replacement:

| case | names | comments | what it tests |
|---|---|---|---|
| `messy_insurance` | cryptic DACH abbreviations | rich | mapper reasoning under bad names, good docs |
| WP9 §10.7 opacity probe | masked | stripped | honest degradation with no signal |
| **AdventureWorks** | **clean, English** | **none** | **semantic breadth with no documentation** |

State the consequence plainly in the case file: for the mapper this is an *easy naming* case and
a *hard documentation* case, and it does **not** exercise the cryptic-legacy-naming trap classes.
It complements `messy_insurance`; it does not replace it.

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

_To be filled by the executing run. Record arm B's FK-derived order here BEFORE the first run._
