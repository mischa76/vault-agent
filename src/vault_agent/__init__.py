"""Vault-Agent: Agentic AI for Data Vault 2.0 automation."""
from importlib.metadata import PackageNotFoundError, version

try:
    # One source of truth: pyproject.toml's `version`, bumped with `uv version X.Y.Z`. Read
    # from the installed distribution so the constant can never disagree with the package
    # (2026-09-12: tag 0.9.0 shipped while this said "0.1.0", because it was a second copy).
    __version__ = version("vault-agent")
except PackageNotFoundError:  # pragma: no cover - source tree without an install
    __version__ = "0+unknown"
