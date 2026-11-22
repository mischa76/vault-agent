"""The version lives in exactly one place, and three others must agree with it.

Tag `0.9.0` (2026-09-12) shipped while `pyproject.toml` and `__version__` said `0.1.0`: the
version was a constant copied into two files and bumped in neither. Since then `pyproject.toml`
is the source (`uv version X.Y.Z`), `__version__` reads it from the installed distribution, the
lock file carries it, and `CHANGELOG.md` has a section for it. The release workflow refuses a
tag that disagrees; this test catches the drift before a tag exists.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

from typer.testing import CliRunner

import vault_agent
from vault_agent.cli import app

_ROOT = Path(__file__).parent.parent


def _pyproject_version() -> str:
    data = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", _pyproject_version())


def test_package_reports_the_pyproject_version() -> None:
    assert vault_agent.__version__ == _pyproject_version()


def test_lock_file_carries_the_pyproject_version() -> None:
    lock = (_ROOT / "uv.lock").read_text(encoding="utf-8")
    m = re.search(r'^name = "vault-agent"\nversion = "([^"]+)"', lock, re.M)
    assert m, "uv.lock has no vault-agent package entry"
    assert m.group(1) == _pyproject_version(), "run `uv lock` after bumping the version"


def test_changelog_has_a_section_for_the_current_version() -> None:
    changelog = (_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{_pyproject_version()}]" in changelog, (
        "CHANGELOG.md needs a `## [X.Y.Z] - YYYY-MM-DD` section for the version being released"
    )


def test_cli_version_flag_prints_it() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"vault-agent {_pyproject_version()}"
