"""Greenfield byte-identity guard for WP23 (brownfield mode), written BEFORE the WP.

WP23 adds an extension mode (``run --existing <dir>``). The ADR-0004 inertness pattern
binds: without the flag, a run must produce exactly the artifacts it produced before, byte
for byte. This module pins the whole ``write_outputs`` tree of a representative greenfield
run as a manifest of ``relative path -> sha256`` captured from the generator BEFORE any
WP23 change landed.

A manifest rather than a full copy of the tree: the point here is "nothing moved", and a
per-file digest states that as precisely as a duplicate of ~30 SQL files would, while
staying readable in a diff. The complementary fixtures keep their full-text form —
``staging_ungrounded_baseline/`` (raw vault + staging text) and ``report/`` (the HTML) —
so a digest mismatch can always be localised by running those.

NEW artifacts are allowed and must be named in ``_EXPECTED_NEW``: WP23 §2.1 deliberately
adds ``metadata/dv_model.yml`` (the logical round-trip source) and §2.7 adds
``extension-diff.md`` on extension runs only. Everything else is frozen — a file that
changes content, disappears, or appears unannounced fails here.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from vault_agent.cli import write_outputs

_BUILDER_PATH = (
    Path(__file__).parent.parent / "demo" / "bank_postgres" / "build_vault_models.py"
)
_MANIFEST = Path(__file__).parent / "fixtures" / "greenfield_manifest.json"

# Artifacts WP23 adds on purpose. A greenfield run gains dv_model.yml (§2.1); the diff
# artifact (§2.7) is extension-only and must NOT appear in a greenfield tree.
_EXPECTED_NEW = {"metadata/dv_model.yml"}


def _load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_vault_models", _BUILDER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def greenfield_manifest(out_dir: Path) -> dict[str, str]:
    """Run the real generator over the bank model and digest every written file."""
    builder = _load_builder()
    # The transfer variant exercises the widest surface: a self-referencing transactional
    # link (WP8), an effectivity satellite, a multi-active satellite and the scaffolding.
    state = await builder.generate_models(builder.build_bank_dv_model_with_transfer())
    write_outputs(state, out_dir)
    return {
        str(p.relative_to(out_dir).as_posix()): _digest(p)
        for p in sorted(out_dir.rglob("*"))
        if p.is_file()
    }


async def test_greenfield_output_is_byte_identical_to_the_pre_wp23_baseline(
    tmp_path: Path,
) -> None:
    actual = await greenfield_manifest(tmp_path / "out")
    expected: dict[str, str] = json.loads(_MANIFEST.read_text(encoding="utf-8"))

    missing = sorted(set(expected) - set(actual))
    assert not missing, f"greenfield artifacts disappeared: {missing}"

    appeared = sorted(set(actual) - set(expected))
    assert set(appeared) <= _EXPECTED_NEW, (
        f"unannounced new greenfield artifacts: {sorted(set(appeared) - _EXPECTED_NEW)}"
    )

    changed = sorted(name for name, sha in expected.items() if actual[name] != sha)
    assert not changed, (
        f"greenfield artifacts changed content: {changed} — WP23 must be inert without "
        f"--existing (regenerate the manifest only with a deliberate, documented reason)"
    )


async def test_greenfield_run_writes_no_extension_diff(tmp_path: Path) -> None:
    """§2.7: the diff artifact is extension-only — its absence is part of inertness."""
    out = tmp_path / "out"
    await greenfield_manifest(out)

    assert not (out / "extension-diff.md").exists()


@pytest.mark.skip(reason="regeneration helper; run deliberately, see the module docstring")
async def test_regenerate_manifest(tmp_path: Path) -> None:  # pragma: no cover
    manifest = await greenfield_manifest(tmp_path / "out")
    _MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
