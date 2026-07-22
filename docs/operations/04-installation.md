# 4. Installation & setup

## 4.1 Prerequisites

You need **Python 3.12+**, **git**, and **[uv](https://docs.astral.sh/uv/)** (the
project's dependency manager — pip works in principle, but every documented command
assumes uv). For building generated output on a warehouse (chapter 9) you additionally
need a local **PostgreSQL 16** or access to another AutomateDV-supported platform; dbt
itself is installed as a project extra, not globally.

On **Windows 11**, `scripts/install/` in the repo installs the whole stack — WSL2 +
Ubuntu, uv, PostgreSQL, the repo, and a keyless smoke test — from one elevated
PowerShell script; on an existing Ubuntu/Debian machine its second stage runs
standalone. It also pulls in `jq` for the trace-reading recipes (10.3) — a convenience,
not a requirement: nothing in the pipeline uses it, and that chapter carries a
stdlib-Python fallback for environments where installing tools is not permitted.

If you install manually under WSL, keep the repo and virtualenv on the Linux filesystem
(ext4), not under `/mnt/c` — NTFS round-trips make everything (tests, uv, git)
painfully slow.

## 4.2 Installing

```bash
git clone https://github.com/mischa76/vault-agent.git
cd vault-agent
uv sync
```

`uv sync` creates the virtualenv and installs the core package plus dev tooling. Two
optional extras exist and are needed only for what their names say:

```bash
uv sync --extra demo    # dbt-core + dbt-postgres (~1.9) — for chapter 9 builds
uv sync --extra eval    # langsmith — ONLY for the optional eval upload (11.5)
```

The CLI entry point is `vault-agent` (run through `uv run vault-agent …` or activate
the venv). The eval harness has no entry point by design; it runs as
`uv run python -m eval.run` (chapter 11).

## 4.3 API key & .env

The pipeline needs `ANTHROPIC_API_KEY`:

```bash
cp .env.example .env    # then add your ANTHROPIC_API_KEY
```

Settings load from the environment with `.env` as fallback (chapter 5). The key is
required *lazily*: importing or constructing anything never needs it — a clear
validation error is raised only at the first real LLM call site. Unknown or stale
variables in `.env` are ignored, never fatal.

What works **without** a key: the entire test suite, ruff, mypy, both Postgres demos
(their build scripts are deterministic), `vault-agent --help`, and the eval scorer
layer. What needs a key: `vault-agent run`/`resume` (the five LLM agents) and live
eval runs.

## 4.4 Verifying the installation

```bash
uv run pytest             # keyless — no API key, no network
uv run ruff check .
uv run mypy
uv run vault-agent --help
```

All four must pass on a fresh clone (the suite is in the 400+ range and grows;
the exact count is whatever CI pins). For an end-to-end sanity check without spending
tokens, build the bank demo (9.5): it feeds a fixed model through the real code
generator and, with `--extra demo` plus a local Postgres, `dbt build` runs green.

## 4.5 Warehouse prerequisites (optional)

For chapter 9 you need a Postgres 16 database and role the demos can use, and a
`profiles.yml` for dbt — the generated output's README documents the expected profile
shape per run. AutomateDV is pinned (`packages.yml` is generated with the verified
version); `dbt deps` fetches it into the output project, so nothing AutomateDV-related
is installed globally. Platform notes beyond Postgres: 9.6.
