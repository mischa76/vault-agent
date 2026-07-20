# Vault-Agent — Architecture & Implementation Review

*Translated from the German original (2026-07-20); content unchanged.*

**Date:** 2026-06-13
**Scope:** `src/vault_agent/**`, `tests/**`, `pyproject.toml`, prompts and rules.
**Method:** Static code study. `ruff`, `mypy`, and `pytest` could not be run in this session
(the sandbox cannot mount the WSL UNC path) — the findings are not cross-checked against a
test run. Recommendation: verify in CI.

---

## Overall verdict

The architecture is clean and matches the ambition stated in `CLAUDE.md`. The LangGraph graph
is deliberately thin, the business logic lives in the agents, the DV2.0 rules in pure Python
(`rules/dv2_rules.py`), the prompts as `.md`. The separation between LLM-driven agents (parser,
business_key, modeler) and deterministic agents (code_generator, validator, adr_author) is
consistent and well justified — it makes code generation and validation reproducible and
hallucination-free.

Three patterns stand out as particularly well done: (1) the pervasive dependency injection via
`Protocol` extractors, which makes every LLM agent testable without an API key; (2) forced
tool-use with schemas derived from pydantic, so structured outputs validate back into the
models without ad-hoc parsing; (3) defense-in-depth, where the validator independently
re-checks structural invariants that the modeler and generator already enforce.

The main weakness is a **genuine correctness gap in effectivity-satellite generation**
(see H-1): the `driving_key`, which the modeler, validator, prompt, and ADR handle carefully,
is ignored by the code generator. Beyond that there is an invalid model name in the config and
a few roadmap gaps (no use of `source_schemas`, no PDF/DOCX input path).

---

## Findings by priority

| # | Severity | Area | Finding |
|---|----------|------|---------|
| H-1 | **High** | code_generator | Effectivity sat: `driving_key` is ignored, `src_dfk` = first connected hub |
| H-2 | Medium | config | `heavy_model = "claude-opus-4-6"` is not a valid model string → modeler runs fail |
| M-1 | Medium | requirements_parser | No PDF/DOCX input path, although source documents are `.docx`/`.pdf` per the charter |
| M-2 | Medium | state/pipeline | `source_schemas` is read by no agent; the model is built purely from prose |
| L-1 | Low | graph | Retry cap couples to the audit log (`decisions`) instead of an explicit counter |
| L-2 | Low | code_generator | `_to_column` can collapse two labels onto the same column (no collision detection) |
| L-3 | Low | config | `Settings()` at import → without `ANTHROPIC_API_KEY` any direct import of `config` crashes |
| L-4 | Low | dv2_modeler | Draft-ADR fragments accumulate across retries in `state.adrs` (only visible on abort) |
| L-5 | Low | tests | The eff_sat test cements the faulty behaviour from H-1 (stays green, but is wrong) |

---

## Details

### H-1 — Effectivity satellite ignores the driving key (correctness)

`_render_eff_sat` picks the driving foreign key hard-coded as `hub_fks[0]` — i.e. the *first*
connected hub — and all the rest as `src_sfk`:

```python
driving_fk = hub_fks[0]
secondary_fk = hub_fks[1:]
```

`link.driving_key` is never read during rendering. This is inconsistent with the rest of the
system, which takes the driving key very seriously: the validator enforces its existence
(`E_EFFSAT_NO_DRIVING_KEY`), the modeler prompt explains at length that the driving key is the
"one at a time" side (e.g. the employee hub in "an employee has one manager at a time"), and
the ADR records it. If the modeler emits `connected_hubs` in an order where the driving hub is
not first, then the generated effectivity satellite end-dates by the **wrong** key — a
semantically incorrect Data Vault construct that passes validation.

Recommendation: thread `link.driving_key` into `_render_eff_sat` and derive `src_dfk`/`src_sfk`
from it (driving = hash keys of the hubs in `driving_key`, secondary = the rest). Convert the
test `test_effectivity_satellite_generates_on_link` accordingly to driving-key selection (see
L-5).

### H-2 — Invalid heavy-model string

```python
heavy_model: str = "claude-opus-4-6"
```

There is no model `claude-opus-4-6` (the current one is `claude-opus-4-8`). The
`Dv2ModelerAgent` uses `settings.heavy_model` by default, i.e. a real pipeline run of the most
important reasoning step would fail with a 404/model-not-found. `primary_model =
"claude-sonnet-4-6"` is valid. Please fix the heavy-model string and ideally verify both values
against the API.

### M-1 — No PDF/DOCX input path

`RequirementsParserAgent._read_document` only does `path.read_text(...)`. `pypdf` is a
dependency but is not used; a PDF/DOCX would be read as text garbage. The CLI restricts the
input to "markdown/text" in the help text — that is consistent, but contradicts the project
goal (source documents are `.docx`/`.pdf` per the charter). Recommendation: introduce a small,
file-type-dispatching reader (md/txt directly, pdf via pypdf, docx via python-docx) before
processing real requirements documents.

### M-2 — `source_schemas` unused

`VaultAgentState.source_schemas` exists but is consumed by no agent. Business keys and
satellite attributes are "invented" from the requirements text alone, not validated against
real source columns. For DACH DWH landscapes, matching against an actual source schema (columns
exist, BK is not-null/unique in the source) is a central value-add. A sensible roadmap item —
possibly a dedicated "schema_grounding" step between business_key_identifier and dv2_modeler.

### L-1 — Retry cap coupled to the audit log

`route_after_validation` counts `decisions` with `agent == "dv2_modeler"` to enforce the retry
cap. This couples control flow to logging: if someone changes how/whether the modeler records
its decision, the loop guard breaks silently. More robust would be an explicit
`modeling_attempts: int` in the state, incremented by the modeler.

### L-2 — Possible column collision in `_to_column`

`_to_column` normalises via `[^0-9a-zA-Z]+ → _` and UPPER. "customer-id" and "customer id" both
yield `CUSTOMER_ID`. There is no collision detection on generated column names. Harmless with
clean inputs, but a potential silent error with real requirements documents. A warning in the
generator on colliding normalisations would be cheap.

### L-3 — `Settings()` at module import

`settings = Settings()` runs when `config.py` is imported and requires `anthropic_api_key` with
no default. The "no API key needed" property only holds because `config` is imported
exclusively *lazily* (in the extractor `__init__`). A direct `import vault_agent.config`
without a set key, however, crashes hard. Consider a lazy `get_settings()` accessor or a
clearer error message.

### L-4 — Accumulating draft ADRs

The modeler appends a draft-ADR fragment to `state.adrs` on *every* run. On the happy path,
`adr_author` sets `state.adrs = [adr]` and overwrites them. But if the retry cap is reached
(route → `END`), N fragments remain. Harmless, but untidy — discard the fragments before
re-modeling, or do not collect them in the first place.

### L-5 — Test freezes the H-1 bug

`test_effectivity_satellite_generates_on_link` explicitly asserts
`src_dfk = "ACCOUNT_HK"  # driving = first connected hub`. The test is green, but it encodes the
wrong behaviour. After fixing H-1 this test must be switched to the driving-key-based selection
— otherwise it masks the correction.

---

## What is good (deliberately keep)

The deterministic agents (code_generator, validator, adr_author) without an LLM are the right
design decision and cleanly implemented. The validator is structured as an independent gate
with clear `E_`/`W_` codes and also checks cross-construct (grain redundancy, attribute
overlap, BK collision) — that is methodologically strong. The rules in `dv2_rules.py` capture
the Linstedt/Olschimke canon well (one hub per BK, links without descriptive attributes,
satellite split axes, unit of work, collision code), and the deliberate framing of the Vos
revisions as "ADR-gated, never a silent default" shows good methodological discipline. Test
coverage across all agents, graph, and CLI is broad; the stubs (`data_contract`,
`orchestrator`) are honestly marked as `NotImplementedError` and consistent with the documented
milestone.

---

## Recommended order

1. Fix **H-1** (driving-key threading) and pull in **L-5** — largest correctness risk, touches
   the DV core.
2. Correct the **H-2** model string — otherwise no real modeler step runs.
3. **M-1** multi-format reader, **M-2** schema grounding — unlock real requirements documents.
4. **L-1 through L-4** as cleanup/hardening work in a later PR.
