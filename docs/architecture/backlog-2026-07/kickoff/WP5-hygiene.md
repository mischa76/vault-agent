# Kick-off WP5 — Hygiene batch

You are a senior Python engineer working on **vault-agent** (this repository). Your task is
exactly one work package with six sub-items; implement them in spec order, one commit per
sub-item.

## Read first, in this order
1. `CLAUDE.md` — repo canon.
2. `docs/architecture/backlog-2026-07/00-overview.md` — §Shared conventions + DoD.
3. `docs/architecture/backlog-2026-07/wp5-hygiene-spec.md` — your spec (§5.1–§5.6).
4. Touched code: `src/vault_agent/cli.py`, `src/vault_agent/agents/orchestrator.py`,
   `src/vault_agent/agents/base.py`, `src/vault_agent/config.py`, `pyproject.toml`,
   `src/vault_agent/prompts/` (which files are actually loaded — `rg load_prompt`).

## Task
§5.1 renderer knowledge merge · §5.2 `ClassVar[str | None]` prompt_path + dead prompt/
`tools/` removal · §5.3 unused deps/settings (check WP6 status for `langsmith_*` first) ·
§5.4 std-lib logging + CLI `--debug` · §5.5 checkpoint pruning on finalise (verify the
current `AsyncSqliteSaver` delete-thread API in the installed version before using it) ·
§5.6 doc-drift fixes.

## Constraints
- Library code configures no logging handlers/levels; only the CLI does.
- Default CLI output must remain unchanged (only `--debug` adds output).
- Before deleting anything, `rg` for references; paste the empty result into the commit
  message.

## Definition of Done
Spec acceptance criteria 1–5 verified · `uv run pytest -q` / `ruff` / `mypy strict`
green · zero `# type: ignore[assignment]` on `prompt_path` · CLAUDE.md milestone
paragraph · conventional commits referencing the spec.
