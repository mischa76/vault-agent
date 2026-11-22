"""C44 — the API chooses 404 by a typed exception, not by the message's prefix. `_guard` in
`ui/app.py` answered 404 when `str(exc)` began with „no " or contained „ has no " — a branch on
message text, against the craft rule. Committed before the change: `ProjectNotFoundError` does
not exist yet, and a `ProjectError` whose message happens to start with „no " answers 404.
Keyless."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from vault_agent.ui import projects
from vault_agent.ui.app import create_app
from vault_agent.ui.projects import ProjectError, ProjectNotFoundError


def test_not_found_is_the_type_not_the_wording(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = TestClient(create_app(tmp_path / "projects"))
    pid = client.post("/api/projects", json={"name": "Bank demo"}).json()["id"]

    def missing(self: projects.ProjectStore, project_id: str) -> dict[str, object]:
        raise ProjectNotFoundError("the project went away between two requests")  # no „no "

    monkeypatch.setattr(projects.ProjectStore, "get", missing)
    assert client.get(f"/api/projects/{pid}").status_code == 404

    def refused(self: projects.ProjectStore, project_id: str) -> dict[str, object]:
        raise ProjectError("no idea what this project wants")                # a refusal, not a miss

    monkeypatch.setattr(projects.ProjectStore, "get", refused)
    assert client.get(f"/api/projects/{pid}").status_code == 400


def test_the_store_raises_the_typed_miss_at_its_lookup_sites(tmp_path: Path) -> None:
    store = projects.ProjectStore(tmp_path / "projects")
    for call in (lambda: store.get("nobody"), lambda: store.run_dir("nobody", "..")):
        try:
            call()
        except ProjectNotFoundError:
            continue
        raise AssertionError("expected ProjectNotFoundError")
    assert issubclass(ProjectNotFoundError, ProjectError)
