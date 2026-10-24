"""Projects are folders (WP66 §2.1): ``<root>/<id>/project.json``, ``inputs/``, ``runs/``."""
from __future__ import annotations

import builtins
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from vault_agent.source_schema import load_source_schemas

FileKind = Literal["requirements", "schema", "profiling"]
_ALLOWED: dict[str, set[str]] = {
    "requirements": {".md", ".txt", ".pdf"},
    "schema": {".yml", ".yaml", ".json"},
    "profiling": {".yml", ".yaml", ".json"},
}


class ProjectError(ValueError):
    """An attributable refusal (a bad name, a missing project, a file the loader rejects)."""


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        raise ProjectError(f"project name {name!r} leaves no usable identifier")
    return slug


class ProjectStore:
    """The on-disk store the API serves; every method is a plain file operation."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, project_id: str) -> Path:
        path = self.root / project_id
        if not (path / "project.json").is_file():
            raise ProjectError(f"no project {project_id!r} under {self.root}")
        return path

    def _read(self, project_id: str) -> dict[str, Any]:
        path = self._dir(project_id) / "project.json"
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))

    def _write(self, project_id: str, data: dict[str, Any]) -> None:
        (self.root / project_id / "project.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def create(self, name: str) -> dict[str, Any]:
        project_id = _slug(name)
        if (self.root / project_id).exists():
            raise ProjectError(f"project {project_id!r} already exists")
        (self.root / project_id / "inputs").mkdir(parents=True)
        (self.root / project_id / "runs").mkdir()
        data = {
            "id": project_id,
            "name": name,
            "created": datetime.now(UTC).isoformat(timespec="seconds"),
            "files": [],
        }
        self._write(project_id, data)
        return data

    def list(self) -> list[dict[str, Any]]:
        return [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(self.root.glob("*/project.json"))
        ]

    def get(self, project_id: str) -> dict[str, Any]:
        return self._read(project_id)

    def runs(self, project_id: str) -> builtins.list[dict[str, Any]]:
        """One summary per ``runs/<stamp>/run.json``, newest first (WP67 §3.2)."""
        summaries: list[dict[str, Any]] = []
        for meta in sorted(self._dir(project_id).glob("runs/*/run.json"), reverse=True):
            data = json.loads(meta.read_text(encoding="utf-8"))
            summaries.append({k: data.get(k) for k in (
                "id", "status", "started", "finished", "requirements", "schema", "existing_run",
                "error", "profiling", "target_platform",  # WP82
            )})
        return summaries

    def input_path(self, project_id: str, name: str) -> Path:
        path = (self._dir(project_id) / "inputs" / name).resolve()
        if path.parent != (self._dir(project_id) / "inputs").resolve() or not path.is_file():
            raise ProjectError(f"project {project_id!r} has no input file {name!r}")
        return path

    def run_dir(self, project_id: str, run_id: str, *, create: bool = False) -> Path:
        path = self._dir(project_id) / "runs" / run_id
        if create:
            path.mkdir(parents=True, exist_ok=False)
        return path

    def add_file(self, project_id: str, kind: FileKind, name: str, content: str) -> dict[str, Any]:
        """Store an input file; a schema (or profiling) file must pass the house loader first."""
        data = self._read(project_id)
        safe = Path(name).name
        if safe != name or not safe:
            raise ProjectError(f"file name {name!r} is not a plain file name")
        if Path(safe).suffix.lower() not in _ALLOWED[kind]:
            raise ProjectError(
                f"{safe}: a {kind} file must be one of {sorted(_ALLOWED[kind])}"
            )
        target = self.root / project_id / "inputs" / safe
        target.write_text(content, encoding="utf-8")
        if kind == "schema":
            try:
                tables = load_source_schemas(target)
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                target.unlink(missing_ok=True)
                raise ProjectError(f"{safe}: {exc}") from exc
            if not tables:
                target.unlink(missing_ok=True)
                raise ProjectError(f"{safe}: the schema declares no tables")
        entry = {"kind": kind, "name": safe, "bytes": len(content.encode("utf-8"))}
        data["files"] = [f for f in data["files"] if f["name"] != safe] + [entry]
        self._write(project_id, data)
        return entry
