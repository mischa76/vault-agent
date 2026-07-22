# Vault-Agent Operations Manual

The complete guide to installing, configuring, running, and maintaining vault-agent —
written for the **operator / data architect**: someone who runs the pipeline, judges its
outputs, answers the human-in-the-loop checkpoint, and ships the generated Data Vault to
a warehouse. It refreshes the Data Vault 2.0 vocabulary where needed but is not a DV2.0
textbook, and it explains code internals only where they matter for operations
(checkpoints, traces, gates).

## Contents

| # | Chapter | Covers |
|---|---------|--------|
| 1 | [Introduction](01-introduction.md) | What vault-agent is and isn't; how to read this manual |
| 2 | [Concepts & terminology](02-concepts.md) | DV2.0 primer, pipeline vocabulary, error constellations by example |
| 3 | [Architecture](03-architecture.md) | Components, pipeline topology, state & persistence |
| 4 | [Installation & setup](04-installation.md) | Prerequisites, uv, extras, API key, warehouse prerequisites |
| 5 | [Configuration reference](05-configuration.md) | All settings and environment variables, model tiers |
| 6 | [Running the pipeline](06-running.md) | CLI reference for `run`/`resume`, inputs, output anatomy |
| 7 | [The HITL checkpoint](07-hitl-checkpoint.md) | Review queue, interactive prompt, ratification workflows |
| 8 | [Validation gates reference](08-validation-gates.md) | Every E_/W_ code: meaning, cause, typical fix |
| 9 | [From output to warehouse](09-warehouse.md) | dbt workflow, source binding, incremental behaviour, demos |
| 10 | [Observability & debugging](10-observability.md) | `--debug`, LLM traces, `.vault-agent/` internals |
| 11 | [Evaluation & release operations](11-evaluation.md) | Eval harness, gates, ablation, model-release protocol |
| 12 | [Troubleshooting & FAQ](12-troubleshooting.md) | Common failure modes, exit codes |
| 13 | [Glossary](13-glossary.md) | Short definitions, linked from all chapters |

## Conventions

- Diagrams are Mermaid (rendered natively by GitHub). Where a diagram and prose
  disagree, treat both as suspect and check the code.
- Counted facts (number of gates, number of tests) drift; where this manual states a
  count it names the reference point. The code is the source of truth — count the
  codes, don't trust prose.
- Shell examples assume the repo root as working directory and a POSIX shell.
