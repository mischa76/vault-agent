# WP9 — Business↔source mapping (Phase 2, ADR-0008)

Status: **Accepted for implementation** (2026-07-13; spike decisions applied — see the
decision record in [`spike-mapping-results.md`](./spike-mapping-results.md)) · Size: L ·
Depends on: ADR-0008 (Accepted), ADR-0004/WP7 (landed), ADR-0006 HITL (landed) ·
Blocks: WP10 (multi-source hub)

Maintainer decisions taken 2026-07-13 (all per spike recommendation): LLM-first mechanism ·
ratification **file** primary + `--map` shortcut · **category-based** confidence gate ·
graph placement **(a)** generate-with-proposed, regenerate on override · canonical key name
= **business term when sources disagree, source name when a single source feeds the hub** ·
**multi-source hub split out into WP10** (this WP delivers single-source binding;
multi-candidate keys land in `unresolved`).

## 1. Problem

Phase 1 (ADR-0004) only *warns* when a proposed business key/attribute matches no source
column. The two-input target needs the **mapping** itself: per business concept, *which
physical source column feeds it* — or that the concept is a **coverage gap** (ADR-0008 #3).
The spike measured the mechanism; this WP productionises it.

## 2. What the spike settled (evidence: memo D4)

- **Mechanism: LLM-first** (variant B): one forced-tool pass over enriched schema +
  profiling + comments; deterministic post-validation demotes non-existent /
  type-incompatible picks to `unresolved`. 0.984 accuracy, 1.000 gap recall, cheaper in
  input tokens than the deterministic-first hybrid (0.650), trap-resistant.
- **Profiling is not load-bearing for intent** — it serves BK-plausibility and
  post-validation evidence. Pre-step file only; no pipeline-invoked profiling (ADR-0008 #4,
  resolved).
- **Degradation under weak documentation is UNPROVEN for the LLM path** — the
  opacity-masked probe (§10.7) is a mandatory acceptance criterion.

## 3. Inputs (extend, do not replace)

### 3.1 Enriched source schema
- New `SourceColumn(BaseModel)`: `name: str`, `type: str = ""`, `comment: str | None = None`.
- `SourceTable.columns: list[str | SourceColumn]`, normalised by a `before` validator
  (WP8 `LinkHubRef` union pattern) with a `.column_names` property for existing consumers
  (grounding, staging) — bare-string YAML stays valid and byte-for-byte inert.
- `source_schema.load_source_schemas` accepts both YAML shapes. Reference input:
  `eval/datasets/messy_insurance/source_schema_enriched.yml`.

### 3.2 Profiling file producer (ADR-0008 #4)
New CLI input `--profiling <file.yml/json>` (mirrors `--source-schema`): loaded by
`src/vault_agent/profiling.py: load_profiling` (attributable `ValueError`; empty → inert)
into `state.profiling` (table → column → `ColumnProfile`:
`uniqueness_ratio/null_ratio/distinct_count/example_values`). Reference:
`eval/datasets/messy_insurance/profiling.yml`. Never produced by the pipeline logging into
a source.

### 3.3 Multi-source hub — deferred to WP10
One business key fed by several sources (`Q_A.partner.partner_id` + `Q_B.customer.
customer_id` → one hub) is not representable in today's model/generator. **WP10** adds
`Hub.sources`, per-source staging with canonical-key aliasing, and the union hub. In WP9,
a concept resolving to more than one legitimate source column lands in **`unresolved`**
with both candidates in the evidence (never force-picked) and a `MAPPING_UNRESOLVED` flag —
honest output until WP10 gives it a home. Same-as links (asserted-equivalent but differing
keys) stay deferred beyond WP10.

## 4. The mapping agent

`src/vault_agent/agents/source_mapper.py: SourceMapperAgent`, split like `data_contract`:

- **Deterministic core (keyless-tested):** concept work-list from the validated model
  (hub business keys as `business_key`, satellite attributes as `attribute`, entity from
  the construct); prompt payload assembly; **post-validation** (existence + type-compat →
  demote to `unresolved`; never invent a column); write `state.mappings`; raise
  `FlagKind.MAPPING_GAP` (advisory, aggregatable) per gap and `FlagKind.MAPPING_UNRESOLVED`
  per unresolved concept.
- **Injectable `MappingProposer` (Protocol):** `AnthropicMappingProposer` via
  `ForcedToolCaller(get_settings().primary_model)` — Sonnet-tier; tool schema/prompt lifted
  from the spike's variant B (one decision per concept: `map|gap|unresolved`, confidence,
  evidence).

**Graph placement (decision (a)):**
`validator --pass--> source_mapper --> code_generator --> human_checkpoint --> adr_author`.
Generation runs with *proposed* bindings; if the human changes a binding at ratification,
the resume path regenerates the affected staging (the resume already rewrites artifacts).
The mapper runs outside the re-model loop (only on a stable model).

## 5. State + ratification (decisions Q3/Q4)

- Promote the spike's `ProposedMapping` into `state.py` verbatim, plus
  `Proposal.ratification_status: Literal["proposed","accepted","overridden"] = "proposed"`.
- `write_outputs` emits **`mappings.review.yml`** (one row per proposal with evidence,
  category and confidence inline; gaps + unresolved listed);
  `vault-agent resume --mappings <edited file>` applies it (edit-and-resume, ADR-0006).
  `--map "concept=TABLE.COLUMN"` stays as a small-override shortcut.
- Gaps/unresolved join the review queue (two new `FlagKind`s in `REVIEW_FLAG_GROUPS`,
  aggregatable). `requires_signoff` semantics **unchanged** — a gap is honest output, not
  a blocker.

## 6. Rename layer (decision Q6/Q6a)

- **Hub business key:** for a **single-source** hub (all of WP9), the ratified source
  column name is carried as `src_nk` — *no gratuitous rename* (behaviour change only for
  mapped runs; unmapped runs stay byte-identical). The business-term canonical name
  applies when sources *disagree* — that case arrives with WP10.
- **Satellite attributes:** a ratified `(table, column)` binds staging to the source
  column and **keeps the source column name** (no business-label rename on mapped runs).
  The one-sat-per-source split is WP10 scope (needs multi-source).
- *Implementation:* `staging_generator.bind_sources` consumes ratified `state.mappings` —
  a ratified binding overrides the WP7 inference; ADR-0004 grounding warnings clear for
  mapped concepts (they resolve, not just warn).

## 7. Confidence semantics (decision Q2)

Carry a deterministic **category** per proposal — `exact_name > comment_grounded >
profiled_key > llm_semantic > unresolved` — derived from the returned evidence; the review
queue sorts/flags by category, raw confidence is a secondary signal only. (Evidence: the
deterministic variant's calibration inverted to 0.000 on a confident wrong pick.)

## 8. Scorers + eval (D2 assets, already landed)

Wire the existing `mapping_accuracy`/`gap_detection`/`confidence_calibration` scorers into
`eval/run.py`: after the mapper runs, score `state.mappings` against the case's
`golden_mapping.yml`. Add a small `bank` golden mapping (easy case, high floor); gate it
with `min_scores.mapping_accuracy` once a baseline run is measured. Treat
`ambiguous`-class concepts as unresolved-is-acceptable in the gate (memo thin-evidence #4).

## 9. Tests

Loader tests (enriched + bare schema shapes; profiling valid/empty/malformed, inert
without flag) · mapper deterministic core keyless (work-list assembly, post-validation
demotion, never-invent property, flags, `state.mappings` shape) · ratification-file
round-trip (write → edit → resume; status updates; `--map` shortcut) · staging binding
override incl. source-name preservation · byte-identity guards: unmapped/ungrounded runs
identical (pin BEFORE changes, WP7-baseline style) · eval: golden mappings load, scorers
pin.

## 10. Acceptance criteria

1. `vault-agent run <doc> --source-schema <enriched> --profiling <file>` produces
   `state.mappings` (proposals/gaps/unresolved) + `mappings.review.yml`.
2. On `messy_insurance` the agent reproduces the spike's variant-B band (memo D4) within
   variance; the trap behaviour matches the autopsy.
3. Gaps/unresolved appear aggregated in the review queue; `requires_signoff` unchanged.
4. Ratification (file + shortcut) updates bindings; staging binds ratified source columns
   with source-faithful names; ADR-0004 warnings clear for mapped concepts.
5. Multi-candidate keys land in `unresolved` with both candidates in evidence — never
   force-picked (WP10 pointer in the flag message).
6. Unmapped/ungrounded/no-profiling runs stay byte-identical (regression guards).
7. **Opacity-masked degradation probe:** on a masked schema (`COL_0001…`, golden retained)
   accuracy drops AND the agent degrades honestly (more `unresolved`, lower confidence,
   categories shift toward `llm_semantic`/`unresolved`) — never confident hallucination.
   This closes the ADR-0008 precondition-(c) measurement gap recorded on acceptance.
   **✅ MET (2026-07-14):** `eval/opacity_probe.py` (keyless masking transform + live probe).
   Measured: accuracy 0.972 (real names) → 0.902 (columns masked) → ~0.88 (columns + tables
   masked), `unresolved` rising, categories collapsing to `profiled_key`/`llm_semantic`, and
   **0 confident-wrong proposals across all runs**. Memo thin-evidence #1 updated to CLOSED.
8. Suite + ruff + mypy green; Postgres hardness re-verification on a grounded + profiled +
   ratified single-source run (WP7 §-style) REQUIRED before done.

## 11. Out of scope

Multi-source hub + canonical business-term aliasing + sat-per-source (→ WP10) · same-as
links · pipeline-invoked profiling · DDL/`information_schema` introspection · FK-graph link
discovery.
