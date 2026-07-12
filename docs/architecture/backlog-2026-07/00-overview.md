# Backlog 2026-07 — fully specified work packages

Status: Proposed · Author: Mischa Eismann + Claude (project review 2026-07-06/07)

This package turns every open point from `PROJECT_REVIEW_2026-07-06.md` (and the deferrals
recorded in CLAUDE.md) into implementation-ready specs. Each work package (WP) has a spec in
this directory and a self-contained kick-off prompt in `kickoff/` that a developer agent
(e.g. Claude Opus 4.8 via Claude Code) can execute without further briefing.

## Work packages and recommended order

| WP | Spec | What | Size | Depends on |
|----|------|------|------|------------|
| WP4 | `wp4-typed-validation-issue-spec.md` | `ValidationIssue` pydantic model replaces issue dicts | S | — |
| WP1 | `wp1-validator-gates-spec.md` | 4 new validator gates (eff-sat date order, dup attr, hub-HK collision, dup hub) | S/M | WP4 |
| WP2 | `wp2-adr-author-spec.md` | ADR author: correct caveat, per-output numbering, drop repo-path coupling | S | — |
| WP3 | `wp3-llm-cost-spec.md` | Prompt caching, errors-only retry feedback, input-size guard | S | — |
| WP5 | `wp5-hygiene-spec.md` | Renderer merge, dead code/deps removal, logging + `--debug`, checkpoint pruning, doc fixes | M | — |
| WP6 | `wp6-eval-harness-spec.md` | Eval harness: golden datasets, deterministic scorers, optional LangSmith layer | M/L | WP4 |
| WP7 | `wp7-staging-refinements-spec.md` | ma_sat staging grain, bound `source()` refs, seed column types | M | — |
| WP8 | `wp8-multi-role-links-spec.md` | Role-qualified link hub references (self-referencing links) — includes draft ADR-0009 | L | WP1, WP7 |

Rationale for the order: WP4 changes the shape WP1's new gates emit and WP6's scorers
consume — do it first. WP1/WP2/WP3/WP5 are independent of each other. WP8 is the most
invasive model change; land it last, on top of the hardened validator and staging layers.

## Parallel execution plan (waves)

Parallelism is limited by *file overlap* more than by logical dependencies: WP4 touches
`state.py`/`validator.py`/`orchestrator.py`/`dv2_modeler.py` (overlaps almost everything),
WP5 is a cross-cutting sweep, WP8 touches the whole link pipeline. The conflict-free
schedule, one agent per WP, one git worktree/branch per agent:

| Wave | Parallel WPs | Why this is safe |
|------|--------------|------------------|
| 1 | **WP4 + WP2** | WP2 (`adr_author.py` + own tests) is fully disjoint from WP4 |
| 2 | **WP1 + WP3 + WP6** | after WP4 merges they are near-disjoint: validator/rules vs. llm/parser/modeler vs. additive `eval/` |
| 3 | **WP7 + WP5** | WP7 needs WP1's final validator; WP5 sweeps the then-quiet cross-cutting files (coordinate `langsmith_*` with WP6) |
| 4 | **WP8 alone** | invasive; ADR-0009 gate; needs WP1 + WP7 |

Merge discipline (the actual success condition): every agent works on its own branch,
rebases onto main before review; merges are **serial**, full test suite as the gate — never
merge two WPs simultaneously. Known trivial conflicts: every WP appends a CLAUDE.md
milestone paragraph (resolve append-order at merge), and the kick-offs' STOP preconditions
(WP1/WP6 require WP4 merged) must be honoured by the wave scheduler, not the agents.

## Explicitly NOT in this package (needs a design spike / ADR first)

- **Business↔source mapping + DDL/DB introspection (Phase 2, ADR-0008).** The five
  preconditions in ADR-0008 are a contract with the user organisation; implementation must
  not start before an accepted ADR defines the degraded-mode behaviour per missing
  precondition. Spike output should be a spec in this format.
  *Update 2026-07-12: the spike is chartered — see `spike-mapping-charter.md` +
  `kickoff/SPIKE-mapping.md`; it produces the WP9 spec draft and the ADR-0008 status
  recommendation.*
- **Contradiction reconciliation (reality-test #1).** Requires prompt-design
  experimentation with live LLM runs (and ideally WP6's eval harness to measure it). Not
  deterministically speccable today.
- **Typed source-schema quality gates (reality-test #4)** — blocked on the same Phase-2
  schema model as ADR-0008.
- **Business Vault assist, information-layer scaffolding, UI** — per ADR-0007 scope
  boundaries and CLAUDE.md ("no UI until the pipeline is stable on 2+ demos").

## Shared conventions (binding for every WP)

1. **Repo canon first.** Read `CLAUDE.md` fully before coding: technology lock, code
   conventions, "What NOT to do", current milestone. It overrides anything else.
2. **Rules live in `src/vault_agent/rules/dv2_rules.py`**, never in prompts or agents.
   New thresholds/tokens/constants go there with a comment citing the DV2.0 rationale.
3. **Typed flags.** Agent findings go through `state.flag(...)` (`PipelineFlag`); consumers
   branch on `kind`/`asset`, never on message text. New kinds are added to `FlagKind` and,
   if aggregatable, to `orchestrator.REVIEW_FLAG_GROUPS` + `_GROUP_LABELS`.
4. **Determinism.** Everything except the four LLM extractors must be unit-testable without
   an API key. LLM calls go exclusively through `vault_agent.llm.ForcedToolCaller`.
5. **Never silently guess.** Unknowns are named and flagged for human review.
6. **Definition of Done (every WP):**
   - `uv run pytest -q` green (all existing + new tests), no test deleted without
     replacement;
   - `uv run ruff check .` clean; `uv run mypy src/vault_agent` strict clean;
   - the bank demo guardrail tests (`tests/test_demo_bank_postgres.py`) still pass and the
     regenerated demo models stay byte-identical unless the spec says otherwise;
   - CLAUDE.md "Current milestone" gets a dated paragraph describing what landed;
   - docs that the change invalidates are updated in the same commit.
7. **Commit style:** conventional commits, one WP = one commit (or a small series), spec
   referenced in the body.

## How to run a developer agent on a WP

Give the agent the matching `kickoff/WPn-*.md` file as its task prompt, with the repo as
working directory. The kick-off tells it what to read, what to build, and how to verify.
Review its output against the spec's acceptance criteria before merging.
