# LOOPS.md mapping — Karpathy's agent-loop rules vs. vault-agent

Source: Andrej Karpathy, *LOOPS.md: Field Notes on Agents That Run for Days — A Short
List of Rules for Letting the Model Drive* (working notes, v060726, 2026). Adopted
**post hoc**: vault-agent's architecture predates our reading of the document
(2026-07-22); the matches below are convergent design, not implementation of the rules.
The document is a lens for auditing the harness, not a blueprint — and one rule is
deliberately deviated from (VIII, see below). House style follows
`dsaf-mapping.md`/`ireb-mapping.md`: adopted / partially adopted / deviated, each with
the concrete counterpart and rationale.

## Rule-by-rule

### I. Write the loop, not the prompt — adopted (convergent)

The unit of design is the LangGraph state machine, not any single prompt: gather
(requirements_parser) → reason (dv2_modeler) → act (code_generator) → verify
(validator) → repeat (re-model loop, bounded by MAX_MODELING_ATTEMPTS). Prompts are
loaded artifacts (`src/vault_agent/prompts/*.md`), versioned and injected — never
hand-iterated in a chat window.

### II. Separate the roles — adopted (convergent)

Per-agent files, prompts, and context: the modeler never grades its own work; the
validator is deterministic (cannot be sycophantic by construction); the adr_author is
the sole writer of `state.adrs`. Karpathy's "the model becomes sycophantic the moment it
grades itself" is exactly why the validator is *not* an LLM.

### III. Negotiate the contract first — adopted (convergent)

The testable-assertions checklist exists at two levels: the [ENFORCE] gates with stable
E_/W_ codes (32 as of WP10; count the codes, don't trust prose) are the per-run contract,
and the eval golden datasets with `min_scores` gates are the per-release contract.
Karpathy's sizing heuristic (~27 criteria; ten is too few, the evaluator rubber-stamps)
lands remarkably close to the gate count — noted as anecdote, not target.

### IV. Write to disk, not to context — adopted (convergent)

State is one pydantic model persisted via AsyncSqliteSaver; a paused run leaves
`pending.json` + the checkpoint thread; artifacts (review-queue.md, mappings.review.yml,
report.html, ADR) are files. The pipeline can crash, lose its process, and resume from
disk (`vault-agent resume`). Karpathy's three-file test holds: plan/state/review-queue
describe any run.

### V. Let the loop restart — adopted (convergent)

Validation failure throws the model away and re-models (fresh proposal, errors-only
feedback per WP3) instead of patching; the human enters only at the HITL checkpoint —
"when the contract itself is wrong, not when the build is" maps to: gates and golden
sets are human-owned, individual re-model attempts are not.

### VI. Score the subjective — adopted (convergent)

The eval scorers are the written-down rubric; calibration-on-references maps to the
case design (bank = high-floor reference, messy_insurance = trap set, scale_* =
stress). Confidence categories (exact_name > comment_grounded > profiled_key >
llm_semantic) are a graded taste axis with deterministic semantics.

### VII. Read the traces — **gap, closed by WP15 (landed 2026-07-22)**

The one rule with no counterpart at reading time: LLM interactions were invisible after
the fact (the CDK failure took 4 live runs to diagnose; WP9.1's over-deferral was found
by reading one transcript by hand). WP15 (`wp15-trace-capture-spec.md`) added per-run
grep-able jsonl transcripts via a recorder seam on ForcedToolCaller — default on
(`--no-trace` to opt out), local-first, under `.vault-agent/traces/`.

### VIII. Delete the harness — **partially adopted, deliberately deviated**

The rule assumes the harness exists to compensate for the model. vault-agent's harness
splits in two, and the rule applies to only one half:

- **Model-compensation (rule applies):** prompt steering lines (DV_MODELING_RULES
  entries like the CDK "key column, not payload" line, added after LLM steering failed
  4/4) and the three pre-gate backstops that repair LLM output before validation
  (`attributes_without_cdk` in the modeler, `fk_demotion` in the source_mapper per
  WP9.1, and `effsat_two_attributes` — the code generator's rejection of an effectivity
  satellite without exactly two date attributes). These SHOULD be re-tested per model
  release and deleted when a model stops needing them. WP16
  (`wp16-steering-retest-spec.md`, landed 2026-07-22) built the instrument: steering
  registry with ids/origins, backstop-fire telemetry, `eval/ablate.py`, and the release
  protocol in `docs/architecture/steering-ledger.md`.
- **Product (rule deviated from):** the deterministic validator gates. Their existence
  claim is "the generated model is provably DV2.0-conformant, independent of which
  model produced it" — the audit property a DACH enterprise buys. A perfect model makes
  the gates silent, not superfluous (tests aren't deleted because developers improved;
  a green gate run is the certificate). Practically, the gates are also what makes
  rule-VIII deletion *safe*: removing a backstop is a reversible experiment only
  because the matching E_-gate catches the failure if the deletion was premature.

Deletion discipline test: *would you keep it given a perfect model?* Backstop: no →
ablatable. Gate: yes → product.

### IX. The bottleneck always moves — adopted (convergent)

The WP history is this rule enacted: staging gap (WP7/P3) → mapping (WP9/9.1) → eval
universe (WP9.2/WP14) → cost/robustness (WP3, contract truncation) → crash-safety
(WP14.1) → observability (WP15/16). `scale-test-findings.md` institutionalises "find
the next bottleneck" as a written protocol.

## Non-adopted context

LOOPS.md targets autonomous multi-day generator/evaluator loops over *subjective*
outputs (apps, sites). vault-agent's loop is minutes-long, single-pipeline, over
*rule-governed* outputs with a human sign-off gate — which is why the deterministic
validator can replace the LLM evaluator entirely, and why rule VIII needed the split
above. Cited when relevant alongside the DV2.1/DSAF/IREB foundations; ideas subject to
revision as the models change (the document says so itself).
