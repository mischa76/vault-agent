"""WP118 (C43) — the workbench's ids are checked before any path is built, and the owner spec
parses in linear time. Committed before the change: the dot-dot tests and the timing test fail,
the equivalence table passes on the old code and pins what the rewrite must keep. Keyless."""
from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from vault_agent.cli import _parse_owner
from vault_agent.ui.app import create_app
from vault_agent.ui.projects import ProjectError, ProjectStore

_DEMO_ROOT = Path(__file__).resolve().parents[1] / "demo" / "workbench-adventureworks"


def _plant_parent_project(tmp_path: Path) -> Path:
    """A `project.json` in the parent of the store's root: what `..` would read, write and
    delete. The shipped demo's root is such a sub-folder of a tree the owner names."""
    marker = tmp_path / "project.json"
    marker.write_text(json.dumps({"id": "parent", "name": "parent", "files": []}))
    (tmp_path / "runs").mkdir()
    return marker


# --- project ids ------------------------------------------------------------------------------


def test_dot_dot_is_no_project_at_the_store(tmp_path: Path) -> None:
    _plant_parent_project(tmp_path)
    store = ProjectStore(tmp_path / "projects")
    with pytest.raises(ProjectError, match="no project"):
        store.get("..")
    with pytest.raises(ProjectError, match="no project"):
        store.settings("..")


def test_an_encoded_dot_dot_is_404_at_the_api_and_the_parent_survives(tmp_path: Path) -> None:
    """`%2E%2E` is not normalised by a client that does not want it normalised; measured
    2026-11-03: it reaches the route with `project_id == ".."`."""
    marker = _plant_parent_project(tmp_path)
    client = TestClient(create_app(tmp_path / "projects"))
    assert client.get("/api/projects/%2E%2E").status_code == 404
    assert client.put("/api/projects/%2E%2E/settings", json={}).status_code == 404
    assert not (tmp_path / "settings.json").exists()
    assert client.delete("/api/projects/%2E%2E").status_code == 404
    assert marker.exists() and (tmp_path / "projects").is_dir()


# --- run stamps -------------------------------------------------------------------------------


def _project_with_a_stray_run_json(client: TestClient, root: Path) -> str:
    pid = client.post("/api/projects", json={"name": "Bank demo"}).json()["id"]
    meta: dict[str, Any] = {
        "id": f"{pid}:..", "project": pid, "status": "finished",
        "out_dir": str(root / pid), "thread_id": "t", "cli_equivalents": [],
    }
    (root / pid / "run.json").write_text(json.dumps(meta))
    return pid


def test_dot_dot_is_no_run_at_the_store_and_the_api(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    client = TestClient(create_app(root))
    pid = _project_with_a_stray_run_json(client, root)
    store = ProjectStore(root)
    with pytest.raises(ProjectError, match="no run"):
        store.run_dir(pid, "..")
    assert client.get(f"/api/runs/{pid}:..").status_code == 404
    # `runs/..` is the project folder itself; before the check, `delete_run_dir` removed it whole.
    with pytest.raises(ProjectError, match="no run"):
        store.delete_run_dir(pid, f"{pid}:..")
    assert (root / pid / "project.json").is_file()


def test_every_id_the_store_itself_creates_passes_its_check(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    pid = store.create("Bank demo 2026 — Zürich!")["id"]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    assert store.run_dir(pid, stamp, create=True).is_dir()
    assert store.get(pid)["id"] == pid


@pytest.mark.skipif(not _DEMO_ROOT.is_dir(), reason="the shipped demo is not checked out")
def test_the_shipped_demo_runs_pass_the_stamp_check() -> None:
    store = ProjectStore(_DEMO_ROOT)
    stamps = sorted(p.name for p in (_DEMO_ROOT / "adventureworks" / "runs").iterdir())
    assert stamps
    for stamp in stamps:
        assert store.run_dir("adventureworks", stamp).is_dir()


# --- the owner spec ---------------------------------------------------------------------------


def _legacy_parse(spec: str) -> tuple[str, dict[str, str | None]] | type[ValueError]:
    """`_parse_owner` as it stood before WP118 — the two regexes — so the table below is judged
    against the code's own former answers, not against a hand-written expectation."""
    asset, sep, rest = spec.partition("=")
    asset, rest = asset.strip(), rest.strip()
    if not sep or not asset or not rest:
        return ValueError
    if re.fullmatch(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", rest):
        return asset, {"name": rest.split("@", 1)[0], "email": rest}
    email: str | None = None
    match = re.search(r"<([^>]+)>", rest)
    if match:
        email = match.group(1).strip()
        rest = rest[: match.start()].strip()
    if not rest:
        return ValueError
    return asset, {"name": rest, "email": email}


@pytest.mark.parametrize("spec", [
    "customer=John Doe <john.doe@acme.com>",
    "customer=john.doe@acme.com",
    "customer=Data Team",
    "a=x@y",                       # no dot in the domain: a name, not an address
    "a=x@.io",                     # the dot needs a character before it
    "a=x@a.b.",                    # … and one after some dot — `a.b.` has `b` after the first
    "a=x@a..b",
    "a=x@y.z@w",                   # a second `@`: not an address
    "a=x y@z.io",                  # whitespace: not an address
    "a=x y@z.io",             # Unicode whitespace too
    "a=<>Team <t@x.io>",           # the first `<>` is empty; the second pair is the e-mail
    "a=Ann <b <c@x.io>",           # a `<` inside the brackets belongs to the e-mail
    "a=Ann <  c@x.io  >",
    "a=Ann < >",                   # an e-mail of spaces strips to the empty string, as before
    "a=<only@x.io>",               # no name left: refused
    "a=Ann >x< <y@z.io>",
    "", "noequals", "=onlyname", "customer=",
])
def test_the_rewrite_answers_as_the_regexes_did(spec: str) -> None:
    expected = _legacy_parse(spec)
    if expected is ValueError:
        with pytest.raises(ValueError):
            _parse_owner(spec)
    else:
        assert _parse_owner(spec) == expected


@pytest.mark.parametrize("rest", ["<" * 60_000, "a@" + "." * 60_000 + "<"])
def test_a_long_spec_parses_in_linear_time(rest: str) -> None:
    """The two regexes backtracked quadratically: 7.0 s and 11.3 s on these inputs (2026-11-03);
    two seconds leaves a slow runner room and the old code none."""
    started = time.perf_counter()
    _parse_owner(f"x={rest}")
    assert time.perf_counter() - started < 2.0


# --- the static fallback route (found by the C43 triage, 2026-11-03) --------------------------


def test_the_static_route_never_leaves_the_bundle_directory(tmp_path: Path) -> None:
    """`static / path` with an absolute `path` *replaces* the base (`pathlib` semantics), and
    `%2F` arrives as `/`: measured 2026-11-03, `GET /%2Fetc%2Fhostname` served the file. The
    route must answer with the bundle (index or a file under it), never with anything outside."""
    from urllib.parse import quote

    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>bundle</html>")
    (static / "app.js").write_text("console.log(1)")
    secret = tmp_path / "secret.txt"
    secret.write_text("not for the browser")
    client = TestClient(create_app(tmp_path / "projects", static))
    assert client.get("/app.js").text == "console.log(1)"
    for path in (
        "/" + quote(str(secret), safe=""),             # absolute path, encoded
        "/" + quote("../secret.txt", safe=""),          # dot-dot, encoded
        "/" + quote("sub/../../secret.txt", safe=""),   # dot-dot behind a segment
    ):
        r = client.get(path)
        assert r.status_code == 200 and "not for the browser" not in r.text, path
        assert "bundle" in r.text, path
