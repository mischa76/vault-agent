# WP5 — Hygiene batch: renderers, dead code, logging, checkpoint pruning, doc drift

Status: Proposed · Size: M · Depends on: —

Bundle of small, independent cleanups (project review 2026-07-06, findings 6/7 + item 9).
Each sub-item is separately committable; do them in the order listed.

## 5.1 Merge the checkpoint renderers

`cli.py::_CHECKPOINT_HEADINGS/_CHECKPOINT_ORDER/_print_checkpoint` duplicate
`orchestrator.py::_KIND_HEADINGS/_KIND_ORDER/render_review_queue_md`'s presentation
knowledge. Move the shared constants to the orchestrator module (single owner of
review-queue presentation), export them (`KIND_HEADINGS`, `KIND_ORDER` — public names),
and have `cli._print_checkpoint` import them. Rendering functions stay where they are
(markdown in orchestrator, rich-console in cli) — only the *knowledge* is deduplicated.
Add a test asserting both renderers cover exactly the same kinds in the same order.

## 5.2 Dead prompts and the optional prompt_path

The four deterministic agents (validator, orchestrator/checkpoint, code_generator,
adr_author) declare `prompt_path` files that are never loaded. Fix the type instead of
shipping dead files:

- `agents/base.py`: `prompt_path: ClassVar[str | None] = None`; `load_prompt()` raises
  `RuntimeError` naming the agent when called with `None`.
- Deterministic agents: remove the `prompt_path` line (and the `# type: ignore` with it).
  LLM agents: plain `prompt_path = "requirements_parser.md"` etc. — the `ClassVar`
  annotation removes all nine `# type: ignore[assignment]`.
- Delete `src/vault_agent/prompts/{validator,orchestrator,code_generator,adr_author}.md`
  after `rg`-confirming nothing references them.
- Delete the empty `src/vault_agent/tools/` package. CLAUDE.md's "Tools are MCP-style"
  convention line gets a "(directory reintroduced when the first tool lands)" note.

## 5.3 Unused dependencies and settings

- `jinja2`: `rg -l jinja2 src tests` — if (as of review) unused, remove from
  `pyproject.toml`. Do NOT switch the generator to jinja2 in this WP.
- `config.py`: remove `langsmith_*` fields only if WP6 has not landed/started — otherwise
  leave them (WP6 consumes them). Remove `log_level` in favour of §5.4's approach.

## 5.4 Logging + `--debug`

There is no logging in src; the CLI's blanket `except Exception` hides stack traces.

- Std-lib `logging`, logger per module (`logging.getLogger(__name__)`); no config in
  library code (no handlers/levels set outside the CLI — library stays silent by default).
- Sprinkle INFO logs at stage boundaries (each agent's `run` entry with construct counts)
  and DEBUG for payload sizes. No secrets, no full prompts at INFO.
- CLI: global `--debug` option → `logging.basicConfig(level=DEBUG)` + on pipeline failure
  re-raise with full traceback (`console.print_exception()` or plain `raise`) instead of
  the one-line message. Default behaviour unchanged.

## 5.5 Checkpoint pruning

`<out>/.vault-agent/checkpoints.sqlite` grows unboundedly (every run a new thread).
After a run **finalises** (not paused): delete that thread's checkpoints via the saver's
delete API (`AsyncSqliteSaver.adelete_thread(thread_id)` — verify the current
langgraph-checkpoint-sqlite API name first) in `cli.run`/`cli.resume` where
`_clear_pending` is called today. Paused runs keep their thread (needed for resume).
Test: after a completed keyless run (stub extractors, MemorySaver won't do here — use the
sqlite saver against `tmp_path`), the thread's checkpoints are gone while a paused run's
remain.

## 5.6 Documentation drift

- CLAUDE.md: "The validator has 10 independent gates" → replace with the actual current
  issue-code count (count `E_`/`W_` codes in `validator.py` at implementation time;
  after WP1 there are more) — or better, drop the number: "independent E_/W_ gates".
- `orchestrator.py::HumanCheckpointAgent` docstring + CLAUDE.md claim "interrupt() is the
  node's first statement": false (queue assembly precedes it — safe because pure). Reword
  both to: "everything before interrupt() must stay pure/idempotent because the node
  re-executes from the top on resume; assemble_review_queue is pure."
- `prompts/orchestrator.md` (if kept for the checkpoint agent — it is deleted in §5.2;
  fold anything still useful into module docstrings).

## Acceptance criteria

1. One source of truth for checkpoint presentation; parity test in place.
2. Zero `# type: ignore[assignment]` on `prompt_path`; dead prompt files and `tools/`
   gone; `pyproject.toml` carries no unused deps.
3. `vault-agent run --debug` prints full tracebacks; default output unchanged.
4. Finalised runs leave no checkpoint rows; paused runs still resumable (test).
5. CLAUDE.md/docstrings carry no stale claims listed above. Standard DoD.
