"""Tests for the import-guarded LangSmith layer (WP6 layer 4).

Keyless and package-independent: a fake ``langsmith`` module is injected into
``sys.modules``, and absence of the package is simulated the same way — the default
suite must pass whether or not the ``eval`` extra is installed."""
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from eval.datasets import EvalCase, GoldenModel
from eval.langsmith_upload import (
    dataset_name,
    ensure_dataset,
    make_client,
    upload_run_results,
)
from eval.scorers import ScorerResult
from vault_agent.config import Settings


def _settings(langsmith_api_key: str | None) -> Settings:
    return Settings(anthropic_api_key="sk-ant-test", langsmith_api_key=langsmith_api_key)


def _case() -> EvalCase:
    return EvalCase(name="bank", input_document="unused.md", golden=GoldenModel())


class _FakeClient:
    """Records every LangSmith call the upload layer makes."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.datasets: dict[str, Any] = {}
        self.examples: list[dict[str, Any]] = []
        self.runs: list[dict[str, Any]] = []
        self.feedback: list[dict[str, Any]] = []

    def has_dataset(self, dataset_name: str) -> bool:
        return dataset_name in self.datasets

    def read_dataset(self, dataset_name: str) -> Any:
        return self.datasets[dataset_name]

    def create_dataset(self, dataset_name: str, description: str) -> Any:
        dataset = SimpleNamespace(id=f"id-{dataset_name}", name=dataset_name)
        self.datasets[dataset_name] = dataset
        return dataset

    def create_example(self, **kwargs: Any) -> None:
        self.examples.append(kwargs)

    def create_run(self, **kwargs: Any) -> None:
        self.runs.append(kwargs)

    def create_feedback(self, run_id: Any, key: str, score: float, comment: str) -> None:
        self.feedback.append({"run_id": run_id, "key": key, "score": score})


def test_make_client_without_key_is_disabled() -> None:
    assert make_client(_settings(None)) is None


def test_make_client_without_package_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # None in sys.modules makes `import langsmith` raise ImportError — exactly the
    # behaviour when the `eval` extra is not installed.
    monkeypatch.setitem(sys.modules, "langsmith", None)
    assert make_client(_settings("ls-key")) is None


def test_make_client_with_key_and_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "langsmith", SimpleNamespace(Client=_FakeClient))
    client = make_client(_settings("ls-key"))
    assert isinstance(client, _FakeClient)
    assert client.api_key == "ls-key"


def test_ensure_dataset_creates_once_with_golden_example() -> None:
    client = _FakeClient("k")
    case = _case()
    ensure_dataset(client, case)
    ensure_dataset(client, case)  # second call must not duplicate
    assert list(client.datasets) == [dataset_name(case)] == ["vault-agent-eval-bank"]
    (example,) = client.examples
    assert example["outputs"] == {"golden": case.golden.model_dump()}


def test_upload_run_results_logs_runs_and_feedback() -> None:
    client = _FakeClient("k")
    runs = [
        [ScorerResult(name="construct_f1", score=1.0, details="d")],
        [ScorerResult(name="construct_f1", score=0.5, details="d")],
    ]
    upload_run_results(
        client, _case(), runs, models={"primary_model": "m"}, git_sha="abc1234"
    )
    assert len(client.runs) == 2
    assert client.runs[0]["name"] == "eval:bank:run1"
    assert client.runs[0]["outputs"] == {"construct_f1": 1.0}
    assert client.runs[0]["extra"]["metadata"]["git_sha"] == "abc1234"
    assert [fb["score"] for fb in client.feedback] == [1.0, 0.5]
