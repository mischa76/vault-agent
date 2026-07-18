# WP12 — Interactive checkpoint prompt (UI track stage 1.5)

Status: Proposed · Size: S/M · Depends on: nothing new (ADR-0006 interrupt/resume, WP9
mapping ratification — all landed). Complements WP11; no file overlap with it beyond the
CLI summary lines.

## 1. Problem & positioning

When a run pauses at the HITL checkpoint today, the CLI prints the review queue and
resume *instructions* — the human must re-type `vault-agent resume --owner "asset=Name
<email>" --map "concept=TABLE.COLUMN" --accept` by hand. That round-trip is pure
friction: the process that knows the pending items just exited. The milestone notes have
carried "an interactive resume prompt" as a planned item since the HITL loop closed.

This is **stage 1.5 of the UI track**: interactivity *in the terminal*, no server, no
new framework. It strengthens the CLI-first invariant (WP11 §1) rather than competing
with it — stage 2's web UI then only ever has to be *nicer*, never *necessary*.

**Capability parity rule (the §1 invariant, applied):** the prompt may only offer what
the `resume` flags already offer — owner assignment, single-source mapping ratification,
accept. It is ergonomics over the same `apply_human_decision` path, never a new
capability. Anything the prompt cannot express (today: multi-source `sources:`
resolution, WP10 §2.4) falls back to the file-based flow, stated in the prompt.

## 2. Behaviour

- `run` (and `resume` invoked with **no** decision options) gains
  `--interactive/--no-interactive`, default **auto**: interactive only when
  `sys.stdin.isatty() and sys.stdout.isatty()`. Non-TTY (CI, pipes, tests) keeps
  today's print-and-exit behaviour **byte-identical** — scriptability is the invariant.
- On pause, after `_print_summary`/`_report_paused` context is shown, the interactive
  loop walks the *actionable* blocking/pending items:
  1. Per contract with a placeholder owner (matched via `ContractOwner.PLACEHOLDER_NAME`,
     never message text): prompt `Owner for contract 'X' (Name <email>, Enter to skip):`
     — parsed by the existing `_parse_owner`; invalid input re-prompts with the error.
  2. Per unresolved mapping concept (`state.mappings.unresolved`): show the proposal's
     candidate evidence lines, prompt for `TABLE.COLUMN` (Enter to skip) — parsed by the
     existing `_parse_map` right-hand side. Multi-source keys are listed but deferred to
     `resume --mappings` (see parity rule).
  3. Final gate: `Accept and finalize? [y/N]` — mirrors `--accept` exactly; validation
     errors are shown before the question (they are not fixable interactively; whether
     accept proceeds past them follows today's `resume --accept` semantics, unchanged).
- Confirmed input is assembled by the existing `_build_decision` and resumed
  **in-process** via `_resume_pipeline(out, thread_id, decision)` — the checkpointer
  thread already exists; no new machinery. A run that pauses again (possible) re-enters
  the loop.
- Skip-everything / decline-accept / Ctrl-C: exactly today's exit — `pending.json` kept,
  resume instructions printed. Aborting must never lose the checkpoint.
- `resume` invoked *with* decision flags behaves exactly as today (flags win; no prompt).

## 3. Implementation notes

- `cli.py` only (+ tests). Prompting via `rich.prompt.Prompt`/`Confirm` on the existing
  `Console`; the prompt function is **injectable** (module-level seam, monkeypatched in
  tests) so the whole flow is keyless-testable without a real TTY.
- No business logic: the loop only *collects strings* and hands them to the existing
  parse/build/resume functions. Decision semantics live in `apply_human_decision`,
  untouched.
- TTY detection in one small helper (`_is_interactive(default: bool | None)`) so the
  flag's auto/force-on/force-off logic is unit-testable.

## 4. Tests (keyless)

- **Non-TTY regression**: with a non-TTY stdin (default in pytest), `run` on a pausing
  state produces byte-identical console output to today (pin the paused-path output).
- **Parity**: an interactive session answering owner + mapping + accept assembles the
  *same decision dict* as the equivalent `resume --owner … --map … --accept` invocation
  (assert on `_build_decision` input equality, both paths).
- **Abort safety**: declining accept (and simulated Ctrl-C) leaves `pending.json` and the
  checkpointer thread intact; a subsequent flag-based `resume` still works.
- **Invalid input re-prompt**: a malformed owner spec re-prompts, then a valid one lands.
- **Multi-source deferral**: a multi-candidate key is listed with the file-based pointer
  and not promptable.
- **Flag matrix**: `--interactive` forces the prompt on non-TTY (for demos/tmux edge
  cases); `--no-interactive` suppresses it on a TTY.

## 5. Acceptance criteria

1. A paused bank run in a real terminal can be taken to finalized entirely through the
   prompt (owner + accept), producing the same artifacts as the flag-based resume
   (byte-identical outputs given the same inputs).
2. CI/scripted invocations are provably unaffected (non-TTY regression pin green).
3. Every prompt capability has a flag-based equivalent (parity test green) — nothing
   becomes interactive-only.
4. Full suite + ruff + mypy strict green; no new dependency (rich is already a typer
   dependency in use).
