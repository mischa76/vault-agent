"""WP5 §5.4: the library logs via module loggers but never configures logging."""
import logging

import pytest

from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import VaultAgentState


def test_library_configures_no_handlers() -> None:
    # Importing the package (conftest already imported the world) must leave the
    # vault_agent logger hierarchy unconfigured: silent by default, the CLI opts in.
    assert logging.getLogger("vault_agent").handlers == []
    assert logging.getLogger("vault_agent").level == logging.NOTSET


async def test_agent_run_logs_info_at_stage_boundary(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="vault_agent"):
        await ValidatorAgent().run(VaultAgentState())
    messages = [record.getMessage() for record in caplog.records]
    assert any("validating model" in message for message in messages)
    assert any("validation failed" in message for message in messages)  # empty model: E_NO_HUBS
