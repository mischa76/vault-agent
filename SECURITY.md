# Security policy

## Reporting a vulnerability

Please report security issues privately to **me@eismann.consulting** — not via public
GitHub issues. Include what you found, where (file/component), and how to reproduce it.
I'm a solo maintainer: expect an acknowledgement within a few days and an honest
assessment of severity and timeline; credit is given in the fix's release notes unless
you prefer otherwise.

## Supported versions

The project is in active pre-1.0 development; only the current `main` branch is
supported. There are no backported fixes.

## Scope notes

Reports I'm particularly interested in:

- **Prompt-injection paths**: a crafted requirements document, source schema, or
  profiling file steering the LLM agents into unsafe output. The deterministic
  validator gates and human checkpoint are the designed mitigations — findings that
  bypass *both* are high-severity.
- **Generated-code issues**: generated dbt/AutomateDV output that could execute
  unintended SQL against the target warehouse.
- Classic dependency or CI issues (the lockfile and workflows are in-repo).

One caution for reproduction material: run traces (`.vault-agent/traces/`) contain the
full input documents and source metadata. Never attach traces from real data to a
report — reproduce with the shipped synthetic examples under `examples/inputs/`.
