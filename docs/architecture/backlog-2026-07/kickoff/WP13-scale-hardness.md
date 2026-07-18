# Kick-off WP13 — Scale hardness test tooling (Charter A)

You are a senior Python engineer working on **vault-agent** (this repository). Your task
is the *tooling half* of WP13: the deterministic landscape generator, the eval cases,
and the usage capture. The live measurement protocol (spec §4) is executed afterwards by
the maintainer — you prepare it, you do not run it. A small commit series is fine
(generator + tests, eval cases, usage capture).

## Read first, in this order
1. `CLAUDE.md` — repo canon; especially the WP6 (eval harness), WP9/WP9.1 (mapper, FK
   demotion, trap classes), WP10 (multi-source hub) and WP3 (`MAX_DOCUMENT_CHARS`,
   prompt caching) milestone paragraphs.
2. `docs/architecture/backlog-2026-07/00-overview.md` — §Shared conventions + DoD.
3. `docs/architecture/backlog-2026-07/wp13-scale-hardness-spec.md` — your spec.
4. `docs/architecture/backlog-2026-07/spike-mapping-results.md` +
   `eval/datasets/messy_insurance/` (source_schema_enriched.yml, profiling.yml,
   golden_mapping.yml) — the style and trap-class source your generator parameterises.
5. `eval/datasets.py`, `eval/run.py`, `eval/scorers.py` — the WP6 loader/runner/scorer
   shapes you extend; `eval/mapping.py` for the golden-mapping form.
6. `src/vault_agent/llm.py` — `ForcedToolCaller` (where the injectable `usage_recorder`
   lands) and `tests/test_llm.py` (the stub-client pattern; extend it with usage
   payloads).
7. `src/vault_agent/agents/requirements_parser.py` — `MAX_DOCUMENT_CHARS` (the
   generator warns near it, never silently).

## Task
Spec §2 generator (`eval/scale/`, seeded, keyless, byte-deterministic) · §3 eval cases
(`scale_30` committed, 100/300 generated on demand from `(N, seed)`) + `usage_recorder`
in `ForcedToolCaller` + totals in eval result JSONs · findings-doc template
(`docs/architecture/scale-test-findings.md`).

## Constraints
- Dependency direction stays eval → src; the core package gains NO new dependency and NO
  behaviour change when `usage_recorder` is unset.
- Do not commit large generated YAML for the 100/300 steps.
- Trap classes are parameterised and seeded, not copied verbatim from messy_insurance.
- The golden sample follows WP9.2 universe semantics (sampled concepts, not all tables).

## Definition of Done
Spec acceptance criteria 1–4 verified (5 is the maintainer's live half — your handover
lists the exact commands to run it: generate 30/100/300, `python -m eval.run
--dataset scale_N`, where the findings go) · all new tests keyless · `uv run pytest -q` /
`ruff` / `uv run mypy src/vault_agent` (+ eval per mypy config) strict green · bank demo
guardrails green · CLAUDE.md milestone paragraph · conventional commits referencing the
spec.
