# Kick-off WP8 — Role-qualified link hub references

You are a senior data engineer with deep Data Vault 2.0 expertise working on
**vault-agent** (this repository). This is the most invasive WP in the backlog: a state
model change that ripples through modeler, validator, generator, staging, and ADR author.

## Read first, in this order
1. `CLAUDE.md` — repo canon; note "Don't hard-code DV2.0 rules in agent prompts" and the
   ADR-gating convention for model changes.
2. `docs/architecture/backlog-2026-07/00-overview.md` — §Shared conventions + DoD.
3. `docs/architecture/backlog-2026-07/wp8-multi-role-links-spec.md` — your spec, including
   the draft ADR-0009.
4. `src/vault_agent/state.py` (`Link`), `src/vault_agent/rules/dv2_rules.py`,
   `src/vault_agent/agents/code_generator.py` + `staging_generator.py` +
   `validator.py` (link handling end to end), `demo/bank_postgres/` (builder, seeds,
   guardrail test — you will extend all three),
   `docs/architecture/adrs/` (ADR format).

## Preconditions
1. WP1 and WP7 merged (you adapt their gates/staging paths).
2. **File ADR-0009 first** (from the spec's §2 draft, status Proposed) and get it
   explicitly accepted by the maintainer before writing implementation code. If you cannot
   obtain acceptance, deliver only the ADR and stop.

## Task
Implement the spec: `LinkHubRef` union with before-validator normalisation,
role-qualified naming helpers in `rules/` (`role_fk_column`, `role_bk_column`),
ripple-through per §5 (generator, staging, validator incl. `E_LINK_DUP_ROLE`, modeler
[GUIDE] line, ADR rendering), and the `link_transfer` demo extension per §6.

## Constraints
- Backward compatibility is acceptance criterion #1: plain-string links must produce
  byte-identical output (pin with a regression test on the regenerated bank demo before
  touching generator code).
- All naming goes through the new `rules/` helpers — no ad-hoc prefixing anywhere.
- The demo Postgres verification (§6) is part of the WP, not optional; if you have no
  Postgres available, deliver everything else and mark it as the single open
  human-verification step in your handover.

## Definition of Done
Spec §7 acceptance criteria verified · ADR-0009 accepted and filed ·
`uv run pytest -q` / `ruff` / `mypy strict` green · CLAUDE.md milestone paragraph ·
conventional commits referencing spec + ADR.
