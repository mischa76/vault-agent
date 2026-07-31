---
paths:
  - "src/vault_agent/agents/**/*.py"
  - "src/vault_agent/llm.py"
  - "src/vault_agent/prompts/**/*.md"
---

# Agent conventions

- **One agent per file**, prompt as a sibling `.md` in `prompts/`, loaded via `prompt_path`.
  A deterministic agent has no prompt and `load_prompt()` raises if you give it one.
- **Every model call goes through `ForcedToolCaller`** (`llm.py`): forced single tool, streaming,
  cache-controlled system block, the shared retry matrix, usage and trace recorders.
  Do not call the SDK directly from an agent — `grep messages.create src/vault_agent` must stay
  empty (ADR-0010).
- **The LLM part is injectable.** Deterministic core in the agent, model call behind a seam the
  tests replace. The suite runs with no API key.
- **A truncated response is a typed failure**, not an empty payload: `LLMCallError.truncated`.
  List-shaped output splits via `llm.call_with_truncation_split` with a domain merge; a single
  coherent artefact has only the budget lever.
- **Never guess a value the input does not carry.** Flag it: `state.flag(...)` with a `FlagKind`
  and the asset. An honest gap is output; an invented column is a defect. Consumers branch on
  `kind`/`asset`, never on the message text.
- **Prompt steering is registered**, not inlined: `DV_MODELING_RULES` entries carry an id, origin
  and backstop link, and the ledger (`docs/architecture/steering-ledger.md`) records the
  evidence. Adding or deleting a rule regenerates
  `tests/fixtures/steering/modeler_rules_pre_wp16.txt` in the same commit, with the pre-WP16
  block asserted to remain a byte-identical prefix.
- **DV2.0 knowledge lives in `rules/`**, not in a prompt and not at a call site. If you need a
  hub's staging key column, a satellite's feed or its payload relations, a role-qualified column
  or a normalised identifier, call the helper.
- Log at agent boundaries (INFO, with construct counts), payload sizes at DEBUG. The library
  never configures handlers or levels.
