# 15 Handover: what leaves an engagement, and what stays (WP92, ADR-0015)

vault-agent is the consultant's own tool, run inside an engagement (ADR-0015, accepted 2026-10-26
— Option C: a team tool with logins and a shared checkpointer is a later ADR of its own, opened
when a customer asks to run it themselves). This chapter says what that means at the end of an
engagement: which files the customer receives, which stay with the consultant, how a project
root travels between machines, and what the record inside it does and does not prove.

## 15.1 The project root is the engagement

Everything a run produced lives under the workbench's `--root` (14.2): one folder per project with
`project.json`, `inputs/` (the requirement documents, schema and profiling files the customer
supplied) and `runs/<stamp>/` (one folder per run, the CLI's `--out`). A CLI run without the
workbench has the same `--out` folder, minus the project wrapper. Keep the root **outside the
repository** and treat it as the customer's material from the first run on: it holds their
requirements, their schema and the model made from them (10.7).

## 15.2 What the customer receives

Hand over the run folder's deliverables, not the run folder. A run's `--out` folder *is* the dbt
project (6.4): `dbt_project.yml` and `packages.yml` at its top, `models/`, `metadata/`, and beside
them the documents the run wrote. From `runs/<stamp>/`:

| Hand over | What it is | Chapter |
|---|---|---|
| `dbt_project.yml`, `packages.yml`, `README.md`, `models/`, `metadata/` | The dbt project: staging and raw vault, the construct metadata, the logical model, and `metadata/source_catalogue.yml` with the bindings and aliases that made it build | 6.4, 9.1, 9.3 |
| `contracts/` | One data contract per source asset, with the derived dbt tests | 6.4 |
| `review-queue.md`, `mappings.review.yml` | Every decision taken at the checkpoint with the owner named for it; the ratified business-to-source mapping | 7 |
| `adrs/` | The model ADR the run proposed, finalised by the architect | 6.4 |
| `report.html` | The self-contained run report with the model graph | 6.4 |
| The edited mapping and profiling files, if any | The human's answers that bound the model to the sources | 7, 9.3 |

The generated project is self-contained since WP74/WP76: it parses and builds on its own, with
the catalogue it carries (14.7). The customer puts it in their git; from then on their commit
history, not the run folder, says who changed what.

## 15.3 What stays with the consultant

- `.vault-agent/` inside every run folder (10.6): `checkpoints.sqlite`, `pending.json`, the LLM
  traces. The traces hold the prompts and the model's answers, which contain the
  customer's requirements verbatim — they are the engagement's working papers, kept or deleted
  under the engagement's terms, never shipped as part of the project.
- `.env` and the key it holds (5.1). The key is the consultant's, or the customer's for the
  engagement's duration; it is never in the root.
- The workbench itself. It listens on `127.0.0.1` only and has no option to change that (pinned by
  `tests/test_wp92_relocatable_root.py`); customer staff take part at the checkpoints in a joint
  session, on the consultant's screen or a workstation the customer provides, not through logins of
  their own. On a server without a browser the consultant reaches it through an SSH tunnel (14.1).

## 15.4 The root travels whole

A root can be copied or moved — to another path, another disk, another machine — and opened
there with `vault-agent ui --root <new path>` from any working directory. The workbench locates a
run by its place under the root (`<root>/<project>/runs/<stamp>`), never by the `out_dir` the
run's `run.json` recorded at start; that field, and the `cli_equivalents` next to it, are a record
of what was run where, and the API reports the current location. A paused run stays decidable
after the move, a finished one stays readable (model, artefacts, report, console). Nothing inside
a run folder is rewritten by the move.

What does not travel is the key (15.3) and the Python environment: the new machine needs the same
installation (4) and, to build the project, the warehouse extras (9).

## 15.5 Residency per engagement

Which route the run's model calls took — Anthropic directly, Bedrock in an AWS region, Vertex in a
Google Cloud region — is the engagement's decision, made before the first run and recorded in the
run's summary and traces (`llm route`, 5.5). The route is chosen per engagement, not per customer
login, because there is one operator. The vendor-questionnaire answers for a class-1 context are
in `docs/architecture/deployment-residency.md`.

## 15.6 What the record proves, and what it does not

The checkpoint records an owner per decision as the name the operator typed (`Name <email>`,
7). That is an assertion, not an authenticated identity — ADR-0015's neutral consequence. The
review queue says who was *named*; the customer's git history of the handed-over project says who
*committed*. An engagement that needs decisions attributable to authenticated identities needs
the team tool, and therefore ADR-0015's follow-up ADR, not a stricter form of this chapter.
