"""WP72 — the Databricks twin of the bank demo (spec §3). Committed before the change, failing.
Keyless: file parity with the Postgres demo, the seed dialect, the profile's secrets, the
regeneration."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

from vault_agent.rules.platforms import platform_profile

ROOT = Path(__file__).resolve().parents[1]
PG = ROOT / "demo" / "bank_postgres"
DB = ROOT / "demo" / "bank_databricks"


def _rel_files(base: Path, patterns: tuple[str, ...]) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for pattern in patterns:
        for p in sorted(base.glob(pattern)):
            out[str(p.relative_to(base))] = p.read_bytes()
    return out


def test_the_twin_carries_the_same_sql_seeds_and_package_as_the_postgres_demo() -> None:
    patterns = ("models/**/*.sql", "models/**/*.yml", "seeds/*.csv", "packages.yml")
    assert _rel_files(DB, patterns) == _rel_files(PG, patterns)
    assert (DB / "models" / "raw_vault" / "sat_account_customer_eff.sql").exists()


def test_the_seed_types_are_the_dialects_translation_of_the_postgres_demos() -> None:
    pg = yaml.safe_load((PG / "dbt_project.yml").read_text(encoding="utf-8"))
    db = yaml.safe_load((DB / "dbt_project.yml").read_text(encoding="utf-8"))
    assert db["name"] == "bank_databricks" and db["profile"] == "bank_databricks"
    dialect = platform_profile("databricks")
    pg_seeds, db_seeds = pg["seeds"]["bank_postgres"], db["seeds"]["bank_databricks"]
    assert db_seeds["+quote_columns"] is False
    for seed, config in pg_seeds.items():
        if not seed.startswith("raw_"):
            continue
        expected = {col: dialect.seed_type(t) for col, t in config["+column_types"].items()}
        assert db_seeds[seed]["+column_types"] == expected, seed
    text = (DB / "dbt_project.yml").read_text(encoding="utf-8")
    assert "varchar" not in text and ": numeric" not in text


def test_the_profile_reads_the_connection_from_the_environment() -> None:
    text = (DB / "profiles.yml").read_text(encoding="utf-8")
    assert "dapi" not in text  # a Databricks token literal would start with it
    for name in ("DATABRICKS_HOST", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN"):
        assert f"env_var('{name}')" in text or f'env_var("{name}")' in text, name
    assert "DATABRICKS_CATALOG" in text and "'workspace'" in text
    assert "DATABRICKS_SCHEMA" in text and "'default'" in text
    assert "type: databricks" in text


def test_regenerating_with_the_databricks_platform_reproduces_the_committed_models(
    tmp_path: Path,
) -> None:
    spec = importlib.util.spec_from_file_location(
        "bank_databricks_build", DB / "build_vault_models.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    written = module.regenerate(tmp_path)
    assert written
    for path in written:
        committed = DB / "models" / "raw_vault" / path.name
        assert committed.read_bytes() == path.read_bytes(), path.name
