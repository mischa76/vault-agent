# Kick-off WP2 — ADR author remediation

You are a senior Python engineer working on **vault-agent** (this repository). Your task is
exactly one work package; do not expand scope.

## Read first, in this order
1. `CLAUDE.md` — repo canon.
2. `docs/architecture/backlog-2026-07/00-overview.md` — §Shared conventions + DoD.
3. `docs/architecture/backlog-2026-07/wp2-adr-author-spec.md` — your spec.
4. `src/vault_agent/agents/adr_author.py` (all), `src/vault_agent/graph.py` (node order —
   understand why GENERATION_GAP flags exist before adr_author runs),
   `src/vault_agent/state.py` (`PipelineFlag`, `FlagKind`),
   `tests/test_agents/test_adr_author.py`.

## Task
Implement the spec: per-output ADR numbering (default 1, deterministic, idempotent —
remove `_DEFAULT_ADR_DIR` / `_next_adr_number` / `adr_dir`), flag-derived caveat replacing
the false "not yet generated" claim, raw-vault + staging counts in References, tests per
§3.

## Constraints
- The caveat must derive from `FlagKind.GENERATION_GAP` flags (kind/asset matching) —
  never from message text, never from re-deriving generator capability.
- Idempotency is a hard requirement: same state in → byte-identical ADR out.

## Definition of Done
Spec §4 acceptance criteria verified (including the `rg` check) · `uv run pytest -q` /
`ruff` / `mypy strict` green · CLAUDE.md milestone paragraph · conventional commit
referencing the spec.
