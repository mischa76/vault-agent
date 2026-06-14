"""Base class for all agents."""
from abc import ABC, abstractmethod
from pathlib import Path

from vault_agent.state import VaultAgentState


class BaseAgent(ABC):
    """All agents inherit from this. Each owns a prompt file and a state field."""

    prompt_path: Path  # relative to src/vault_agent/prompts/

    @abstractmethod
    async def run(self, state: VaultAgentState) -> VaultAgentState:
        """Read what the agent needs from state, write what it owns."""
        ...

    def load_prompt(self) -> str:
        prompts_dir = Path(__file__).parent.parent / "prompts"
        return (prompts_dir / self.prompt_path).read_text(encoding="utf-8")
