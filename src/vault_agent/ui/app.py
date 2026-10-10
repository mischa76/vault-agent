"""The FastAPI application (WP66): routes over :class:`ProjectStore` and :class:`RunManager`."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from vault_agent.report import build_model_mermaid, build_report
from vault_agent.ui.graphs import build_source_mermaid
from vault_agent.ui.projects import FileKind, ProjectError, ProjectStore
from vault_agent.ui.runs import RunConflictError, RunManager


class NewProject(BaseModel):
    name: str


class NewFile(BaseModel):
    kind: FileKind
    name: str
    content: str


class StartRun(BaseModel):
    requirements: str
    schema_file: str | None = Field(default=None, alias="schema")
    existing_run: str | None = None

    model_config = {"populate_by_name": True}


class Decision(BaseModel):
    accept: bool = False
    discard: bool = False
    resolutions: dict[str, str] = Field(default_factory=dict)
    owners: dict[str, str] = Field(default_factory=dict)


def create_app(root: Path) -> FastAPI:
    store = ProjectStore(root)
    runs = RunManager(store)
    app = FastAPI(title="vault-agent workbench", version="0.1")

    def _guard(exc: Exception) -> HTTPException:
        if isinstance(exc, RunConflictError):
            return HTTPException(status_code=409, detail=str(exc))
        if isinstance(exc, ProjectError):
            code = 404 if str(exc).startswith("no ") or " has no " in str(exc) else 400
            return HTTPException(status_code=code, detail=str(exc))
        raise exc

    @app.get("/api/projects")
    def list_projects() -> list[dict[str, Any]]:
        return store.list()

    @app.post("/api/projects", status_code=201)
    def create_project(body: NewProject) -> dict[str, Any]:
        try:
            return store.create(body.name)
        except ProjectError as exc:
            raise _guard(exc) from exc

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, Any]:
        try:
            return store.get(project_id)
        except ProjectError as exc:
            raise _guard(exc) from exc

    @app.post("/api/projects/{project_id}/files", status_code=201)
    def add_file(project_id: str, body: NewFile) -> dict[str, Any]:
        try:
            return store.add_file(project_id, body.kind, body.name, body.content)
        except ProjectError as exc:
            raise _guard(exc) from exc

    @app.post("/api/projects/{project_id}/runs", status_code=201)
    async def start_run(
        project_id: str, body: StartRun, wait: bool = Query(default=False)
    ) -> dict[str, Any]:
        try:
            return await runs.start(
                project_id, body.requirements, body.schema_file, body.existing_run, wait=wait
            )
        except (ProjectError, RunConflictError) as exc:
            raise _guard(exc) from exc

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        try:
            return runs.read(run_id)
        except ProjectError as exc:
            raise _guard(exc) from exc

    @app.get("/api/runs/{run_id}/events")
    def get_events(run_id: str, after: int = Query(default=0, ge=0)) -> dict[str, Any]:
        try:
            return runs.events(run_id, after)
        except ProjectError as exc:
            raise _guard(exc) from exc

    @app.get("/api/runs/{run_id}/checkpoint")
    async def get_checkpoint(run_id: str) -> dict[str, Any]:
        try:
            return await runs.checkpoint(run_id)
        except ProjectError as exc:
            raise _guard(exc) from exc

    @app.post("/api/runs/{run_id}/checkpoint")
    async def decide(
        run_id: str, body: Decision, wait: bool = Query(default=False)
    ) -> dict[str, Any]:
        try:
            return await runs.decide(
                run_id, accept=body.accept, discard=body.discard,
                resolutions=body.resolutions, owners=body.owners, wait=wait,
            )
        except (ProjectError, ValueError) as exc:
            if isinstance(exc, ProjectError):
                raise _guard(exc) from exc
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/runs/{run_id}/artefacts")
    def list_artefacts(run_id: str) -> list[dict[str, Any]]:
        try:
            return runs.artefacts(run_id)
        except ProjectError as exc:
            raise _guard(exc) from exc

    @app.get("/api/runs/{run_id}/artefacts/{relative:path}")
    def get_artefact(run_id: str, relative: str) -> FileResponse:
        try:
            return FileResponse(runs.artefact(run_id, relative))
        except ProjectError as exc:
            raise _guard(exc) from exc

    @app.get("/api/runs/{run_id}/model")
    async def get_model(run_id: str) -> dict[str, Any]:
        try:
            state = await runs.state(run_id)
        except ProjectError as exc:
            raise _guard(exc) from exc
        return {
            "run": run_id,
            "model": state.dv_model.model_dump(mode="json"),
            "output_mermaid": build_model_mermaid(state.dv_model),
            "input_mermaid": build_source_mermaid(state.source_schemas),
            "existing": (
                state.existing_model.model_dump(mode="json") if state.existing_model else None
            ),
        }

    @app.get("/api/runs/{run_id}/report", response_class=HTMLResponse)
    async def get_report(run_id: str) -> str:
        try:
            state = await runs.state(run_id)
        except ProjectError as exc:
            raise _guard(exc) from exc
        return build_report(state)

    return app
