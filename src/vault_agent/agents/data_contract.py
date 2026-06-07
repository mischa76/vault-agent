"""data contract agent – to be implemented."""
from vault_agent.agents.base import BaseAgent
from vault_agent.state import VaultAgentState


class DataContractAgent(BaseAgent):
    prompt_path = "data_contract.md"  # type: ignore[assignment]

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        raise NotImplementedError("Implement in W1-W3")
