"""WP82 §2.7 — the guard that holds the CLI's options against the API's request models, in both
directions: a CLI option without a row here fails, and so does an API field no option reaches.
Committed before the change, failing (`profiling`, `target_platform`, `bind`, `mappings`)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import typer.main

from vault_agent import cli
from vault_agent.rules.platforms import TargetPlatform
from vault_agent.ui.app import Decision, StartRun

PROCESS = "process"  # the option steers the process (where, whether, how to write), not the run

# `vault-agent run` → StartRun. A value names the API field (or alias); PROCESS names an exception.
RUN = {
    "input_doc": "requirements",
    "source_schema": "schema",
    "profiling": "profiling",
    "existing": "existing_run",
    "target_platform": "target_platform",
    "pit": "pit",
    "as_of_start": "as_of_start",
    "as_of_end": "as_of_end",
    "as_of_grain": "as_of_grain",
    # WP113: the run's model route — per run on the CLI, per project (or per run) in the workbench
    "primary_model": "primary_model",
    "heavy_model": "heavy_model",
    "anthropic_base_url": "anthropic_base_url",
    "naming_profile": "naming",  # WP114: a file on the CLI, the profile object in the body
    "out": PROCESS,
    "write": PROCESS,
    "trace": PROCESS,
    "interactive": PROCESS,
}

# `vault-agent resume` → Decision. A file option maps to the dict(s) its content becomes.
RESUME = {
    "owner": ("owners",),
    "accept": ("accept",),
    "mappings": ("mappings", "mapping_sources"),
    "map_": ("mappings",),
    "resolutions": ("resolutions",),
    "resolve": ("resolutions",),
    "link": ("links",),
    "no_link": ("links",),
    "bind": ("bindings",),
    "discard": ("discard",),
    "out": PROCESS,
    "write": PROCESS,
    "trace": PROCESS,
    "interactive": PROCESS,
}


def _params(command: str) -> set[str]:
    return {p.name for p in typer.main.get_command(cli.app).commands[command].params if p.name}


def _api_names(model: type) -> set[str]:
    return {info.alias or name for name, info in model.model_fields.items()}


def test_every_run_option_has_a_row_and_every_startrun_field_is_reached() -> None:
    assert _params("run") == set(RUN), "a new `run` option: add it to StartRun or name it PROCESS"
    mapped = {v for v in RUN.values() if v != PROCESS}
    assert mapped <= _api_names(StartRun), mapped - _api_names(StartRun)
    assert _api_names(StartRun) <= mapped, "an API field no CLI option reaches"


def test_every_resume_option_has_a_row_and_every_decision_field_is_reached() -> None:
    assert _params("resume") == set(RESUME), (
        "a new `resume` option: add it to Decision or name it PROCESS"
    )
    mapped = {f for v in RESUME.values() if v != PROCESS for f in v}
    assert mapped <= _api_names(Decision), mapped - _api_names(Decision)
    assert _api_names(Decision) <= mapped, "an API field no CLI option reaches"


def test_the_cli_decision_payload_and_the_api_model_name_the_same_keys() -> None:
    """`discard` ends a run instead of deciding it; everything else is one payload."""
    assert set(cli._build_decision([], False)) == set(Decision.model_fields) - {"discard"}


def test_the_workbench_offers_exactly_the_platforms_the_code_knows() -> None:
    source = (Path(__file__).parent.parent / "frontend" / "src" / "types.ts").read_text()
    match = re.search(r"export const PLATFORMS = \[([^\]]*)\]", source)
    assert match, "frontend/src/types.ts: PLATFORMS missing"
    offered = re.findall(r'"([a-z]+)"', match.group(1))
    assert offered == list(get_args(TargetPlatform))
