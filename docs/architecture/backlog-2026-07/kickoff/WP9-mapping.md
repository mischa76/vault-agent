# Kick-off WP9 — Business↔source mapping

You are a senior data engineer implementing exactly ONE work package for the vault-agent
project. Do not expand scope. This WP productionises the mechanism the mapping spike
measured — the spec encodes decisions already taken by the maintainer; do not re-litigate
them.

## Read first, in this order
1. `CLAUDE.md` — repo canon (binding).
2. `docs/architecture/backlog-2026-07/00-overview.md` — §Shared conventions + DoD.
3. `docs/architecture/backlog-2026-07/wp9-mapping-spec.md` — your spec (final, decisions
   inlined).
4. `docs/architecture/backlog-2026-07/spike-mapping-results.md` — the evidence behind every
   design choice, incl. the trap autopsy your implementation must reproduce (§10.2).
5. `docs/architecture/adrs/ADR-0008-source-to-target-mapping.md` (Accepted) — guardrails,
   incl. the acceptance caveat your §10.7 probe closes.
6. Assets that already exist: `eval/mapping.py`, `eval/scorers.py` (mapping scorers),
   `eval/datasets/messy_insurance/{golden_mapping,profiling,source_schema_enriched}.yml`,
   and — if still present in history — the spike prototypes under `spike/` (git log) for
   the variant-B prompt/tool schema to lift.
7. Code you extend: `state.py`, `source_schema.py`, `agents/data_contract.py` (the
   agent-split pattern to mirror), `agents/staging_generator.py` (`bind_sources`),
   `cli.py` (inputs, write_outputs, resume), `graph.py`, `llm.py`.

## Order of work
1. Byte-identity guards FIRST (unmapped/ungrounded runs — spec §9).
2. §3.1 enriched SourceColumn union + §3.2 profiling producer (each inert-compatible).
3. §4 SourceMapperAgent (deterministic core keyless; injectable proposer) + graph edge.
4. §5 state.mappings + mappings.review.yml + resume (`--mappings`, `--map`).
5. §6 staging binding override (source-faithful names) + §7 category semantics.
6. §8 eval wiring + bank golden mapping.
7. §10.7 opacity probe + §10.8 Postgres re-verification (document results in CLAUDE.md).

## Constraints
- All LLM calls via `ForcedToolCaller`, Sonnet-tier; keyless test suite stays keyless.
- Never invent a column (post-validation demotes; the spike's key safety property).
- Multi-candidate keys → `unresolved` + flag (WP10 pointer); do NOT implement Hub.sources
  here.
- Live runs (eval band §10.2, opacity probe §10.7, Postgres §10.8) need the local
  API key/.env — if your environment lacks them, deliver everything else and list these as
  explicit open human-verification steps.

## Definition of Done
Spec §10 acceptance criteria (live items as documented open steps if needed) ·
pytest/ruff/mypy green (src + eval) · CLAUDE.md milestone paragraph · conventional commits
referencing spec + ADR-0008.

## Final report
Deliverables, verification tails, §10 checklist (met/not-met + evidence), open
human-verification steps, and anything the spec under-specified (flag, don't improvise).
