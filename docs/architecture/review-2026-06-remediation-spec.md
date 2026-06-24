# Remediation Spec — Architecture Review 2026-06-13

> **Purpose:** Turn the findings of the 2026-06-13 architecture review
> ([../../ARCHITECTURE_REVIEW_2026-06-13.md](../../ARCHITECTURE_REVIEW_2026-06-13.md)) into an
> implementation-ready blueprint that can be executed directly in Claude Code. Each finding gets
> the intended behaviour, the exact files to touch, concrete acceptance criteria, and the test
> changes needed. Same two-tier `[ENFORCE]`/`[GUIDE]` discipline as
> [../methodology/dv2-modeling-rules-spec.md](../methodology/dv2-modeling-rules-spec.md).
>
> **Convention:** ADRs (`docs/architecture/adrs/*`) are immutable decision records and are *not*
> edited here. Where a finding changes a recorded decision, this spec calls for a **new** ADR.
> Corrections to living specs (the modeling-rules spec) are made in place.

## How to use this in Claude Code

Work the findings in the **Rollout order** at the bottom. Each section is self-contained: it names
the files, the change, and the acceptance criteria. Every change must keep `ruff`, `mypy --strict`,
and `pytest` green (the deterministic agents run without an API key — no network in CI). Do not
introduce new frameworks or bypass AutomateDV (see `CLAUDE.md` → "What NOT to do").

Definition of done for the whole spec: all H- and M-findings implemented with tests; L-findings
either implemented or explicitly deferred with a one-line note in this file.

---

## H-1 — Effectivity satellite must apply the declared driving key

**Severity:** High (correctness). **Files:** `src/vault_agent/agents/code_generator.py`,
`tests/test_agents/test_code_generator.py`. Canonical rule added to
`docs/methodology/dv2-modeling-rules-spec.md` §2.

**Problem.** `_render_eff_sat` selects `driving_fk = hub_fks[0]` (the first connected hub) and
ignores `link.driving_key`. The modeler declares it, the validator enforces it
(`E_EFFSAT_NO_DRIVING_KEY`), the prompt explains it, the ADR surfaces it — but the generated
`automate_dv.eff_sat` end-dates by whatever hub happens to be first in `connected_hubs`. If that is
not the driving hub, the satellite is semantically wrong yet passes validation.

**Intended behaviour [ENFORCE].** `src_dfk` = the hash key(s) of the hubs named in
`link.driving_key`; `src_sfk` = the hash keys of the remaining `connected_hubs`, in their declared
order. AutomateDV's `src_dfk` takes a single key in the common case and a list when the driving key
spans multiple hubs — render a bare string for one driving hub, a list for several, matching how
`src_fk`/`src_cdk` are already rendered.

**Implementation notes.**
- Thread the parent `Link` (or at least its `driving_key`) into `_render_eff_sat`. Today the call
  site `self._render_satellite(...)` only has `link_fks` (a `dict[str, list[str]]`). Either pass the
  `links_by_name` mapping down, or precompute `link_driving_fks[link.name]` and
  `link_secondary_fks[link.name]` alongside `link_fks` in `run`.
- Map driving-key hub names → hash keys via the existing `hub_hashkeys` dict. Preserve order.
- Guard: if `link.driving_key` is empty at generation time (should already be blocked by the
  validator gate, but the generator is an independent stage), flag for human review with a clear
  message and skip — do not silently fall back to the first hub.

**Acceptance criteria.**
- For a link `connected_hubs=["hub_account","hub_customer"]`, `driving_key=["hub_customer"]`, the
  generated eff_sat has `src_dfk = "CUSTOMER_HK"` and `src_sfk = ["ACCOUNT_HK"]`.
- Reordering `connected_hubs` does not change `src_dfk` as long as `driving_key` is unchanged.
- A multi-hub driving key (`driving_key=["hub_a","hub_b"]`) renders `src_dfk = ["A_HK","B_HK"]`.
- Empty `driving_key` at generation → no SQL emitted, an error appended to `state.errors`.

**Test changes (also fixes L-5).** Replace the current
`test_effectivity_satellite_generates_on_link`, which hardcodes the bug
(`src_dfk = "ACCOUNT_HK"  # driving = first connected hub`). New tests:
- model declares `driving_key=["hub_customer"]` on the link → assert `src_dfk = "CUSTOMER_HK"`,
  `src_sfk = ["ACCOUNT_HK"]`.
- a reordered-hubs variant proving order-independence.
- a multi-hub driving key variant.
- empty driving key → flagged, not generated.

---

## H-2 — Invalid heavy-model identifier in config

**Severity:** Medium (blocks real modeler runs). **Files:** `src/vault_agent/config.py`,
`tests/` (new lightweight test), optionally `.env.example`.

**Problem.** `heavy_model: str = "claude-opus-4-6"` is not a valid model string; the `Dv2ModelerAgent`
uses `settings.heavy_model` by default, so a real run of the hardest reasoning step fails with a
model-not-found error. `primary_model = "claude-sonnet-4-6"` is valid.

**Intended behaviour.** Set `heavy_model` to a current, valid Claude model identifier. **Verify the
exact string against the Anthropic API / docs before committing** — do not trust a value from memory.
Keep the Sonnet-default / heavy-on-demand split (ADR-0001 stands; only the string is wrong).

**Acceptance criteria.**
- `Settings().heavy_model` and `.primary_model` are both valid current identifiers (verified).
- A test asserts both fields are non-empty and match the expected `claude-…` pattern (a cheap guard
  against regressions; it does not call the network).
- `.env.example` (if present/added) documents both, plus `ANTHROPIC_API_KEY`.

**Note.** No ADR change: ADR-0001 records the *policy* ("Sonnet default, Opus for hardest cases"),
which is unchanged. This is purely a config correction.

---

## M-1 — Multi-format requirements input (PDF / DOCX), not just text

**Severity:** Medium (feature gap vs. documented design). **Files:**
`src/vault_agent/agents/requirements_parser.py`, `pyproject.toml` (add `python-docx`),
`tests/test_agents/test_requirements_parser.py`, `2-multi-agent-design.md` (already lists a "PDF
Reader" tool — implementation just catches up to the design).

**Problem.** `_read_document` does `path.read_text(...)` only. `pypdf` is a dependency but unused; a
PDF or DOCX is read as garbage. Real-world requirements documents commonly arrive as `.docx`/`.pdf`
rather than plain text, so the parser must handle them.

**Intended behaviour.** A small dispatch-by-extension reader inside the Requirements Parser:
- `.md`, `.txt` → `read_text` (current path).
- `.pdf` → extract text via `pypdf` (already a dependency).
- `.docx` → extract text via `python-docx` (new dependency).
- unknown extension → append a clear `state.errors` entry and skip (don't crash the pipeline).
Keep extraction in a single private helper so it stays unit-testable without the LLM. Update the CLI
`run` argument help to reflect the supported formats.

**Acceptance criteria.**
- A `.pdf` and a `.docx` fixture each yield non-empty extracted text routed into the extractor.
- An unsupported extension produces a `state.errors` entry and is skipped, pipeline continues.
- Existing `.md`/`.txt` behaviour unchanged.

**Test changes.** Add fixtures under `tests/fixtures/` (a tiny generated PDF and DOCX) and tests that
the reader returns text for each; the LLM extractor stays stubbed.

---

## M-2 — Ground the model in `source_schemas` instead of prose only

**Severity:** Medium (roadmap; core value for real DWH use). **Files:** `state.py` (already has
`source_schemas`), a new grounding step, `business_key_identifier.py` and/or `dv2_modeler.py`,
prompts, tests. **Recommend a candidate ADR** because it adds a pipeline stage.

**Problem.** `VaultAgentState.source_schemas` is declared but consumed by no agent. Business keys and
satellite attributes are invented from requirement prose, never checked against real source columns.
The multi-agent design already assigns the Business-Key Identifier a "Schema Inspector / Data
Profiler" tool — unimplemented.

**Intended behaviour (phased).**
- **Phase 1 [ENFORCE-lite]:** when `source_schemas` is non-empty, validate that proposed business
  keys and satellite attributes reference columns that actually exist in the declared schema; flag
  unknowns as warnings (`W_BK_NOT_IN_SOURCE`, `W_ATTR_NOT_IN_SOURCE`) rather than failing — the
  schema may be incomplete. When `source_schemas` is empty, behave exactly as today (no regression).
- **Phase 2 [GUIDE]:** feed the relevant schema slice into the business-key and modeler prompts so
  candidate keys/attributes are drawn from real columns.

**Acceptance criteria.**
- With an empty `source_schemas`, output is byte-for-byte unchanged from today (regression guard).
- With a populated schema, a business key not present in any source table raises the new warning and
  is surfaced in `state.errors`/validation, not silently accepted.
- Decide and document the `source_schemas` format (e.g. a list of `{table, columns:[…]}` JSON/YAML);
  capture it in the candidate ADR.

**Deliverable:** draft `docs/architecture/adrs/ADR-0004-source-schema-grounding.md` (status Proposed)
describing the schema format and where grounding sits in the graph, before coding Phase 1.

---

## L-1 — Decouple the retry cap from the audit log

**Severity:** Low (maintainability). **Files:** `state.py`, `graph.py`,
`src/vault_agent/agents/dv2_modeler.py`, `tests/test_graph.py`.

**Problem.** `route_after_validation` counts `decisions` entries with `agent == "dv2_modeler"` to
enforce `MAX_MODELING_ATTEMPTS`. Control flow is coupled to logging — change how the modeler logs and
the loop guard breaks silently.

**Intended behaviour.** Add an explicit `modeling_attempts: int = 0` to `VaultAgentState`; the modeler
increments it each run; `route_after_validation` reads that field. Keep `decisions` for the audit
trail only.

**Acceptance criteria.**
- The cap is enforced via `state.modeling_attempts`, not by counting `decisions`.
- Existing graph tests (`test_failing_validation_loops_back…`, `test_persistent_failure_stops_at_retry_cap`)
  pass against the new counter; update them to assert on `modeling_attempts` where they currently
  count modeler decisions.

---

## L-2 — Detect column-name collisions in `_to_column`

**Severity:** Low. **Files:** `code_generator.py`, `tests/test_agents/test_code_generator.py`.

**Problem.** `_to_column` maps `[^0-9a-zA-Z]+ → _` and uppercases; `"customer-id"` and
`"customer id"` both become `CUSTOMER_ID`. Two distinct labels can silently collide in a payload /
key list.

**Intended behaviour.** When two distinct source labels within one construct's column set normalise
to the same identifier, append a warning to `state.errors` (e.g. `code_generator: column-name
collision in <construct>: 'customer-id' and 'customer id' both map to CUSTOMER_ID`). Generation may
continue; the point is visibility.

**Acceptance criteria.** A satellite/link whose attributes contain two colliding labels produces a
collision warning naming both originals and the collapsed identifier.

---

## L-3 — Lazy settings access so importing `config` never crashes

**Severity:** Low. **Files:** `src/vault_agent/config.py` and its importers.

**Problem.** `settings = Settings()` runs at import time and requires `ANTHROPIC_API_KEY` with no
default. The "no API key needed for construction/tests" property only holds because `config` is
imported lazily inside each extractor's `__init__`. A direct `import vault_agent.config` without the
key crashes hard.

**Intended behaviour.** Replace the module-level singleton with a cached accessor
`get_settings()` (e.g. `functools.lru_cache`) that constructs `Settings()` on first use. Update the
three extractor `__init__`s to call `get_settings()`. This preserves lazy behaviour while making the
failure mode explicit and import-safe.

**Acceptance criteria.**
- `import vault_agent.config` succeeds with no env var set.
- Constructing a real extractor without `ANTHROPIC_API_KEY` raises a clear, attributable error.
- All existing tests still run without an API key.

---

## L-4 — Don't accumulate draft ADR fragments across retries

**Severity:** Low. **Files:** `src/vault_agent/agents/dv2_modeler.py`.

**Problem.** The modeler appends a draft ADR fragment to `state.adrs` on every pass. On the happy
path `adr_author` overwrites with `state.adrs = [adr]`; but if the retry cap is hit and the graph
routes to `END`, N stale fragments remain in `state.adrs`.

**Intended behaviour.** The modeler should not accumulate: either replace its own draft each pass
(keep at most one draft fragment) or stop emitting a draft fragment and let `adr_author` be the sole
writer. Prefer the latter — the finalized ADR already renders everything from `state.dv_model`.

**Acceptance criteria.** After an exhausted-retry run that ends without `adr_author`, `state.adrs`
holds at most one entry. A happy-path run is unchanged (single finalized ADR).

---

## L-5 — Fix the test that freezes the H-1 bug

Folded into **H-1** (see its Test changes). Tracked here so it isn't lost: the current
`test_effectivity_satellite_generates_on_link` asserts the wrong `src_dfk` and must be rewritten as
part of H-1, not left green.

---

## Rollout order

1. **H-1** + **L-5** — driving-key application and its corrected tests (biggest correctness risk).
2. **H-2** — valid heavy-model string (unblocks real modeler runs); verify against the API.
3. **L-3** — `get_settings()` (small, de-risks every later change and direct imports).
4. **L-1** — explicit `modeling_attempts` counter.
5. **L-4** — stop accumulating draft ADRs.
6. **L-2** — column-collision warning.
7. **M-1** — multi-format requirements reader (+ `python-docx`, fixtures).
8. **M-2** — `source_schemas` grounding: draft ADR-0004 first, then Phase 1 validation, then
   Phase 2 prompt grounding.

After each item: `ruff check`, `mypy --strict`, `pytest`. Keep every deterministic test runnable
without an API key.

## Traceability

| Finding | Spec section | Canonical spec touched | New ADR? |
|---|---|---|---|
| H-1 | above | dv2-modeling-rules-spec.md §2 (done) | no |
| H-2 | above | — | no |
| M-1 | above | (2-multi-agent-design already lists PDF Reader) | no |
| M-2 | above | — | **ADR-0004 (proposed)** |
| L-1…L-5 | above | — | no |
