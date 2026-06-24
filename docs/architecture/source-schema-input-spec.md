# Spec — Source-schema input (Phase 1): feed `source_schemas`, activate grounding

> **Purpose.** Close the "declared but unfed" gap: give the pipeline a way to **supply a source
> schema** (declared YAML/JSON) so the **already-built** ADR-0004 grounding actually runs. This is
> the *producer* half — the consumers exist. Implementation-ready for Claude Code; `[ENFORCE]`/
> `[GUIDE]` discipline.
>
> **Author of spec:** review pass, 2026-06-17. **Implements:** Claude Code.
> **Builds on:** [ADR-0004](./adrs/ADR-0004-source-schema-grounding.md),
> [ADR-0007](./adrs/ADR-0007-automation-scope-by-layer.md),
> [how-requirements-become-a-model.md](../how-requirements-become-a-model.md).

## How to use this in Claude Code

Small, additive, **fully inert when no schema is supplied** (no regression). Keep `ruff`/`mypy`/
`pytest` green; deterministic — no API key. **Phase 1 only**: this wires a producer to the existing
grounding. It does **not** change Raw-Vault naming, add a mapping, or generate staging (Phase 2/3 —
see §8).

Definition of done: `vault-agent run <doc> --source-schema <file.yml>` populates
`state.source_schemas`; the validator's `W_BK_NOT_IN_SOURCE` / `W_ATTR_NOT_IN_SOURCE` warnings,
the prompt grounding, and the per-table contracts all activate; with no flag, output is unchanged.

---

## 0. Context & scope

**Consumers already exist (ADR-0004) — do not rebuild them:**

- `state.source_schemas: list[SourceTable]` (`SourceTable{table, columns}`) in `state.py`.
- `grounding.py`: `known_columns`, `is_grounded`, `render_schema_prompt_section`.
- `validator._check_source_grounding`: emits `W_BK_NOT_IN_SOURCE` / `W_ATTR_NOT_IN_SOURCE`
  (warnings; only when `source_schemas` is non-empty).
- `dv2_modeler._build_system_prompt` and `business_key_identifier` inject the schema into prompts.
- `data_contract._assets`: one contract per source table when a schema is present.
- `orchestrator`: `ExecutionPlan.grounded = bool(state.source_schemas)`.

**Missing — the producer (this spec):** nothing populates `source_schemas`. The CLI builds
`VaultAgentState(input_documents=[...])` only, so via the CLI grounding is always inert.

**In scope:** a declared **YAML/JSON** loader + a `--source-schema` CLI flag that fills
`state.source_schemas`. **Out of scope (Phase 2/3, §8):** source-dialect naming, business↔source
mapping, staging generation, DDL parsing, live DB introspection.

---

## 1. Schema file format [ENFORCE]

A declared file (YAML or JSON — `yaml.safe_load` parses both). Canonical shape mirrors ADR-0004:

```yaml
source_schemas:
  - table: customer
    columns: [national_customer_id, bank_customer_reference, customer_name, date_of_birth]
  - table: account
    columns: [account_number, balance, status]
  - table: account_customer
    columns: [account_number, national_customer_id, effective_from, effective_to]
```

- Top-level key `source_schemas:` → a list of `{table: str, columns: [str, ...]}`.
- Also accept a **bare top-level list** of the same objects (convenience).
- Each entry validates into the existing `SourceTable` model. Column names are stored **as written**
  (grounding normalises both sides via `normalize_identifier`, so case/punctuation don't matter).

---

## 2. Loader [ENFORCE]

New module `src/vault_agent/source_schema.py` (loading is I/O — keep it separate from `grounding.py`,
which is matching):

```python
def load_source_schemas(path: Path) -> list[SourceTable]: ...
```

- Read the file, `yaml.safe_load` it, accept either the `source_schemas:` key or a bare list.
- Validate each entry into `SourceTable` (pydantic). On a malformed entry raise a **clear,
  attributable `ValueError`** naming the file and the problem (the CLI turns it into a clean exit —
  §3); do not silently drop, since a bad schema is a user error worth surfacing.
- Missing file → `FileNotFoundError` (CLI surfaces it). Empty/`null` document → empty list (treated
  as "no schema": inert).
- Type-clean under `mypy --strict`; `yaml` is typed now that `types-PyYAML` is a dev dep.

---

## 3. CLI integration [ENFORCE]

Add to `vault-agent run` (in `cli.py`):

- A new option `--source-schema` / `-s` (`Path | None = None`, `exists=True, dir_okay=False`) —
  help: "Optional declared source schema (YAML/JSON) to ground keys/attributes against."
- When provided, call `load_source_schemas` and pass the result into `_run_pipeline`, which sets it
  on the initial state: `VaultAgentState(input_documents=[...], source_schemas=schemas)`.
- Wrap loader errors like the existing CLI error handling (`console.print` + `raise typer.Exit(1)`).
- `resume` needs no flag: `source_schemas` was set at run time and is persisted in the checkpoint.

Surface it in `_print_summary`: add a line, e.g.
`grounding:     on (N source table(s))` when `state.source_schemas`, else `off`. The grounding
*warnings* already flow into the human-checkpoint output and `review-queue.md` as
`validation_warning` items — no extra wiring needed.

---

## 4. Example file [GUIDE]

Add `examples/inputs/bank_source_schema.yml` — a faithful schema for the bank toy domain (the
columns of the `raw_*` seeds), so the demo command works:

```bash
vault-agent run examples/inputs/bank_account_requirements.md \
  --source-schema examples/inputs/bank_source_schema.yml --out output
```

A faithful schema means grounding passes cleanly (`grounded: on`, no spurious warnings); to *see*
grounding bite, a reviewer can drop or rename a column and re-run — document this one-liner in the
example or the demo notes. (Deterministic proof that a missing column warns lives in the tests, §5,
not in the LLM run.)

---

## 5. Tests [ENFORCE]

- **Loader** (`tests/test_source_schema.py`): a YAML fixture and a JSON fixture each load into the
  expected `list[SourceTable]`; the bare-list form works; a malformed entry raises a clear
  `ValueError`; a missing key / empty doc yields `[]`.
- **Grounding activation** (extend `tests/test_agents/test_validator.py` if not already covered):
  with a populated `source_schemas`, a business key / attribute absent from it produces
  `W_BK_NOT_IN_SOURCE` / `W_ATTR_NOT_IN_SOURCE`; with empty `source_schemas`, neither fires
  (regression guard — this likely already exists; keep it green).
- **CLI** (`tests/test_cli.py`): `run --help` lists `--source-schema`; loading a sample file sets
  `state.source_schemas` (test the loader + state wiring; the graph can stay stubbed).
- All without an API key.

---

## 6. Acceptance criteria [ENFORCE]

- `vault-agent run <doc> --source-schema <file>` runs; `state.plan.grounded` is true and the summary
  shows grounding on.
- A key/attribute not in the declared schema surfaces as a `W_*_NOT_IN_SOURCE` warning in the
  checkpoint and `review-queue.md` (warnings — **non-blocking**, per ADR-0004).
- With a populated schema, contracts are emitted **one per source table** (existing `data_contract`
  behaviour).
- **No regression:** without `--source-schema`, `source_schemas` is empty and every output is
  byte-for-byte as today.

---

## 7. Docs to update [ENFORCE]

- `README.md` Quick start: document the `--source-schema` flag with the bank example. (The intro
  already says "optionally grounding against a supplied source schema" — now it's real.)
- `docs/how-requirements-become-a-model.md`: update the status table — `source_schemas` is now
  **fed** by a declared-file producer (grounding no longer inert); the naming/two-input target
  (Phase 2) remains future.
- `CLAUDE.md` current-milestone: one line that the source-schema producer (declared YAML/JSON) now
  activates ADR-0004 grounding.
- Optional: an amendment note on `ADR-0004` that the "Schema Inspector / Data Profiler" future tool
  now has a first, minimal producer (declared file); DB introspection remains future.

---

## 8. Out of scope — later phases (do NOT build here)

- **Phase 2 — source-dialect naming + mapping:** name Stage/Raw Vault from the source schema (not
  the prose) with an agent-proposed, human-confirmed business↔source mapping (the decided target in
  `how-requirements-become-a-model.md`).
- **Phase 3 — staging generator:** emit the `stg_*` layer automatically (PoC Finding #1).
- **Richer inputs:** DDL parsing (`CREATE TABLE`), live DB introspection (`information_schema`).

Keep Phase 1 minimal so it ships and de-risks the rest.

## Rollout order

1. Loader module + tests (§2, §5).
2. CLI flag + state wiring + summary line (§3) + CLI test.
3. Example schema file (§4).
4. Docs (§7).

After each: `ruff` / `mypy --strict` / `pytest` green; confirm the no-flag path is unchanged.
