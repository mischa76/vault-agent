# WP13 — Scale hardness test: the 300-table landscape (Charter A)

Status: Proposed · Size: M (tooling) + live-run budget · Depends on: WP6 eval harness,
WP9/WP9.1 mapper, WP10 multi-source hub (all landed). Charter:
`../roadmap-2026-07-productization.md` §Charter A.

## 1. Problem

The pipeline is verified on demo-sized cases (≤ 6 tables, ≤ 38 columns in the hardest
grounded case; the 256-column contract test covered the *width* axis). Class-1
landscapes have hundreds of source tables across several systems. Nobody knows today
where vault-agent first breaks on *breadth* — LLM output caps, mapper accuracy decay,
validator noise, an unusably long review queue, token cost, wall-clock. The point of
this WP is to find the first breakpoints ourselves, cheaply and reproducibly, before a
customer does.

Two deliverable halves: (a) a **deterministic, keyless synthetic-landscape generator** +
eval cases (implementable now), (b) a **measurement protocol** executed as live runs in
the WSL environment (API key, real cost — executed by Mischa/Claude Code after (a)
merges, results recorded in a findings doc).

## 2. Generator (`eval/scale/`)

`python -m eval.scale.generate --tables N --seed S --out <dir>` writes a complete input
set for a landscape of N source tables:

- **`source_schema.yml`** — N tables across 3 synthetic source systems (a core/legacy
  system with cryptic DACH-style names, a CRM with anglophone names, a smaller
  peripheral system), types + comments (the ADR-0008 precondition-(c) shape). Naming
  realism is *lifted from the messy_insurance style*, seeded and parameterised, and must
  include the spike's five trap classes in known proportions: abbreviations
  (`VERTR_NR`), false friends, technical GUIDs shadowing business keys, synonyms across
  systems, and FK comments referencing anchor tables (exercising the WP9.1 demotion).
  A seeded fraction of entities exists in ≥ 2 systems with differing key columns
  (multi-source hubs, WP10); a seeded fraction of tables is wide (100–300 columns) so
  the width axis rides along (modeler satellite splitting around
  `SAT_WIDE_ATTRIBUTE_THRESHOLD`).
- **`profiling.yml`** — seeded plausible profiles (uniqueness/null ratios, examples)
  consistent with the schema, including the statistics trap (a GUID profiling "better"
  than the true business key).
- **`requirements.md`** — a generated requirements document naming the business
  entities/relationships the model should cover; its size must scale with N and the
  generator must report when it approaches `MAX_DOCUMENT_CHARS` (the WP3 guard is part
  of what we measure, not something to dodge).
- **`golden_mapping.yml`** — for a seeded sample of ~30 concepts (not all N tables:
  hand-veriable spot checks, WP9.2 universe semantics), the known-correct
  mappings/gaps, generated alongside (the generator *knows* the truth — that is the
  whole trick of synthetic data).

Determinism: same `(N, seed)` → byte-identical outputs (pinned test). All generator
logic keyless, no imports from `vault_agent` beyond `rules.normalize_identifier` if
needed (keep the dependency direction eval → src, as WP6 established).

## 3. Eval cases + usage capture

- New cases `eval/datasets/scale_30/`, `scale_100/`, `scale_300/` referencing generated
  inputs (committed for 30; 100/300 generated on demand by the runner via the generator —
  do NOT commit hundreds of KB of synthetic YAML for the large steps, the dataset entry
  stores `(N, seed)` and calls the generator). `scale_30` gets loose `min_scores`
  (mapping_accuracy ≥ 0.8, pipeline_health = 1.0); 100/300 stay ungated (measurement,
  not regression gates).
- **Token/cost capture:** `ForcedToolCaller` (the single LLM path) gains an optional
  injectable `usage_recorder` callback receiving per-call `(model, input_tokens,
  output_tokens, cache_read_tokens)` from `response.usage` — in-memory, no behaviour
  change when unset (default None; keyless-tested via the existing stub client).
  `eval/run.py` registers a recorder and writes the totals into each result JSON; the
  per-repeat summary prints them. This is generally useful (class-1 cost transparency),
  not scale-test-only.
- The runner already records wall-clock per run; additionally record
  `review_items_total` and the *rendered* review-queue line count (readability proxy —
  does WP-aggregation keep the checkpoint scannable at hundreds of flags?).

## 4. Measurement protocol (live, WSL, budget-gated)

Executed AFTER the tooling merges; one repeat per step, escalate only while the previous
step completed: 30 → 100 → 300. Per step record in
`docs/architecture/scale-test-findings.md` (template committed with this WP): wall-clock,
token totals + cache-read share, cost estimate, hubs/links/sats counts, validation
verdict + issue counts, mapping accuracy vs the golden sample, gap/unresolved counts,
review-queue totals + rendered length, report.html size and whether the WP11 Mermaid
graph still renders usably, and any hard failure (which agent, which limit). Abort
criteria: a step that hard-fails twice, or projected cost for the next step exceeding
the budget Mischa sets before starting. Every breakpoint found becomes its own follow-up
WP — this WP only *finds* them.

## 5. Tests (keyless)

Generator determinism (byte-identity for fixed seed) · trap-class proportions present
(count, not exact strings) · schema/profiling/golden consistency (every golden concept
exists in the schema; profiling only names declared columns) · requirements size scales
and the near-`MAX_DOCUMENT_CHARS` warning fires · usage_recorder: recorded totals match
the stub client's usage payloads; unset recorder = no behaviour change ·
`scale_30` loads through the WP6 dataset loader.

## 6. Acceptance criteria

1. `generate --tables 30 --seed 42` twice → byte-identical; committed `scale_30` case
   runs through `python -m eval.run --dataset scale_30` structurally (stubbed/keyless
   path exercised in tests; live green verified in WSL before the protocol starts).
2. Usage totals appear in eval result JSONs (stub-verified keyless; live-verified with
   one bank-case run).
3. The findings template exists and the protocol section names the abort criteria.
4. Full suite + ruff + mypy strict green; no new runtime dependency in the core package
   (generator may use stdlib + pyyaml, already present).
5. (Live half, after merge) findings doc filled for at least the 30-step, with either
   all three steps recorded or the first breakpoint precisely characterised.
