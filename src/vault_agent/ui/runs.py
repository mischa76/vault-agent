"""Runs are background tasks over the CLI's internals (WP66 §2.2–2.4).

Nothing here decides anything: the task calls ``cli._run_pipeline`` and ``cli._resume_pipeline``
with what the API received, writes the outputs the CLI writes, and records the CLI invocation
every action is equivalent to.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import shlex
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from vault_agent import cli
from vault_agent.agents.entity_resolver import pending_resolution_decisions
from vault_agent.agents.orchestrator import assemble_review_queue
from vault_agent.existing_model import load_existing_catalogue, load_existing_model
from vault_agent.link_proposal import pending_link_decisions, proposal_key
from vault_agent.source_schema import load_source_schemas
from vault_agent.state import RESOLUTION_SAME_AS, VaultAgentState, split_concept_key
from vault_agent.ui.projects import ProjectError, ProjectStore

TERMINAL = {"finished", "failed", "discarded"}
# A thread with work in it and nothing running: the CLI's crash path continues or discards it.
CONTINUABLE = {"interrupted", "crashed"}
STATE_FILE = "state.json"  # a finished run's state, beside its trace (WP69 §2.3)


# The answers `resume --resolve` takes beside a construct name (cli._parse_resolve).
RESOLUTION_ANSWERS = ("NEW", "same_as_candidate", "unresolved")


def _pending_links(state: VaultAgentState) -> list[dict[str, Any]]:
    """What the CLI prints at the resolution checkpoint for each proposal (WP71 §2.2)."""
    from vault_agent.state import KeyLicense, LinkProposal

    out = []
    for p in pending_link_decisions(state.link_proposals):
        kind = ("license" if isinstance(p, KeyLicense)
                else "link" if isinstance(p, LinkProposal) else "relationship")
        out.append({
            "key": proposal_key(p), "kind": kind, "target": cli._link_target(p),
            "note": cli._link_category_note(p), "evidence": list(p.evidence),
        })
    return out


def _pending_resolutions(state: VaultAgentState) -> list[dict[str, Any]]:
    out = []
    for p in pending_resolution_decisions(state.resolutions):
        label, entity = split_concept_key(p.concept)
        claim = (
            f"equivalent to {p.same_as!r} but keyed differently"
            if p.resolution == RESOLUTION_SAME_AS else f"IS the existing {p.resolution!r}"
        ) + cli._subtype_note(p, state)
        out.append({
            "concept": p.concept, "label": label, "entity": entity or None, "claim": claim,
            "category": p.category, "confidence": p.confidence, "evidence": list(p.evidence),
        })
    return out


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
        self._reconcile()

    def _reconcile(self) -> None:
        """Runs a gone server left at ``running`` (WP69 §2.4): with a thread and a checkpoint
        database they become ``interrupted`` and continuable, without one ``failed``."""
        for meta_path in sorted(self.store.root.glob("*/runs/*/run.json")):
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("status") != "running":
                continue
            out_dir = Path(meta["out_dir"])
            thread_id = meta.get("thread_id")
            stamp = datetime.now(UTC).isoformat(timespec="seconds")
            if thread_id and Path(cli._checkpoint_db(out_dir)).exists():
                error = "the server stopped while the run was running"
                cli._write_pending(out_dir, thread_id, self._input_doc(meta),
                                   phase=cli.PENDING_CRASHED, error=error)
                meta.update(status="interrupted", error=error, finished=stamp,
                            cli_equivalents=meta.get("cli_equivalents", [])
                            + [self._continue_equivalent(out_dir)])
            else:
                meta.update(status="failed", finished=stamp,
                            error="the server stopped before the run was checkpointed")
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def _input_doc(self, meta: dict[str, Any]) -> Path:
        try:
            return self.store.input_path(meta["project"], meta["requirements"])
        except (ProjectError, KeyError, TypeError):
            return Path("unknown")

    @staticmethod
    def _continue_equivalent(out_dir: Path) -> str:
        return shlex.join(["vault-agent", "resume", "--out", str(out_dir)])

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
        thread_id = uuid4().hex  # known before the task starts (WP69 §2.2)
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
            "thread_id": thread_id,
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
            self._run(run_id, input_doc, out_dir, schema_path, existing_dir, thread_id)
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
        thread_id: str,
    ) -> None:
        try:
            schemas = load_source_schemas(schema_path) if schema_path else []
            existing = load_existing_model(existing_dir) if existing_dir else None
            state, paused, _thread = await cli._run_pipeline(
                input_doc, out_dir, schemas,
                existing_model=existing,
                existing_source=str(existing_dir) if existing_dir else None,
                thread_id=thread_id,
                carried_schemas=load_existing_catalogue(existing_dir) if existing_dir else [],
            )
            self._finish(run_id, state, paused, input_doc, thread_id)
        except asyncio.CancelledError:
            self._interrupt(run_id, out_dir, thread_id, input_doc)
            raise
        except Exception as exc:  # the CLI's rescue has recorded the crash; we record the status
            self._fail(run_id, exc)

    def _interrupt(self, run_id: str, out_dir: Path, thread_id: str, input_doc: Path) -> None:
        """A cancelled task is an interrupted thread, as a crash is (WP69 §2.1): the pending
        pointer the CLI continues from, and the status."""
        meta = self.read(run_id)
        cli._write_pending(out_dir, thread_id, input_doc,
                           phase=cli.PENDING_CRASHED, error="cancelled from the workbench")
        self._update(
            run_id, status="interrupted", error="cancelled from the workbench",
            finished=datetime.now(UTC).isoformat(timespec="seconds"),
            cli_equivalents=meta["cli_equivalents"] + [self._continue_equivalent(out_dir)],
        )

    # ----- cancel / continue (WP69) ----------------------------------------------------------
    async def cancel(self, run_id: str) -> dict[str, Any]:
        meta = self.read(run_id)
        task = self._tasks.get(run_id)
        if meta["status"] != "running" or task is None or task.done():
            raise RunConflictError(f"run {run_id!r} is {meta['status']}; nothing to cancel here")
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        return self.read(run_id)

    async def continue_(self, run_id: str, *, wait: bool) -> dict[str, Any]:
        meta = self.read(run_id)
        if meta["status"] not in CONTINUABLE or not meta["thread_id"]:
            raise ProjectError(f"run {run_id!r} is {meta['status']}, not interrupted or crashed")
        other = self._active if self._active and self._active != run_id else None
        if other and self.read(other)["status"] == "running":
            raise RunConflictError(f"run {self._active!r} is still running")
        out_dir, thread_id = Path(meta["out_dir"]), meta["thread_id"]
        self._update(run_id, status="running", error=None)
        self._states.pop(run_id, None)
        self._active = run_id
        input_doc = self._input_doc(meta)
        self._tasks[run_id] = asyncio.create_task(
            self._continue(run_id, out_dir, thread_id, input_doc)
        )
        if wait:
            await self._tasks[run_id]
        return self.read(run_id)

    async def _continue(
        self, run_id: str, out_dir: Path, thread_id: str, input_doc: Path
    ) -> None:
        try:
            state, paused = await cli._continue_pipeline(out_dir, thread_id, input_doc=input_doc)
            self._finish(run_id, state, paused, input_doc, thread_id)
        except asyncio.CancelledError:
            self._interrupt(run_id, out_dir, thread_id, input_doc)
            raise
        except Exception as exc:
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
            # The final state beside the trace, so a restarted server still serves it (§2.3).
            (cli._checkpoint_dir(out_dir) / STATE_FILE).write_text(
                state.model_dump_json(), encoding="utf-8"
            )
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
        persisted = cli._checkpoint_dir(Path(meta["out_dir"])) / STATE_FILE
        if meta["status"] == "finished" and persisted.is_file():
            state = VaultAgentState.model_validate_json(persisted.read_text(encoding="utf-8"))
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
        at_resolution = cli._paused_at_resolution(state)  # the CLI's predicate (WP71 §2.1)
        return {
            "run": run_id,
            "phase": "resolution" if at_resolution else "signoff",
            "links": _pending_links(state) if at_resolution else [],
            "resolutions": _pending_resolutions(state) if at_resolution else [],
            "answers": list(RESOLUTION_ANSWERS),
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
        links: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        meta = self.read(run_id)
        allowed = {"paused"} | (CONTINUABLE if discard else set())
        if meta["status"] not in allowed or not meta["thread_id"]:
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
        for key, build in (links or {}).items():
            equivalent += ["--link" if build else "--no-link", key]
        if accept:
            equivalent.append("--accept")
        decision = cli._build_decision(
            owner_specs, accept, resolutions=resolutions or None, links=links or None
        )
        state = await self.state(run_id)
        phase = "resolution" if cli._paused_at_resolution(state) else "signoff"
        command = shlex.join(equivalent)
        self._update(
            run_id, status="running",
            cli_equivalents=meta["cli_equivalents"] + [command],
            checkpoints=meta.get("checkpoints", []) + [{"phase": phase, "command": command}],
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
