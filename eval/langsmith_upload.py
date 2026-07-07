"""Optional LangSmith layer (wp6-eval-harness-spec.md §6) — import-guarded.

When ``settings.langsmith_api_key`` is set *and* the ``langsmith`` package (the ``eval``
optional-dependency extra) is importable, the live runner (a) creates/updates one
LangSmith dataset per eval case and (b) logs each live run with its scores as feedback.
Absence of the key or the package changes nothing: :func:`make_client` returns ``None``
and the runner skips the upload.

The ``langsmith`` import happens lazily inside :func:`_import_langsmith`, never at module
import time, so importing this module (and everything that imports it) stays safe without
the extra installed. Pipeline tracing itself (``LANGCHAIN_TRACING_V2``) is documented in
``eval/README.md`` and deliberately not code-enforced.
"""
import importlib
from typing import Any
from uuid import uuid4

from eval.datasets import EvalCase
from eval.scorers import ScorerResult
from vault_agent.config import Settings

# LangSmith dataset name per eval case; also the searchable link between golden case and
# logged runs in the LangSmith UI.
DATASET_PREFIX = "vault-agent-eval-"


def _import_langsmith() -> Any | None:
    """The guarded import: the module, or ``None`` when the extra is not installed."""
    try:
        return importlib.import_module("langsmith")
    except ImportError:
        return None


def make_client(settings: Settings) -> Any | None:
    """A ``langsmith.Client`` when key + package are present, else ``None`` (disabled)."""
    if not settings.langsmith_api_key:
        return None
    module = _import_langsmith()
    if module is None:
        return None
    return module.Client(api_key=settings.langsmith_api_key)


def dataset_name(case: EvalCase) -> str:
    return f"{DATASET_PREFIX}{case.name}"


def ensure_dataset(client: Any, case: EvalCase) -> Any:
    """Create the case's LangSmith dataset if missing (with one golden example); return it."""
    name = dataset_name(case)
    if client.has_dataset(dataset_name=name):
        return client.read_dataset(dataset_name=name)
    dataset = client.create_dataset(
        dataset_name=name,
        description=f"vault-agent golden eval case '{case.name}' (WP6 eval harness)",
    )
    client.create_example(
        inputs={
            "input_document": str(case.input_document),
            "source_schema": str(case.source_schema) if case.source_schema else None,
        },
        outputs={"golden": case.golden.model_dump()},
        dataset_id=dataset.id,
    )
    return dataset


def upload_run_results(
    client: Any,
    case: EvalCase,
    runs: list[list[ScorerResult]],
    *,
    models: dict[str, str],
    git_sha: str,
) -> None:
    """Log each live run as a LangSmith run with one feedback entry per scorer."""
    ensure_dataset(client, case)
    for index, results in enumerate(runs, start=1):
        run_id = uuid4()
        client.create_run(
            id=run_id,
            name=f"eval:{case.name}:run{index}",
            run_type="chain",
            inputs={"input_document": str(case.input_document), "run": index},
            outputs={result.name: result.score for result in results},
            extra={"metadata": {"git_sha": git_sha, **models, "dataset": dataset_name(case)}},
        )
        for result in results:
            client.create_feedback(
                run_id, key=result.name, score=result.score, comment=result.details
            )
