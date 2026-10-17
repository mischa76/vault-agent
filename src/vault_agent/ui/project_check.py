"""WP78 — does a run's written project resolve, and does dbt parse it?

Two answers, both keyless and without a warehouse. The deterministic one reads the written
project the way the eval harness does (`unresolved_stage_refs`, WP74) plus the staging metadata
for the inferred bindings — what a human must still provide. The second runs `dbt parse` on
request, when dbt and an adapter are in this process's environment, with a throwaway profile
whose connection values are placeholders: `dbt parse` opens no connection. The subprocess runner
is injectable so the suite covers the path without dbt. Nothing here gates or changes a run.
"""
from __future__ import annotations

import importlib.util
import json
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Protocol

import yaml

from vault_agent.agents.staging_generator import unresolved_stage_refs

PROFILE_NAME = "vault_project"  # the generated dbt_project.yml's `profile:`
MAX_ERROR_LINES = 20

# Placeholder connection values per adapter: enough for `dbt parse`, never connected.
_PROFILES: dict[str, dict[str, Any]] = {
    "postgres": {"type": "postgres", "host": "localhost", "port": 5432, "user": "parse",
                 "password": "parse", "dbname": "parse", "schema": "parse", "threads": 1},
    "databricks": {"type": "databricks", "host": "parse.invalid", "http_path": "/sql/1.0/parse",
                   "token": "parse", "catalog": "parse", "schema": "parse", "threads": 1},
}


class CommandRunner(Protocol):
    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]: ...


def run_command(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """The default runner: a subprocess with captured text output."""
    return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)  # noqa: S603


def dbt_available() -> dict[str, str] | None:
    """`{"version", "adapter"}` when dbt-core and one of the known adapters import here, else
    None. Read from the installed packages, never from a remembered extra."""
    if importlib.util.find_spec("dbt") is None:
        return None
    try:
        from dbt.version import __version__ as version
    except Exception:  # noqa: BLE001 - any import failure means "not usable here"
        return None
    for adapter in ("postgres", "databricks"):
        if importlib.util.find_spec(f"dbt.adapters.{adapter}") is not None:
            return {"version": str(version), "adapter": adapter}
    return None


def _staging_metadata(out_dir: Path) -> dict[str, Any]:
    path = out_dir / "metadata" / "automatedv.yml"
    if not path.is_file():
        return {}
    document: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    staging = document.get("staging") if isinstance(document, dict) else None
    return staging if isinstance(staging, dict) else {}


def project_check(out_dir: Path) -> dict[str, Any]:
    """The deterministic answer for a written project: staging models, the stages dbt could not
    resolve (`unresolved_stage_refs`), the stages whose binding is inferred (the staging
    metadata's `source_binding`), dbt's availability and the last parse result, if persisted."""
    staging_dir = out_dir / "models" / "staging"
    # Recursive: an operator may lay the views out in sub-folders (a per-folder `+schema` for
    # a quota, as the Databricks builds did); dbt resolves by model name, not by folder.
    models = {
        p.stem: p.read_text(encoding="utf-8") for p in sorted(staging_dir.rglob("*.sql"))
    } if staging_dir.is_dir() else {}
    sources = staging_dir / "sources.yml"
    sources_yml = sources.read_text(encoding="utf-8") if sources.is_file() else ""
    unresolved = unresolved_stage_refs(models, sources_yml) if models else []
    inferred = sorted(
        name for name, meta in _staging_metadata(out_dir).items()
        if isinstance(meta, dict) and meta.get("source_binding") == "inferred"
    )
    return {
        "staging_models": len(models),
        "unresolved": unresolved,
        "inferred": inferred,
        "dbt": dbt_available(),
        "parse": _last_parse(out_dir),
    }


def _last_parse(out_dir: Path) -> dict[str, Any] | None:
    meta = out_dir / "run.json"
    if not meta.is_file():
        return None
    data: Any = json.loads(meta.read_text(encoding="utf-8"))
    parse = data.get("parse") if isinstance(data, dict) else None
    return parse if isinstance(parse, dict) else None


def _error_lines(output: str) -> list[str]:
    """The lines dbt marks as errors, with the indented lines that explain them."""
    lines = output.splitlines()
    picked: list[str] = []
    take = False
    for line in lines:
        text = line.strip()
        if not text:
            continue
        if "Error" in text or "error" in text.split()[:3]:
            take = True
        if take:
            picked.append(text)
            if len(picked) >= MAX_ERROR_LINES:
                break
    return picked


def parse_command(out_dir: Path, profiles_dir: Path) -> list[str]:
    return ["dbt", "parse", "--no-use-colors", "--project-dir", str(out_dir),
            "--profiles-dir", str(profiles_dir)]


def dbt_parse(out_dir: Path, runner: CommandRunner = run_command) -> dict[str, Any]:
    """Run `dbt deps` (when `dbt_packages/` is absent) and `dbt parse` on the written project
    with a throwaway profile for the installed adapter. Typed result: ``status`` ``ok`` |
    ``failed`` | ``unavailable``, ``adapter``, ``seconds``, ``errors``, ``log`` (the output's
    path under `.vault-agent/`), ``command``."""
    available = dbt_available()
    if available is None:
        return {"status": "unavailable", "adapter": None, "seconds": 0.0, "errors": [],
                "log": None, "command": None,
                "detail": "dbt-core with dbt-postgres or dbt-databricks is not installed in "
                          "the workbench's environment (`uv sync --extra demo` or "
                          "`--extra demo-databricks`)"}
    adapter = available["adapter"]
    started = time.monotonic()
    output: list[str] = []
    log_dir = out_dir / ".vault-agent"
    log_dir.mkdir(parents=True, exist_ok=True)
    # The throwaway profile lives beside the run's own bookkeeping, so the recorded CLI
    # equivalent names a real path and the terminal can repeat exactly what the button did.
    profiles_dir = log_dir / "dbt-profiles"
    profiles_dir.mkdir(exist_ok=True)
    (profiles_dir / "profiles.yml").write_text(
        yaml.safe_dump({PROFILE_NAME: {"target": "parse",
                                       "outputs": {"parse": _PROFILES[adapter]}}}),
        encoding="utf-8",
    )
    code = 0
    if not (out_dir / "dbt_packages").is_dir():
        deps = runner(["dbt", "deps", "--no-use-colors", "--project-dir", str(out_dir),
                       "--profiles-dir", str(profiles_dir)], cwd=str(out_dir))
        output.append(deps.stdout + deps.stderr)
        code = deps.returncode
    command = parse_command(out_dir, profiles_dir)
    if code == 0:
        parsed = runner(command, cwd=str(out_dir))
        output.append(parsed.stdout + parsed.stderr)
        code = parsed.returncode
    text = "\n".join(output)
    log = log_dir / "dbt-parse.log"
    log.write_text(text, encoding="utf-8")
    return {
        "status": "ok" if code == 0 else "failed",
        "adapter": adapter,
        "version": available["version"],
        "seconds": round(time.monotonic() - started, 1),
        "errors": _error_lines(text) if code != 0 else [],
        "log": str(log),
        "command": shlex.join(["dbt", "deps", "--project-dir", str(out_dir), "--profiles-dir",
                               str(profiles_dir)]) + " && " + shlex.join(command),
    }
