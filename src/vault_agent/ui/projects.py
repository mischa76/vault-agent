"""Projects are folders (WP66 §2.1): ``<root>/<id>/project.json``, ``inputs/``, ``runs/``."""
from __future__ import annotations

import builtins
import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, field_validator

from vault_agent.config import LLMOptions, Settings, get_settings
from vault_agent.rules.naming import NamingProfile
from vault_agent.rules.platforms import DEFAULT_TARGET_PLATFORM, TargetPlatform
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


class ProjectSettings(BaseModel):
    """WP113 (C3): what a project pins for every run it starts — each field optional, a
    blank clears it. Secrets are never here; they stay in `.env`."""

    target_platform: TargetPlatform | None = None
    primary_model: str | None = None
    heavy_model: str | None = None
    anthropic_base_url: str | None = None
    # WP114 (C3): the naming profile the project's runs generate under; None = the house style.
    naming: NamingProfile | None = None

    @field_validator("primary_model", "heavy_model", "anthropic_base_url", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("anthropic_base_url")
    @classmethod
    def _url_has_a_scheme(cls, value: str | None) -> str | None:
        if value is not None and not value.lower().startswith(("http://", "https://")):
            raise ValueError("anthropic_base_url must start with http:// or https://")
        return value

    def stored(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None}

    def naming_profile(self) -> NamingProfile:
        return self.naming or NamingProfile()

    def llm_options(self) -> LLMOptions:
        return LLMOptions(primary_model=self.primary_model, heavy_model=self.heavy_model,
                          anthropic_base_url=self.anthropic_base_url)


def environment_facts() -> dict[str, Any]:
    """WP113: the environment a run would inherit — the route, the models, the endpoint, and
    whether the key is set. Never the key. A route without its credentials is reported as
    such instead of raising (the settings model raises at construction)."""
    try:
        settings = get_settings()
    except ValueError:
        return {
            "llm_provider": os.environ.get("LLM_PROVIDER", "anthropic"),
            "anthropic_api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "primary_model": Settings.model_fields["primary_model"].default,
            "heavy_model": Settings.model_fields["heavy_model"].default,
            "anthropic_base_url": os.environ.get("ANTHROPIC_BASE_URL") or None,
            "credentials": "missing for the configured route",
        }
    return {
        "llm_provider": settings.llm_provider,
        "anthropic_api_key_set": bool(settings.anthropic_api_key),
        "primary_model": settings.primary_model,
        "heavy_model": settings.heavy_model,
        "anthropic_base_url": settings.anthropic_base_url,
        "route": settings.route_description(),
    }


class ProjectConflictError(ProjectError):
    """WP112: a deletion a rule refuses (409) — what depends on the thing is named."""


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

    # ----- settings (WP113, C3) ---------------------------------------------------------------
    def settings(self, project_id: str) -> ProjectSettings:
        path = self._dir(project_id) / "settings.json"
        if not path.is_file():
            return ProjectSettings()
        return ProjectSettings.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def save_settings(self, project_id: str, settings: ProjectSettings) -> ProjectSettings:
        path = self._dir(project_id) / "settings.json"
        path.write_text(json.dumps(settings.stored(), indent=2), encoding="utf-8")
        return settings

    def settings_view(self, project_id: str) -> dict[str, Any]:
        """The stored settings, what a run would effectively take, and the environment."""
        stored = self.settings(project_id)
        env = environment_facts()
        return {
            "settings": stored.stored(),
            "effective": {
                "target_platform": stored.target_platform or DEFAULT_TARGET_PLATFORM,
                "primary_model": stored.primary_model or env["primary_model"],
                "heavy_model": stored.heavy_model or env["heavy_model"],
                "anthropic_base_url": stored.anthropic_base_url or env["anthropic_base_url"],
                "naming": stored.naming_profile().model_dump(),  # WP114
            },
            "environment": env,
        }

    # ----- deleting (WP112, C2) ---------------------------------------------------------------
    def _run_metas(self, project_id: str | None = None) -> builtins.list[dict[str, Any]]:
        pattern = f"{project_id}/runs/*/run.json" if project_id else "*/runs/*/run.json"
        return [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(self.root.glob(pattern))
        ]

    def readers_of(self, project_id: str, name: str) -> builtins.list[str]:
        """The project's runs whose record names the input (`requirements`, `schema`,
        `profiling`)."""
        return [
            str(m.get("id")) for m in self._run_metas(project_id)
            if name in (m.get("requirements"), m.get("schema"), m.get("profiling"))
        ]

    def extenders_of(self, run_id: str) -> builtins.list[str]:
        """Every run in the store, any project, that extends ``run_id`` (`existing_run`)."""
        return [str(m.get("id")) for m in self._run_metas() if m.get("existing_run") == run_id]

    def delete_file(self, project_id: str, name: str) -> dict[str, Any]:
        """Remove an input file — unless a run has read it: its record and CLI equivalent
        name it."""
        data = self._read(project_id)
        if Path(name).name != name or not name:
            raise ProjectError(f"file name {name!r} is not a plain file name")
        entry = next((f for f in data["files"] if f["name"] == name), None)
        if entry is None:
            raise ProjectError(f"project {project_id!r} has no input file {name!r}")
        readers = self.readers_of(project_id, name)
        if readers:
            raise ProjectConflictError(
                f"input file {name!r} is kept: run(s) {', '.join(readers)} read it"
            )
        (self.root / project_id / "inputs" / name).unlink(missing_ok=True)
        data["files"] = [f for f in data["files"] if f["name"] != name]
        self._write(project_id, data)
        return {"deleted": name, "kind": entry["kind"]}

    def delete_run_dir(self, project_id: str, run_id: str) -> None:
        """The folder the store locates for the run, removed whole (never a recorded path)."""
        _, _, stamp = run_id.partition(":")
        path = self._dir(project_id) / "runs" / stamp
        if not (path / "run.json").is_file():
            raise ProjectError(f"no run {run_id!r}")
        shutil.rmtree(path)

    def delete(self, project_id: str) -> dict[str, Any]:
        """Remove the project folder whole, once its runs are at rest and nothing outside
        extends them."""
        data = self._read(project_id)
        metas = self._run_metas(project_id)
        busy = [str(m.get("id")) for m in metas if m.get("status") in ("running", "paused")]
        if busy:
            raise ProjectConflictError(
                f"project {project_id!r} is kept: run(s) {', '.join(busy)} running or paused — "
                f"cancel or discard first"
            )
        own = {str(m.get("id")) for m in metas}
        outside = [
            e for run_id in own for e in self.extenders_of(run_id) if e not in own
        ]
        if outside:
            raise ProjectConflictError(
                f"project {project_id!r} is kept: run(s) {', '.join(sorted(set(outside)))} "
                f"of another project extend its runs"
            )
        shutil.rmtree(self.root / project_id)
        return {"deleted": project_id, "runs": len(metas), "files": len(data["files"])}

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
