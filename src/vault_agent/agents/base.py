"""Base class for all agents."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from vault_agent.state import VaultAgentState


class BaseAgent(ABC):
    """All agents inherit from this. Each owns a state field it reads/writes.

    ``prompt_path`` (relative to ``src/vault_agent/prompts/``) is declared only by the
    LLM-calling agents; the deterministic agents leave it ``None`` — they own no prompt
    file, and calling :meth:`load_prompt` on one is a programming error.
    """

    prompt_path: ClassVar[str | None] = None

    @abstractmethod
    async def run(self, state: VaultAgentState) -> VaultAgentState:
        """Read what the agent needs from state, write what it owns."""
        ...

    def load_prompt(self) -> str:
        if self.prompt_path is None:
            raise RuntimeError(
                f"{type(self).__name__} is deterministic and declares no prompt_path; "
                "load_prompt() must not be called on it"
            )
        prompts_dir = Path(__file__).parent.parent / "prompts"
        return (prompts_dir / self.prompt_path).read_text(encoding="utf-8")
