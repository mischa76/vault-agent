"""Sanity tests for the shared state model."""
from vault_agent.state import VaultAgentState


def test_state_initializes_empty() -> None:
    state = VaultAgentState()
    assert state.requirements == []
    assert state.dv_model.hubs == []
    assert state.validation_report.passed is False
