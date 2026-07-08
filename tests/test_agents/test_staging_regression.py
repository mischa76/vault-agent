"""Ungrounded byte-identity regression guard (WP7 constraint, written before the WP).

WP7 (staging refinements) may only change generator output on *grounded* runs
(``state.source_schemas`` non-empty), for satellites that declare a ``source_table``, or
when a contract matches a staging source. A plain ungrounded run over the bank Durchstich
model must keep producing byte-identical raw-vault models, staging models, and scaffolding.
The baseline under ``tests/fixtures/staging_ungrounded_baseline/`` was captured from the
generator BEFORE the WP7 changes (main@51e1088) — regenerating it after an intentional
output change requires saying so in the spec/CLAUDE.md, per the WP7 acceptance criteria.
"""
import importlib.util
from pathlib import Path
from types import ModuleType

_BUILDER_PATH = (
    Path(__file__).parent.parent.parent
    / "demo" / "bank_postgres" / "build_vault_models.py"
)
_BASELINE = Path(__file__).parent.parent / "fixtures" / "staging_ungrounded_baseline"


def _load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_vault_models", _BUILDER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read(relative: str) -> str:
    return (_BASELINE / relative).read_text(encoding="utf-8")


async def test_ungrounded_output_is_byte_identical_to_the_pre_wp7_baseline() -> None:
    builder = _load_builder()
    state = await builder.generate_models(builder.build_bank_dv_model())

    expected_raw = {
        p.stem: p.read_text(encoding="utf-8")
        for p in (_BASELINE / "raw_vault").glob("*.sql")
    }
    expected_staging = {
        p.stem: p.read_text(encoding="utf-8")
        for p in (_BASELINE / "staging").glob("*.sql")
    }
    scaffolding_root = _BASELINE / "scaffolding"
    expected_scaffolding = {
        p.relative_to(scaffolding_root).as_posix(): p.read_text(encoding="utf-8")
        for p in scaffolding_root.rglob("*")
        if p.is_file()
    }

    assert state.artifacts.dbt_models == expected_raw
    assert state.artifacts.staging_models == expected_staging
    assert state.artifacts.scaffolding == expected_scaffolding
