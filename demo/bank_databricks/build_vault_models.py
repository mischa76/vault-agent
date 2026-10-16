"""Regenerate the raw-vault models of the Databricks bank demo (WP72).

The model is the Postgres demo's — imported, not copied — and the generator runs with
``target_platform="databricks"``. WP35 proved the raw-vault SQL identical across platforms;
the guard in ``tests/test_wp72_bank_databricks.py`` keeps it that way, so the only thing this
script can ever change here is nothing. It exists so the twin is regenerable the same way.
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent
RAW_VAULT_DIR = HERE / "models" / "raw_vault"


def _postgres_demo():  # type: ignore[no-untyped-def]
    path = HERE.parent / "bank_postgres" / "build_vault_models.py"
    spec = importlib.util.spec_from_file_location("bank_postgres_build", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def regenerate(out_dir: Path = RAW_VAULT_DIR) -> list[Path]:
    """Generate the demo's raw-vault models for Databricks into ``out_dir``."""
    pg = _postgres_demo()
    model = pg.build_bank_dv_model_with_transfer()
    state = asyncio.run(pg.generate_models(model, target_platform="databricks"))
    return list(pg.write_models(state, out_dir))


def main() -> None:
    written = regenerate()
    print(f"Generated {len(written)} raw-vault models into {RAW_VAULT_DIR} (target databricks):")
    for path in written:
        print(f"  - {path.name}")


if __name__ == "__main__":
    main()
