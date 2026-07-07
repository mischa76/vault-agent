# Kick-off WP3 — LLM cost & robustness

You are a senior Python engineer with Anthropic API experience working on **vault-agent**
(this repository). Your task is exactly one work package; do not expand scope.

## Read first, in this order
1. `CLAUDE.md` — repo canon.
2. `docs/architecture/backlog-2026-07/00-overview.md` — §Shared conventions + DoD.
3. `docs/architecture/backlog-2026-07/wp3-llm-cost-spec.md` — your spec.
4. `src/vault_agent/llm.py` (all — every LLM call goes through `ForcedToolCaller`),
   `src/vault_agent/agents/dv2_modeler.py` (`run`, retry feedback),
   `src/vault_agent/agents/requirements_parser.py` (`_read_document`),
   `tests/test_llm.py` (stub-client pattern — extend it, do not invent a new one).
5. The current Anthropic prompt-caching documentation (docs.claude.com) — verify the
   `cache_control` request shape against the live docs, not memory.

## Task
Implement the spec: (1) cache-controlled system block in `ForcedToolCaller.call`;
(2) errors-only, three-field retry feedback in the modeler; (3) `MAX_DOCUMENT_CHARS`
truncation guard + `FlagKind.INPUT_TRUNCATED` in the parser. Tests per spec.

## Constraints
- All tests remain keyless (the stub client asserts the request shape).
- Check whether WP4 has landed and use the matching issue access style (spec §2.2).
- Never silently truncate — the flag with original/truncated sizes is mandatory.

## Definition of Done
Spec §4 acceptance criteria verified · `uv run pytest -q` / `ruff` / `mypy strict` green ·
CLAUDE.md milestone paragraph · conventional commit referencing the spec.
