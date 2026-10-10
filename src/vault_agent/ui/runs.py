"""Runs are background tasks over the CLI's internals (WP66 §2.2–2.4).

Nothing here decides anything: the task calls ``cli._run_pipeline`` and ``cli._resume_pipeline``
with what the API received, writes the outputs the CLI writes, and records the CLI invocation
every action is equivalent to.
"""
from __future__ import annotations

import asyncio
import json
import shlex
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from vault_agent import cli
from vault_agent.agents.orchestrator import assemble_review_queue
from vault_agent.existing_model import load_existing_model
from vault_agent.source_schema import load_source_schemas
from vault_agent.state import VaultAgentState
from vault_agent.ui.projects import ProjectError, ProjectStore

TERMINAL = {"finished", "failed", "crashed", "discarded"}


class RunConflictError(RuntimeError):
    """A second run while one is active: the checkpointer is single-slot per process here."""


def _owner_spec(asset: str, owner: str) -> str:
    return f"{asset}={owner}"


class RunManager:
    """One active run per process; states of this session's runs stay in memory."""

    def __init__(self, store: ProjectStore) -> None:
        self.store = store
        self._active: str | None = None
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._states: dict[str, VaultAgentState] = {}

    # ----- run.json ------------------------------------------------------------------------
    def _meta_path(self, run_id: str) -> Path:
        project_id, _, stamp = run_id.partition(":")
        return self.store.run_dir(project_id, stamp) / "run.json"

    def read(self, run_id: str) -> dict[str, Any]:
        path = self._meta_path(run_id)
        if not path.is_file():
            raise ProjectError(f"no run {run_id!r}")
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))

    def _update(self, run_id: str, **fields: Any) -> dict[str, Any]:
        data = self.read(run_id)
        data.update(fields)
        self._meta_path(run_id).write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    def out_dir(self, run_id: str) -> Path:
        return Path(self.read(run_id)["out_dir"])

    # ----- start -----------------------------------------------------------------------------
    async def start(
        self,
        project_id: str,
        requirements: str,
        schema: str | None,
        existing_run: str | None,
        *,
        wait: bool,
    ) -> dict[str, Any]:
        if self._active and self.read(self._active)["status"] == "running":
            raise RunConflictError(f"run {self._active!r} is still running")
        input_doc = self.store.input_path(project_id, requirements)
        schema_path = self.store.input_path(project_id, schema) if schema else None
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        run_id = f"{project_id}:{stamp}"
        out_dir = self.store.run_dir(project_id, stamp, create=True)
        existing_dir = Path(self.read(existing_run)["out_dir"]) if existing_run else None
        equivalent = ["vault-agent", "run", str(input_doc), "--out", str(out_dir)]
        if schema_path:
            equivalent += ["--source-schema", str(schema_path)]
        if existing_dir:
            equivalent += ["--existing", str(existing_dir)]
        meta = {
            "id": run_id,
            "project": project_id,
            "status": "running",
            "thread_id": None,
            "out_dir": str(out_dir),
            "requirements": requirements,
            "schema": schema,
            "existing_run": existing_run,
            "started": datetime.now(UTC).isoformat(timespec="seconds"),
            "finished": None,
            "error": None,
            "cli_equivalents": [shlex.join(equivalent)],
        }
        (out_dir / "run.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        self._active = run_id
        self._tasks[run_id] = asyncio.create_task(
            self._run(run_id, input_doc, out_dir, schema_path, existing_dir)
        )
        if wait:
            await self._tasks[run_id]
        return self.read(run_id)

    async def _run(
        self,
        run_id: str,
        input_doc: Path,
        out_dir: Path,
        schema_path: Path | None,
        existing_dir: Path | None,
    ) -> None:
        try:
            schemas = load_source_schemas(schema_path) if schema_path else []
            existing = load_existing_model(existing_dir) if existing_dir else None
            state, paused, thread_id = await cli._run_pipeline(
                input_doc, out_dir, schemas,
                existing_model=existing,
                existing_source=str(existing_dir) if existing_dir else None,
            )
            self._update(run_id, thread_id=thread_id)
            self._finish(run_id, state, paused, input_doc, thread_id)
        except Exception as exc:  # the CLI's rescue has recorded the crash; we record the status
            self._fail(run_id, exc)

    def _finish(
        self, run_id: str, state: VaultAgentState, paused: bool, input_doc: Path, thread_id: str
    ) -> None:
        out_dir = self.out_dir(run_id)
        cli.write_outputs(state, out_dir)
        self._states[run_id] = state
        if paused:
            cli._write_pending(out_dir, thread_id, input_doc)
            self._update(run_id, status="paused")
        else:
            cli._clear_pending(out_dir)
            self._update(
                run_id, status="finished",
                finished=datetime.now(UTC).isoformat(timespec="seconds"),
            )

    def _fail(self, run_id: str, exc: Exception) -> None:
        out_dir = self.out_dir(run_id)
        try:
            pending = cli._read_pending(out_dir)
        except ValueError:
            pending = None
        crashed = pending is not None and cli._pending_phase(pending) == "crashed"
        self._update(
            run_id, status="crashed" if crashed else "failed",
            error=f"{type(exc).__name__}: {exc}",
            finished=datetime.now(UTC).isoformat(timespec="seconds"),
        )

    # ----- state -----------------------------------------------------------------------------
    async def state(self, run_id: str) -> VaultAgentState:
        if run_id in self._states:
            return self._states[run_id]
        meta = self.read(run_id)
        if meta["status"] == "paused" and meta["thread_id"]:
            state = await cli._paused_state(Path(meta["out_dir"]), meta["thread_id"])
            self._states[run_id] = state
            return state
        raise ProjectError(f"run {run_id!r} has no state in this session ({meta['status']})")

    async def checkpoint(self, run_id: str) -> dict[str, Any]:
        meta = self.read(run_id)
        if meta["status"] != "paused":
            raise ProjectError(f"run {run_id!r} is {meta['status']}, not paused")
        state = await self.state(run_id)
        queue = assemble_review_queue(state)
        unresolved = sorted(cli._multi_source_unresolved(state))
        return {
            "run": run_id,
            "blocked": queue.requires_signoff,
            "decisions": len(queue.decisions),
            "disclosures": len(queue.disclosures),
            "items": [item.model_dump(mode="json") for item in queue.items],
            "unresolved": [
                {"concept": c, "evidence": cli._unresolved_evidence(state, c)} for c in unresolved
            ],
        }

    # ----- decide ----------------------------------------------------------------------------
    async def decide(
        self,
        run_id: str,
        *,
        accept: bool,
        discard: bool,
        resolutions: dict[str, str],
        owners: dict[str, str],
        wait: bool,
    ) -> dict[str, Any]:
        meta = self.read(run_id)
        if meta["status"] != "paused" or not meta["thread_id"]:
            raise ProjectError(f"run {run_id!r} is {meta['status']}, not paused")
        out_dir, thread_id = Path(meta["out_dir"]), meta["thread_id"]
        equivalent = ["vault-agent", "resume", "--out", str(out_dir)]
        if discard:
            equivalent.append("--discard")
            await cli._discard_pending(out_dir, thread_id)
            self._states.pop(run_id, None)
            return self._update(
                run_id, status="discarded",
                cli_equivalents=meta["cli_equivalents"] + [shlex.join(equivalent)],
                finished=datetime.now(UTC).isoformat(timespec="seconds"),
            )
        owner_specs = [_owner_spec(asset, owner) for asset, owner in owners.items()]
        for spec in owner_specs:
            equivalent += ["--owner", spec]
            cli._parse_owner(spec)  # the CLI's validation, before anything runs
        for concept, answer in resolutions.items():
            equivalent += ["--resolve", f"{concept}={answer}"]
        if accept:
            equivalent.append("--accept")
        decision = cli._build_decision(owner_specs, accept, resolutions=resolutions or None)
        self._update(
            run_id, status="running",
            cli_equivalents=meta["cli_equivalents"] + [shlex.join(equivalent)],
        )
        self._states.pop(run_id, None)
        self._active = run_id
        input_doc = self.store.input_path(meta["project"], meta["requirements"])
        self._tasks[run_id] = asyncio.create_task(
            self._resume(run_id, out_dir, thread_id, decision, input_doc)
        )
        if wait:
            await self._tasks[run_id]
        return self.read(run_id)

    async def _resume(
        self, run_id: str, out_dir: Path, thread_id: str, decision: dict[str, Any], input_doc: Path
    ) -> None:
        try:
            state, paused = await cli._resume_pipeline(
                out_dir, thread_id, decision, input_doc=input_doc
            )
            self._finish(run_id, state, paused, input_doc, thread_id)
        except Exception as exc:
            self._fail(run_id, exc)

    # ----- evidence --------------------------------------------------------------------------
    def events(self, run_id: str, after: int) -> dict[str, Any]:
        meta = self.read(run_id)
        lines: list[dict[str, Any]] = []
        if meta["thread_id"]:
            path = cli._trace_path(Path(meta["out_dir"]), meta["thread_id"])
            if path.is_file():
                raw = path.read_text(encoding="utf-8").splitlines()
                lines = [json.loads(line) for line in raw[after:] if line.strip()]
        return {"run": run_id, "status": meta["status"], "after": after,
                "next": after + len(lines), "events": lines}

    def artefacts(self, run_id: str) -> list[dict[str, Any]]:
        out_dir = self.out_dir(run_id)
        entries = []
        for path in sorted(out_dir.rglob("*")):
            relative = path.relative_to(out_dir)
            if path.is_file() and ".vault-agent" not in relative.parts:
                entries.append({"path": str(relative), "bytes": path.stat().st_size})
        return entries

    def artefact(self, run_id: str, relative: str) -> Path:
        out_dir = self.out_dir(run_id).resolve()
        path = (out_dir / relative).resolve()
        if out_dir not in path.parents or not path.is_file():
            raise ProjectError(f"run {run_id!r} has no artefact {relative!r}")
        return path
