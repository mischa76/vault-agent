"""Tests for the agent base class (WP5 §5.2): prompt_path is optional and typed."""
import pytest

from vault_agent.agents.adr_author import AdrAuthorAgent
from vault_agent.agents.base import BaseAgent
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.agents.orchestrator import HumanCheckpointAgent, OrchestratorAgent
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import VaultAgentState


class _Deterministic(BaseAgent):
    """A prompt-less agent, like the validator or code generator."""

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        return state


def test_load_prompt_without_prompt_path_raises_naming_the_agent() -> None:
    with pytest.raises(RuntimeError, match="_Deterministic"):
        _Deterministic().load_prompt()


def test_deterministic_agents_declare_no_prompt() -> None:
    for cls in (
        ValidatorAgent, CodeGeneratorAgent, AdrAuthorAgent,
        OrchestratorAgent, HumanCheckpointAgent,
    ):
        assert cls.prompt_path is None, cls.__name__


def test_llm_agents_load_their_prompts() -> None:
    # One representative: the declared file exists and loads.
    assert "modeler" in Dv2ModelerAgent().load_prompt().lower()
