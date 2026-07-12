# Spike results — business↔source mapping (Phase 2, ADR-0008)

Status: **Complete** (D1–D6 delivered) · Timebox: honoured · Author: mapping spike ·
Charter: [`spike-mapping-charter.md`](./spike-mapping-charter.md) · ADR:
[ADR-0008](../adrs/ADR-0008-source-to-target-mapping.md) · Spec output:
[`wp9-mapping-spec.md`](./wp9-mapping-spec.md)

The decision memo the charter (§7) asked for: what the measured A/B comparison found, each
answer with the evidence line behind it, and — plainly — where the evidence is thin.

## TL;DR

**LLM-first mapping (variant B) is the mechanism.** On the hard `messy_insurance` case it
reached **mapping_accuracy 0.984** and **gap recall 1.000** at **fewer input tokens than the
deterministic-first hybrid** (variant A: 0.650 accuracy, and *more* tokens). B resisted every
trap the deterministic layer fell for. There is **no accuracy↔cost trade-off to agonise over**
— B is both better and cheaper here. The honest-failure clause ("neither beats trivial
name-matching") did **not** trigger: variant A *is* essentially name+comment matching with an
LLM backstop, and it scored 0.65 where B scored 0.98.

## D4 measurements (5 repeats/config, `messy_insurance`, Sonnet-tier, one forced-tool call/run)

| config | mapping_accuracy | gap_detection | confidence_calibration | tok in (mean) | tok out (mean) | latency (mean) |
|---|---|---|---|---|---|---|
| **variant A** (deterministic-first) | **0.650** | 1.000 | **0.000** | 13 841 | 3 007 | 47.8 s |
| **variant B** (LLM-first) | **0.984** [0.98–1.00] | 1.000 | **0.958** [0.94–0.97] | 6 080 | 3 899 | 55.0 s |
| variant B — no profiling (degraded (d)) | 0.980 | 1.000 | 0.957 | 4 278 | 3 725 | 50.4 s |
| variant B — columns-only (degraded (c)) | 1.000 | 1.000 | 0.960 | 5 105 | 4 195 | 60.2 s |

Raw per-run JSON: `spike/results/` (git-ignored; deleted with `spike/`). Scores are the
permanent D2 scorers (`eval/scorers.py`), which survive the spike.

### Trap autopsy (across the 5 runs of each config)

| trap (§4) | variant A | variant B |
|---|---|---|
| **statistics** (`partner number` → PARTN_NR, *not* the flawless-profiling PARTN_GUID) | **wrong 5/5** (see below) | **correct 5/5** |
| **synonym** (`customer reference`: PARTN_NR vs ExternalCustomerNo) | unresolved 5/5 | unresolved 4/5, ExternalCustomerNo 1/5 |
| **false-friend** (`KD_NR` branch code, `AccountId` surrogate) | **0 hits** | **0 hits** |
| **genuine gaps** (4 derived/out-of-scope concepts) | **caught 4/4, 5/5 runs** | **caught 4/4, 5/5 runs** |

- **Variant A's statistics-trap failure is not the GUID** — it is worse and more instructive.
  Its deterministic layer maps `partner number` to `CLAIMSPRO_PAYMENT.PayeePartnerNo`, whose
  comment literally reads *"…refers to a partner number."* A comment-literal matcher
  over-commits to a foreign-key reference, accepts it with high confidence, and never routes
  it to the LLM. That single confident error is why A's **calibration is 0.000** (its most
  confident proposal is wrong). Precision stays high (0.93) only because A is otherwise
  conservative — recall 0.50, it leaves half the concepts unresolved.
- **Both mechanisms nailed the gaps and dodged the false-friends.** The four no-source
  concepts (Schadenquote, Cross-Selling-Quote, Provision, Maklercode) were caught every run;
  neither ever mapped a concept onto `KD_NR` or `AccountId`. Gap-surfacing (ADR-0008 #3) is
  the *easiest* behaviour to get right here, not the hardest.

## Answers to the charter's §7 questions

**Q1 — Which mechanism, which accuracy, which cost; is the delta worth the spend?**
Variant B, **0.984 vs 0.650**, at **6 080 vs 13 841 input tokens** — B wins accuracy *and*
cost. The deterministic-first hybrid is dominated: its per-concept shortlist payload (5
candidates × ~16 hard concepts, each with type/comment/profiling) is bulkier than B's
send-the-schema-once, and its deterministic accepts over-commit on comment-literal matches.
*The "deterministic-first is cheaper" hypothesis is falsified on this case.* → **Adopt B.**

**Q2 — Is confidence calibrated enough for the ADR's degraded-mode semantics?**
For B, yes: calibration margin **0.958** (correct proposals ~0.9+, wrong ones near 0 — clean
separation). But A's margin of **0.000** is the cautionary tale: a self-reported number can
*invert* for a mechanism whose confident path is heuristic. **Recommendation:** carry a
deterministic **category** alongside the number — `exact_name > comment_grounded >
profiled_key > llm_semantic > unresolved`, derived from the evidence the proposer returns —
and let the review queue gate on category, with confidence as a secondary sort. Do not make a
raw LLM confidence the sole carrier of the degraded-mode contract.

**Q3 — Does `ProposedMapping` hold up as the WP9 state model?**
Yes. `proposals[(concept, entity, table, column, confidence, evidence[])]` + first-class
`gaps` + `unresolved` served *both* mechanisms, all three scorers, and the post-validation
step without strain. WP9 adds one field: `ratification_status`
(`proposed|accepted|overridden`). Promote it into `state.py` verbatim.

**Q4 — Per-item CLI ratification, or a ratification file?**
The messy case yields ~22 proposals + a handful of gaps/unresolved — *workable* per-item
(`--map "concept=TABLE.COLUMN"`), but tedious, and a real DWH concept list runs to hundreds.
**Recommendation:** a **ratification file** (`mappings.review.yml`, edit-and-resume via the
ADR-0006 mechanism) as the primary path, with `--map` kept as a small-override shortcut. The
review queue already aggregates advisory items (WP5), so gaps/unresolved fold in cleanly.

**Q5 — Is the pre-step profiling file sufficient?**
Yes — and, unexpectedly, profiling was **not load-bearing for intent**: dropping it entirely
(no-profiling probe) moved accuracy 0.984 → **0.980**, inside run-to-run noise. Column
*comments and names* carry intent; profiling's real job is BK-plausibility and
post-validation evidence, not disambiguation. **Nothing observed justifies** building the
pipeline-invoked read-only profiling variant ADR-0008 left open — ship the file producer only,
revisit only if a real engagement asks.

**Q6 — Rename layer: map source→business in staging, or carry source names through?**
The question splits by column role, and one half is not a free choice:

- **Hub business key (the hash driver): harmonisation to one canonical name+format is
  *mechanically required*, not stylistic.** A hub integrates the same business entity across
  sources only if `X_HK = hash(business key)` is computed identically in every feeding staging
  model. Two sources with different physical key columns (`Q_A.partner.partner_id`,
  `Q_B.customer.customer_id`) must both alias/standardise to a common representation before
  hashing, or the same customer hashes twice → two hub rows → no integration. This is Data
  Vault's *definition* of a hub (Linstedt: the hub is the integration point on the business
  key), a hard staging rule on names/format — **not** a soft business rule (values stay raw,
  `record_source` preserved). Consequence: for a **multi-source** hub key, "carry source names
  through" is *impossible* — at least one source is always renamed. The real sub-decision is
  only *which* canonical name (a business term, or one source's name chosen as canonical).
- **Satellite descriptive attributes: source names can and should stay.** There is no hash
  constraint, so DV2.0's canonical answer is **one satellite per source** on the same hub
  (`sat_customer_qa`, `sat_customer_qb`, split by `record_source`), each carrying its own
  source column names; value harmonisation happens downstream in the Business Vault.

**Recommendation:** harmonise the **hub key** to a canonical business name in staging (forced
anyway); keep **satellite attribute** names source-faithful (one sat per source). This is a
sharper answer than "business names in the vault" — the rename layer is only genuinely *open*
for descriptive attributes, and there it should preserve source names. Still a **MAINTAINER
(Mischa) decision** for the canonical-key-name policy; detailed in WP9 §6. NB: the two-source
hub above is **not representable in the current model/generator** — see thin-evidence #5 and
WP9 §3.3.

## Where the evidence is thin (read before trusting the numbers)

1. **The columns-only probe did NOT demonstrate honest degradation** — accuracy stayed at
   **1.000**. This is a *negative result for the probe, not a strength to celebrate*: the
   `messy_insurance` physical names, though cryptic, are **recognisable DACH-insurance
   abbreviations** (`VTG_NR`→Vertragsnummer, `PARTN_NR`→Partnernummer, `SPARTE`, `PRAEMIE`)
   that the LLM resolves from its own domain priors *without* comments or types. So the probe
   stressed precondition (c) far too weakly. **Precondition-(c) degradation is unproven.** A
   follow-up must mask opacity (rename physical columns to `COL_0001…`, keep only the golden
   mapping) to measure whether B degrades honestly or hallucinates confidently. Until then,
   the ADR-0008 "output quality is capped by input quality" claim is *plausible but
   unmeasured* for the LLM mechanism. (It *is* visibly true for the deterministic layer, which
   collapses to near-zero signal under columns-only — verified keylessly.)
2. **Single dataset.** All numbers are `messy_insurance` only. The charter's optional `bank`
   easy case was traded away to spend the timebox on the hard case. B's band should be
   re-measured on `bank`/`health_insurance` before WP9 sets a `min_scores` gate.
3. **Model/temperature.** One Sonnet tier, default sampling, prompt-caching on. Numbers may
   shift with model upgrades; the D2 scorers exist precisely to re-measure.
4. **The synonym concept is the one B "misses"** for recall — but leaving a genuinely
   ambiguous concept *unresolved* is arguably the correct assist behaviour (surface it for the
   human), so the 0.984 (vs 1.000) is a scorer artefact, not a real error. WP9 could treat
   `ambiguous`-class concepts as "unresolved-is-acceptable" in the gate.
5. **The multi-source hub is out of scope of the spike — and of the current model.** The spike
   maps one concept to one-or-more source columns, but a hub *fed by two sources* (the same
   business key in `Q_A.partner.partner_id` and `Q_B.customer.customer_id`) is **not
   representable today**: `state.Hub` has no multi-source field and `_render_hub` emits a
   single `source_model` + single `src_nk`. This is the canonical DV2.0 business-key
   harmonisation case and it is a *generator/model gap*, not a mapping-mechanism gap — but WP9
   must close it for the mapping's multi-candidate output (Q6) to have anywhere to land. See
   WP9 §3.3.

## ADR-0008 status recommendation

**Accept ADR-0008 as-is (move Proposed → Accepted).** Every guardrail held under measurement:
assist-level proposals with an evidence trail (✓), gaps as first-class output (✓ 4/4 every
run), no live profiling needed (✓ file sufficed, and profiling proved non-critical), and the
preconditions framing is sound — with **one caveat to record in the ADR's Consequences**: the
"input quality caps output quality" claim is confirmed for the *deterministic* path but
*unproven for the LLM path* on a recognisable schema (thin-evidence item 1). No decision in the
ADR needs to change; the caveat is a measurement gap for WP9 to close, not a flaw in the
premises. Recommend Mischa accept the ADR and greenlight WP9 with the opacity follow-up as an
explicit WP9 acceptance criterion.

## Deliverable inventory

| # | Deliverable | Location | Survives spike? |
|---|---|---|---|
| D1 | Golden mapping + profiling + enriched schema | `eval/datasets/messy_insurance/{golden_mapping,profiling,source_schema_enriched}.yml` | **yes** |
| D2 | Mapping scorers + result types + tests | `eval/mapping.py`, `eval/scorers.py`, `tests/test_mapping_scorers.py` | **yes** |
| D3 | A/B prototypes | `spike/` | no (git-ignored) |
| D4 | Measured runs | `spike/results/*.json` + tables above | no (data → this memo) |
| D5 | This memo | `spike-mapping-results.md` | **yes** |
| D6 | WP9 draft + ADR recommendation | `wp9-mapping-spec.md` + this §ADR-0008 | **yes** |

## Decision record (2026-07-13, Mischa)

All seven decisions taken, all per recommendation: **(1)** rename layer — hub key
harmonised (business term only when sources disagree; source name kept for single-source
hubs), satellite attributes source-faithful; **(2)** ratification file primary + `--map`
shortcut; **(3)** category-based confidence gate; **(4)** graph placement (a)
generate-with-proposed / regenerate-on-override; **(5)** ADR-0008 **Accepted** with the
thin-evidence caveat recorded in its Consequences; **(6)** WP9 greenlit with the
opacity-masked degradation probe as acceptance criterion §10.7; **(7)** multi-source hub
**split into WP10** (WP9 parks multi-candidate keys in `unresolved`). Specs finalised:
`wp9-mapping-spec.md` (decisions inlined), `wp10-multi-source-hub-spec.md` (new),
kick-offs `WP9-mapping.md` / `WP10-multi-source-hub.md`.

## Decisions awaiting the maintainer (Mischa) — original list, superseded by the record above

1. **Rename layer (Q6)** — confirm: harmonise the **hub key** to a canonical business name in
   staging (forced by hashing); keep **satellite attributes** source-faithful, one sat per
   source (recommended). Sub-decision: canonical-key-name policy (business term vs. a chosen
   source name).
2. **Ratification UX (Q4)** — confirm file-primary + `--map` shortcut (recommended).
3. **Confidence carrier (Q2)** — confirm category-based gate over raw LLM confidence (recommended).
4. **Graph placement (WP9 §4)** — generate-with-proposed then regenerate-on-override (recommended (a)).
5. **ADR-0008** — accept as-is with the thin-evidence caveat recorded (recommended).
6. **Greenlight WP9** with the opacity-masked degradation follow-up as an acceptance criterion.
7. **Multi-source hub (WP9 §3.3)** — confirm WP9 adds a multi-source hub (one hub, several
   feeding staging models unioned) so the mapping's multi-candidate key output can land
   (recommended; it is the canonical DV2.0 harmonisation case and a prerequisite for Q6's key
   half).
