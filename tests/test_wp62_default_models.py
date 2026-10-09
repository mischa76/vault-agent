"""WP62 — the default models are Sonnet 5.5 and Opus 5.5; the review record is per modeler
model (spec §3). Committed before the change, failing."""
from __future__ import annotations

import pytest

from eval.wp34_check import REVIEW_DECISION_SAMPLES, check
from tests.test_wp34_check import _chain
from vault_agent.config import Settings


def test_the_defaults_are_the_5_5_models_in_auto_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    for name in ("PRIMARY_MODEL", "HEAVY_MODEL", "FORCED_TOOL_CHOICE"):
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert (s.primary_model, s.heavy_model) == ("claude-sonnet-5-5", "claude-opus-5-5")
    assert s.forced_tool_choice is False


def test_the_review_record_is_per_modeler_model(monkeypatch: pytest.MonkeyPatch) -> None:
    assert set(REVIEW_DECISION_SAMPLES) >= {"claude-opus-4-8", "claude-opus-5-5"}
    assert len(REVIEW_DECISION_SAMPLES["claude-opus-4-8"]) == 11
    # The 5.5 record starts with the fourteenth chain (2026-10-09): nothing before WP63 is a sample.
    record_55 = REVIEW_DECISION_SAMPLES["claude-opus-5-5"]
    assert all(stamp >= "20261009T213238859667Z" for stamp, _ in record_55)

    old = _chain(review_decisions=140)
    old["models"] = {"heavy_model": "claude-opus-4-8", "primary_model": "claude-sonnet-4-6"}
    held, lines = check(old)
    [line] = [ln for ln in lines if "review:" in ln]
    assert held and "11 recorded chain(s)" in line

    # A model whose record is still empty cannot be judged (the 5.5 record was, until the
    # sixteenth chain on 2026-10-10; the guard pins the rule with an emptied record).
    from eval import wp34_check
    monkeypatch.setattr(wp34_check, "REVIEW_DECISION_SAMPLES",
                        {**REVIEW_DECISION_SAMPLES, "claude-opus-5-5": ()})
    new = _chain(review_decisions=140)
    new["models"] = {"heavy_model": "claude-opus-5-5", "primary_model": "claude-sonnet-5-5"}
    held, lines = check(new)
    [line] = [ln for ln in lines if "review:" in ln]
    assert not held and "cannot be judged" in line

    unnamed = _chain(review_decisions=140)  # an archived result without models: the 4.8 record
    held, lines = check(unnamed)
    [line] = [ln for ln in lines if "review:" in ln]
    assert held and "11 recorded chain(s)" in line
