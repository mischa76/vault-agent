"""Shared pytest fixtures."""
import pytest

from vault_agent.state import VaultAgentState


@pytest.fixture
def empty_state() -> VaultAgentState:
    return VaultAgentState()
