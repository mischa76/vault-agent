# Contributing to vault-agent

Thanks for taking the time. This project has a few conventions that are unusual enough to be
worth stating up front — they exist because of specific things that went wrong, and each one is
traceable to an entry in [`docs/log.md`](docs/log.md).

MIT licensed. By contributing you agree your work ships under the same terms.

## Getting set up

```bash
uv sync --extra dev          # Python 3.12+; add --extra eval or --extra demo as needed
uv run pytest                # must pass with NO Anthropic API key set
```

The suite is **keyless by design**. Every LLM call sits behind an injectable seam, and the
deterministic core of each agent is tested without a key. If your change makes the suite need an
API key, the change is wrong, not the suite.

## Definition of done

Three commands, all green, before you open a PR:

```bash
uv run pytest
uv run ruff check .
uv run mypy                  # bare — see below
```

**Never pass a path to mypy.** An explicit path overrides `pyproject.toml`'s
`files = ["src/vault_agent", "eval"]`, which silently skips `eval/` — the code the quality gates
lean on. CI runs the bare form on purpose; your local check should be the same statement.

Then one entry in [`docs/log.md`](docs/log.md). See "Writing things down" below.

## Read these three before a substantial change

1. [`CLAUDE.md`](CLAUDE.md) — the invariants. Twelve rules in trigger/action/evidence form. Most
   of them exist because someone did the opposite once and it cost a build, a run, or wrong data.
2. [`docs/index.md`](docs/index.md) — the catalogue. Everything else is one hop from there.
3. The relevant ADR. Decisions are recorded in `docs/architecture/adrs/`; if your change argues
   against one, that is a new ADR, not a quiet edit.

## Conventions that will come up

**Data Vault rules live in `src/vault_agent/rules/`, never in a prompt.** Prompts steer; rules
are the source of truth. Anything a validator gate or generator needs to know goes in `rules/`,
behind a named helper — and every call site asks that helper rather than re-deriving its answer.

**A gate refuses, a backstop repairs.** A deterministic `E_` gate blocks before generation and
feeds the re-model loop; a backstop silently fixes model output and emits telemetry so we can
tell whether it is still needed. New prompt steering is registered in the steering registry and
recorded in [`docs/architecture/steering-ledger.md`](docs/architecture/steering-ledger.md) with
its evidence — otherwise nobody can answer "does the next model still need this?".

**Branch on typed fields, never on message text.** `FlagKind`, `ValidationIssue.code`, the
confidence category. Substring matching over human-readable messages has produced real bugs here.

**Verify against the installed library, not from memory.** If you use a macro, signature or flag
of AutomateDV, LangGraph, dbt or the Anthropic SDK, read the installed package first and cite
what you read in the PR. A macro name that does not exist looks perfectly plausible in review.

**Write the guard before the change.** If a change must leave existing output untouched, commit
the byte-identity fixture first, then change. Deliberately updating a fixture is fine — same
commit, reason in the message. Several fixtures exist for exactly this
(`tests/fixtures/staging_ungrounded_baseline/`, `tests/fixtures/steering/`, the greenfield
inertness manifest).

**No new framework without an ADR**, and don't bypass AutomateDV by hand-writing dbt models.

## Say what you verified

The most valuable habit in this repo, and the one most often skipped. Distinguish:

- **verified-live** — it ran end to end against the real thing (a real Anthropic API call, a real
  PostgreSQL build). Name the evidence: `dbt build --full-refresh` PASS counts, the trace file,
  the eval scores.
- **keyless-only** — covered by the offline suite, never run against the real API.
- **not-measured** — you believe it works and did not check.

A PR that says "keyless-only" is welcome. A PR that implies live verification it did not do is
the problem. If you change a **rendered dbt template**, the honest evidence is a real Postgres
build; `demo/bank_postgres/` and `demo/mapping_postgres/` exist so you do not have to invent one.

Live runs cost real money. Before paying for another one, read the traces under
`.vault-agent/traces/` and the stored results in `eval/results/` — three ~$5 runs once found
serially what a single trace audit already contained.

## Writing things down

Knowledge routing, in one line each — the full procedure is in
[`.claude/skills/project-docs/SKILL.md`](.claude/skills/project-docs/SKILL.md):

| Kind of fact | Where it goes |
|---|---|
| An agent would silently do the wrong thing without it | an invariant in `CLAUDE.md` (200-line budget; needs an incident and, at budget, an eviction) |
| True only inside one subsystem | `.claude/rules/<topic>.md` with a `paths:` glob |
| A decision with alternatives and consequences | a new ADR |
| Work to be done | a spec plus kick-off under `docs/architecture/backlog-2026-07/` |
| Everything else — and this is most things | an entry in `docs/log.md` |

**`docs/architecture/` and `docs/log.md` are append-only.** ADRs, specs, kick-offs, reviews and
log entries are dated records; their value depends on showing what was believed when. Never
revise one — not to fix a claim, not to tidy prose. A new dated entry does that. A test
(`tests/test_log_completeness.py`) enforces that log entries are not lost.

## Pull requests

- Branch off `main`; PRs run the CI job above.
- Commit subjects follow `type(scope): summary` — `feat(wp30)`, `fix(wp33)`, `docs(scale)`,
  `perf(data_contract)`. The body is where the reasoning goes: what was wrong before, what you
  deliberately did not do, what is verified and how.
- The PR template asks a handful of questions. They are the same ones a reviewer would ask; an
  honest "no" is a fine answer to most of them.

## About the `.claude/` directory

`.claude/rules/` and `.claude/skills/` ship with the repo. They configure Claude Code, and they
are plain markdown — if you use a different tool, or none, they are simply documentation and you
can ignore the tooling aspect. **The conventions they encode are not optional; the tool that
reads them is.** `.claude/settings.local.json` and anything else in `.claude/` stays untracked.
