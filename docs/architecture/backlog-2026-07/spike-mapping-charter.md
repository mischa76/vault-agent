# Spike charter — business↔source mapping (Phase 2, ADR-0008)

Status: Proposed · Type: timeboxed design spike (NOT a work package) ·
Timebox: 2–3 agent-days · Output feeds: WP9 spec + ADR-0008 status decision

## 1. Goal

Answer, with **measured evidence**, the design questions that block a Phase-2 mapping
spec — within the guardrails ADR-0008 already fixes (assist-level, pre-scoped candidate
set, gaps as first-class output, no runtime live-profiling, preconditions (a)–(e) with
explicit degraded mode). The spike produces throwaway prototypes and a decision memo,
**never** production code.

## 2. Non-goals

- No changes to `src/vault_agent/` (prototype code lives under `spike/`, git-ignored or
  deleted at the end; only docs and eval assets survive).
- No staging/generator integration (that is WP9, after the spec).
- No DDL parsing or live DB introspection (ADR-0008 #4; profiling arrives as a file).
- No new trust model — ratification stays the ADR-0006 checkpoint mechanism.

## 3. Deliverables

| # | Deliverable | Form |
|---|-------------|------|
| D1 | Golden mapping dataset for `messy_insurance` (+ optional `bank` as easy case) | `eval/datasets/<case>/golden_mapping.yml` |
| D2 | Deterministic `mapping_accuracy` + `gap_detection` scorers, keyless-tested | `eval/scorers.py` additions (these DO survive the spike — they are eval assets, not prototype) |
| D3 | Two candidate-mechanism prototypes (variant A/B, §6) | `spike/` throwaway code |
| D4 | Measured A/B comparison: accuracy, gap recall, confidence calibration, token cost, latency; ≥ 5 repeats per variant | results JSON + table in the memo |
| D5 | Decision memo answering §7's open questions | `docs/architecture/backlog-2026-07/spike-mapping-results.md` |
| D6 | Draft WP9 spec in the backlog format + ADR-0008 status recommendation (Accept as-is / amend) | `wp9-mapping-spec.md` (draft) |

## 4. Golden mapping — dataset design (D1)

Extend the existing `messy_insurance` eval case (VICTOR legacy schema is already
deliberately cryptic). Format, loaded by a typed loader in the same style as
`dataset.yml`:

```yaml
# eval/datasets/messy_insurance/golden_mapping.yml
mappings:
  - concept: "partner number"        # business label, as the requirements/model use it
    entity: partner                  # business entity the concept belongs to
    source_table: VICTOR_PARTNER
    source_column: PARTN_NR
    kind: business_key               # business_key | attribute
  - concept: "Vertragsnummer"
    entity: vertrag
    source_table: TVERTRAG
    source_column: VSNR
    kind: business_key
  # ... attributes ...
gaps:                                # concepts with NO legitimate source (born downstream)
  - concept: "Schadenquote je Partner"
    reason: derived KPI, no OLTP origin (belongs to Business Vault / marts per ADR-0007)
ambiguous:                           # legitimate multi-candidate cases — either answer scores
  - concept: "customer reference"
    candidates: [{table: VICTOR_PARTNER, column: PARTN_NR},
                 {table: CRM_CUSTOMER, column: EXTERNAL_CUSTOMER_NO}]
```

The golden set MUST contain, by construction (extend the source schema/requirements
minimally if a trap is missing — keep everything anonymized per the repo's
public-readiness convention):

1. **Synonym trap:** two plausible columns for one concept (PARTN_NR vs.
   EXTERNAL_CUSTOMER_NO) — golden via `ambiguous`.
2. **False-friend trap:** a column whose name matches the concept lexically but is
   semantically wrong (e.g. `KDNR` that is a legacy branch code, documented as such in a
   column comment) — mapping it is an ERROR the scorer penalises.
3. **Statistics trap:** a column that profiles like a perfect key (unique, non-null —
   e.g. a technical GUID) but is NOT the business key (ADR-0008: "statistics establish
   structure, not intent").
4. **Genuine gap:** ≥ 2 concepts with no source (derived/enriched) — must land in `gaps`,
   not be force-fit.
5. **Trivial matches** as the baseline floor (exact-name and near-name pairs).

Profiling evidence arrives as a **pre-step artifact** (ADR-0008 #4), one file per case:
`eval/datasets/<case>/profiling.yml` — per column: `uniqueness_ratio`, `null_ratio`,
`distinct_count`, `example_values` (sanitised). Hand-authored for the spike, plausible
values; the traps above must be reflected in it (the GUID profiles clean, the real BK has
a realistic minor wart, e.g. 0.2 % nulls from a legacy migration).

## 5. Scorers (D2)

- `mapping_accuracy`: precision/recall/F1 over proposed (concept → table.column) pairs vs.
  golden `mappings`; `ambiguous` entries score correct for any listed candidate; matching
  through `normalize_identifier` on all parts. Score = F1.
- `gap_detection`: recall over golden `gaps` (proposed-as-gap / golden gaps), with
  force-fit penalty listed in details (a golden gap that got mapped anywhere = the worst
  failure mode, called out by name).
- `confidence_calibration` (details-only, no gate): mean confidence of wrong proposals vs.
  mean confidence of correct ones — the ADR's degraded-mode story only works if
  low-confidence actually correlates with error.

All three: pure functions over a typed `ProposedMapping` result object, pinned-score unit
tests, keyless.

## 6. Experiment protocol (D3/D4)

Both variants receive identical inputs: golden model constructs (as concept list),
declared source schema (tables/columns/types + comments where present), profiling.yml.
Both emit the same typed result: proposals with `(concept, table, column, confidence,
evidence: list[str])` + explicit `gaps` + `unresolved`.

- **Variant A — deterministic-first:** heuristics propose (normalised-name similarity /
  token overlap, type compatibility, BK-plausibility from profiling); only unresolved or
  low-margin concepts go to ONE forced-tool-call LLM pass (via `ForcedToolCaller`) with
  the shortlist as context. Hypothesis: cheap, calibrated, but weak on semantics.
- **Variant B — LLM-first:** one forced-tool-call pass proposes everything (schema +
  profiling + comments in the prompt), deterministic post-validation (proposed column
  must exist, type-compatible; violations → unresolved). Hypothesis: strong on synonyms,
  cost + calibration risk.

Protocol: ≥ 5 repeats per variant per case (variance!), record all three scores + input/
output tokens + wall time per run; results as JSON like `eval/results/`. Then two probes:
- **Degraded-mode probe:** re-run the winner without profiling.yml (precondition (d)
  missing) and with a columns-only schema (weak (c)); verify accuracy drop is visible AND
  the prototype degrades honestly (more `unresolved`/lower confidence, not silent guessing).
- **Trap autopsy:** per trap category (§4), which variant fails how — this feeds the
  [GUIDE]/prompt design in WP9.

## 7. Questions the memo (D5) must answer

1. Which mechanism (A/B/hybrid) reaches which `mapping_accuracy` at which cost — and is
   the delta worth the LLM spend?
2. Is confidence calibrated enough to carry the ADR's low-confidence/degraded-mode
   semantics? If not, what replaces it (e.g. category-based: exact-match > profiled-BK >
   LLM-semantic)?
3. Mapping artifact: does the spike's `ProposedMapping` shape hold up as the WP9 state
   model (incl. ratification status + evidence trail for the ADR author)?
4. Ratification UX: given real proposal counts, is per-item CLI ratification
   (`--map "concept=TABLE.COLUMN"`) workable, or does WP9 need a ratification *file*
   (edit + resume) for 100+ attributes?
5. Profiling interface: is the pre-step file sufficient (spike default), or does anything
   observed justify the pipeline-invoked read-only variant ADR-0008 left open?
6. Rename layer: given the proposals' shape, should WP9 map source→business names in
   staging (derived-column rename, business names in the vault) or carry source names
   through? (Recommendation with reasoning; the decision itself may need Mischa.)

## 8. Exit criteria

Spike ends when D1–D6 exist, or the timebox expires — whatever comes first. If the
timebox expires early, the memo documents what was measured and what remains open; no
extension without an explicit decision. Definition of honest failure: "neither variant
beats trivial name-matching meaningfully" is a VALID spike outcome — it would re-scope
WP9 to deterministic matching + human completion, and the memo must say so plainly.

## 9. Constraints

- Repo conventions bind (CLAUDE.md); scorers/datasets follow WP6 patterns exactly.
- All LLM calls through `ForcedToolCaller`; heavy model NOT required (this is Sonnet-tier
  work — measure before reaching for Opus).
- Public-readiness: all dataset content stays anonymized (ATLAS convention).
- The 250+-test suite, ruff, mypy stay green (spike code outside src/ and mypy scope,
  EXCEPT the D2 scorers, which are first-class eval code).
