"""Validator agent.

Deterministically checks the logical Data Vault model in ``VaultAgentState.dv_model`` (and,
if the code generator has already run, the generated artifacts) against the DV2.0 rules in
``vault_agent.rules.dv2_rules``. No LLM is involved, so validation is reproducible and runs
in CI without an API key. It is an independent gate: it re-checks structural invariants the
modeler and generator already enforce, giving defense in depth across agents.

Results land in ``VaultAgentState.validation_report`` as a list of issue dicts
(``severity`` / ``code`` / ``construct`` / ``message``); ``passed`` is true when there are
no error-severity issues.
"""
from typing import Any

from vault_agent.agents.base import BaseAgent
from vault_agent.rules.dv2_rules import (
    REQUIRED_HUB_COLUMNS,
    REQUIRED_LINK_COLUMNS,
    REQUIRED_SAT_COLUMNS,
)
from vault_agent.state import ValidationReport, VaultAgentState

# Maps the logical DV column names in the rules to the AutomateDV metadata keys the code
# generator emits, so the required-column rules can be checked against the artifacts.
_LOGICAL_TO_META = {
    "hash_key": "src_pk",
    "business_key": "src_nk",
    "load_date_time": "src_ldts",
    "record_source": "src_source",
    "hash_diff": "src_hashdiff",
}
_REQUIRED_COLUMNS = {
    ("hubs", "hub"): REQUIRED_HUB_COLUMNS,
    ("links", "link"): REQUIRED_LINK_COLUMNS,
    ("satellites", "satellite"): REQUIRED_SAT_COLUMNS,
}


def _issue(severity: str, code: str, construct: str, message: str) -> dict[str, Any]:
    return {"severity": severity, "code": code, "construct": construct, "message": message}


class ValidatorAgent(BaseAgent):
    """Validates the Data Vault model and generated artifacts against DV2.0 rules."""

    prompt_path = "validator.md"  # type: ignore[assignment]

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        model = state.dv_model
        issues: list[dict[str, Any]] = []

        hub_names = {hub.name for hub in model.hubs}
        link_names = {link.name for link in model.links}

        if not model.hubs:
            issues.append(
                _issue("error", "E_NO_HUBS", "dv_model", "model has no hubs; nothing to validate")
            )

        all_names = (
            [hub.name for hub in model.hubs]
            + [link.name for link in model.links]
            + [sat.name for sat in model.satellites]
        )
        for name in sorted({n for n in all_names if all_names.count(n) > 1}):
            issues.append(
                _issue("error", "E_DUP_NAME", name, f"construct name {name!r} is not unique")
            )

        for hub in model.hubs:
            if not hub.business_key.strip():
                issues.append(
                    _issue("error", "E_HUB_NO_BK", hub.name, "hub has no business key")
                )
            if not any(sat.parent == hub.name for sat in model.satellites):
                issues.append(
                    _issue(
                        "warning", "W_HUB_NO_SAT", hub.name,
                        "hub has no satellite; no descriptive data is captured for it",
                    )
                )

        for link in model.links:
            if len(link.connected_hubs) < 2:
                issues.append(
                    _issue(
                        "error", "E_LINK_TOO_FEW_HUBS", link.name,
                        f"link connects {len(link.connected_hubs)} hub(s); needs >= 2",
                    )
                )
            unknown = [h for h in link.connected_hubs if h not in hub_names]
            if unknown:
                issues.append(
                    _issue(
                        "error", "E_LINK_UNKNOWN_HUB", link.name,
                        f"link references unknown hubs: {unknown}",
                    )
                )

        valid_parents = hub_names | link_names
        for sat in model.satellites:
            if sat.parent not in valid_parents:
                issues.append(
                    _issue(
                        "error", "E_SAT_UNKNOWN_PARENT", sat.name,
                        f"satellite parent {sat.parent!r} is not a known hub or link",
                    )
                )
            if not sat.attributes:
                issues.append(
                    _issue(
                        "error", "E_SAT_NO_PAYLOAD", sat.name,
                        "satellite has no attributes (empty payload)",
                    )
                )

        issues.extend(self._check_artifact_columns(state.artifacts.automatedv_yaml))

        errors = [issue for issue in issues if issue["severity"] == "error"]
        state.validation_report = ValidationReport(passed=not errors, issues=issues)
        state.decisions.append(
            {
                "agent": "validator",
                "passed": not errors,
                "errors": len(errors),
                "warnings": len(issues) - len(errors),
            }
        )
        return state

    @staticmethod
    def _check_artifact_columns(metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """Check each generated construct carries every DV-required column (if generated)."""
        issues: list[dict[str, Any]] = []
        for (section, kind), required in _REQUIRED_COLUMNS.items():
            for name, meta in metadata.get(section, {}).items():
                for logical in required:
                    key = _LOGICAL_TO_META[logical]
                    if not meta.get(key):
                        issues.append(
                            _issue(
                                "error", "E_MISSING_COLUMN", name,
                                f"generated {kind} is missing required column "
                                f"{logical!r} (metadata key {key!r})",
                            )
                        )
        return issues
