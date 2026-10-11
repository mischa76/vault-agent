---
type: spec
status: not-measured
updated: 2026-10-11
---

# WP68 — Workbench console: explanations from the state, no model call

Status: **Approved and in progress** (2026-10-11, user: „go, bau WP68“; ADR-0014 §4 phase 1,
WP65 §2 „Chat“) · Owner: Mischa Eismann · Author: Claude. The right pane's console answers
questions about a run from its state, the gate and flag catalogues, the steering registry and
the CLI's own help — deterministically. No agent, gate or prompt changes; the suite stays
keyless. The LLM assistant remains a later phase with its own ADR.

## 1 Scope

A command grammar over the paused or finished run (`vault_agent.ui.console`, one endpoint
`POST /api/runs/{id}/console {text}`), a transcript in the right pane under the event stream,
and the two catalogues the explanations need, in code: `rules/catalogue.py` — `GATES`
(every validator code with its one-line meaning) and `FLAGS` (every `FlagKind` with its
meaning). Chapter 8 stays the manual; the catalogue is the product's own short answer.

## 2 The rules

1. **Deterministic, and nothing changes.** The console reads state and catalogues and
   returns text; it never resumes, decides, writes or calls a model. A „what if“ answer
   names the CLI command it *would* be and says that nothing ran.
2. **A grammar, not a parser of messages.** Commands: `help`, `status`, `items
   [decisions|disclosures]`, `explain <n|asset|code|flag>`, `why <construct>`,
   `show <construct>`, `gates`, `gate <CODE>`, `flags`, `steering [id]`, `cli`,
   `what if accept|discard|owner <asset>=<Name <email>>|resolve <concept>=<answer>`. Free
   text that equals a construct name, a code, a flag kind or an item's asset is routed to
   the matching command; anything else answers with `help`. Nothing branches on a
   human-readable message; item numbers are positions in the checkpoint's queue.
3. **The code owns the catalogue.** `GATES` has exactly the codes the validator emits,
   `FLAGS` exactly the `FlagKind` members; chapter 8's table names every gate. Guards hold
   all three. The steering answer reads `active_modeling_rules()` (id, text, backstop,
   origin); the CLI answers read the `resume` command's own option help through click.
4. **Explanations cite their source** — the item's kind and role (WP43), the gate's code,
   the flag's kind and reason, the issue's remedy and what it retires, the attempt — and
   point to the perspective where the thing is (`refs`), so the frontend can offer a jump.
5. **The frontend keeps the transcript per run in memory** (not in the run directory: a
   console exchange is not an artefact); the answer is rendered as text.

## 3 Guards before the change

1. `rules.catalogue.GATES` keys equal the `E_`/`W_` codes in `validator.py`; `FLAGS` keys
   equal `FlagKind`'s values; chapter 8's catalogue rows name every gate code.
2. On the stub agents, paused: `items` lists the owner decision numbered; `explain 1`
   names the contract, the kind, the role and `--owner`; `status` says paused and the
   attempts; `what if accept` returns `vault-agent resume --out … --accept` and leaves the run
   paused (`pending.json` still there); `gate E_DUP_HUB` returns the catalogue line; an
   unknown text answers with the help and kind `unknown`.
3. On a constructed state (a hub with a satellite and a link, one issue with a remedy and
   one flag on the hub): `show hub_x` names its key, source entity, satellite and link;
   `why hub_x` lists the issue with its code, remedy and attempt and the flag with its
   kind; `steering` names a rule id with its origin; `flags` counts the flag.
4. A finished run whose state this session does not hold answers kind `unavailable`
   without an exception.

## 4 Pre-registration

The keyless browser walk (WP67's `walk.mjs`) extended by three console exchanges on the
paused run — `items`, `explain 1`, `what if accept` — with the answer visible in the transcript
and the run still paused afterwards. No paid run: the console calls no model, so the real-key
case adds nothing the stub does not show.

## 5 Not in this WP

An LLM over the state (own ADR, own cost line); free-form natural language; console
history on disk; explaining the *input* (requirements text) — the state carries parsed
requirements, and `show` could reach them in a later increment.

## 6 Results

*(appended after the change)*

**2026-10-11 — built and walked keyless.** Spec and guards `fabdd0a` (red), the backend
`335ffba`, the frontend and docs in the commit carrying this line. `rules/catalogue.py`: 46
gate lines and 25 flag lines, guarded against the validator's source, `FlagKind` and chapter
8's table (all three agree today). `ui/console.py`: the grammar of §2.2 over
`assemble_review_queue`, the validation report, the flags, the retirements, the model and
`active_modeling_rules()`; the `what if` answers read the `resume` command's option help
through click. The frontend's console sits under the event stream with a per-run transcript
in memory and the answer's jumps as buttons. Four Python guards, two Vitest tests (13 in all).
**§4:** the keyless walk with the three exchanges on the paused run — `items` listed the
owner decision as item 1, `explain 1` named the contract, kind, role and `--owner`, `what if
accept` named `vault-agent resume --out … --accept` — and the run was still paused after them
(the checkpoint button still there), then accepted and finished as in WP67. No paid run, as
pre-registered. **Not measured:** `why`/`show` in the browser on a real model (unit-tested on
a constructed state); a brownfield run's `resolve` what-if.
