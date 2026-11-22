"""Eval harness for the vault-agent pipeline (WP6).

Three strictly separated layers (wp6-eval-harness-spec.md §2):

1. ``eval/datasets/`` + :mod:`eval.datasets` — golden datasets and their typed loader
   (keyless, unit-tested).
2. :mod:`eval.scorers` — deterministic, pure scoring functions (keyless, unit-tested).
3. :mod:`eval.run` — the live runner (real LLM calls; requires ``ANTHROPIC_API_KEY``;
   never part of the default test suite). :mod:`eval.langsmith_upload` optionally pushes
   datasets/runs to LangSmith and is import-guarded.
"""
