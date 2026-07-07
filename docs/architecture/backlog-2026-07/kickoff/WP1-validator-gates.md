# Kick-off WP1 — Four new validator gates

You are a senior data engineer with Data Vault 2.0 expertise working on **vault-agent**
(this repository). Your task is exactly one work package; do not expand scope.

## Read first, in this order
1. `CLAUDE.md` — repo canon. Note especially: DV rules live in
   `src/vault_agent/rules/dv2_rules.py`, never hard-coded in agents/prompts.
2. `docs/architecture/backlog-2026-07/00-overview.md` — §Shared conventions + DoD.
3. `docs/architecture/backlog-2026-07/wp1-validator-gates-spec.md` — your spec.
4. `src/vault_agent/agents/validator.py` (all of it — mirror its patterns exactly),
   `src/vault_agent/rules/dv2_rules.py` (`effectivity_date_pair`, `normalize_identifier`,
   `DV_MODELING_RULES`), `src/vault_agent/agents/code_generator.py`
   (`_hub_hashkey`, `_render_satellite`), `tests/test_agents/test_validator.py`.

## Preconditions
WP4 (typed `ValidationIssue`) should be merged; if it is not, STOP and report — do not
implement against the dict shape.

## Task
Implement the spec: gates `E_EFFSAT_DATE_ORDER` / `W_EFFSAT_DATE_ORDER_UNVERIFIED`,
`E_SAT_DUP_ATTR`, `E_HUB_HK_COLLISION`, `E_DUP_HUB`; the generator/validator eff-sat
attribute-count alignment (§3); the one [GUIDE] rule line (§4); tests per §5.

## Constraints
- Reuse `effectivity_date_pair` and `normalize_identifier` — re-implementing token or
  normalisation logic is a spec violation.
- Deterministic, sorted, stable issue output (match existing gates).
- The bank demo model must trip none of the new gates
  (`tests/test_demo_bank_postgres.py` stays green untouched).

## Definition of Done
Spec §6 acceptance criteria verified · `uv run pytest -q` / `ruff` / `mypy strict` green ·
validator docstring + CLAUDE.md gate-count wording updated · conventional commit
referencing the spec.
