"""Minimal entry point: feed a single requirement, print the parsed result.

Will work after the Requirements Parser agent is implemented (W1-W3).
"""
from vault_agent.state import VaultAgentState


def main() -> None:
    state = VaultAgentState(input_documents=["examples/inputs/bank_account_requirements.md"])
    print("Loaded state:", state.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
