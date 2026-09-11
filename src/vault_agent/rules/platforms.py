"""Target warehouse platforms the generated dbt project can be aimed at (WP35).

The generated raw-vault and staging models are platform-neutral by construction: every
physical difference is AutomateDV's business, dispatched per adapter inside the package
(``macros/tables/<platform>/``). What the generator itself has to know per platform is
small and lives here, in one place, so no agent re-derives it:

- the **seed column types** written into ``dbt_project.yml`` when a data contract pins a
  staging source's types (WP7 §7.3). The contract speaks JSON-Schema; the mapping to a
  warehouse type is a dialect. ``numeric`` without precision is a *data* trap on
  Databricks — the SQL reference documents ``DECIMAL`` as ``p=10, s=0`` by default
  (learn.microsoft.com/azure/databricks/sql/language-manual/data-types/decimal-type), so
  fractions would be truncated silently on load. Every dialect therefore spells the type
  out; the Postgres dialect is the identity (its output is the byte-identity baseline).
- the **adapter package** and profile shape the generated README points the operator at.

Adding a platform is one ``PlatformProfile`` here plus a fixture pinning its output. It is
NOT a claim of verification: which platforms the project has built against live is a
dated statement in ``docs/operations/09-warehouse.md`` §9.6, never in code.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, get_args

TargetPlatform = Literal["postgres", "databricks"]

DEFAULT_TARGET_PLATFORM: TargetPlatform = "postgres"

# The abstract seed types the staging generator emits (WP7 §7.3). Named after the Postgres
# spelling because that output predates the dialects and is pinned byte-for-byte.
SEED_TYPES: tuple[str, ...] = ("varchar", "bigint", "numeric", "boolean", "timestamp", "date")

# Decimal shape used where a contract says "number" and nothing about scale. 38 is the
# Databricks maximum precision; 18 fractional digits leave 20 integer digits, which covers
# any monetary or measured quantity a source system realistically holds without the
# silent truncation the platform default (p=10, s=0) would apply. A contract carrying an
# explicit precision/scale would be the better source; the contract spec has no such
# field yet, so this is a deliberate wide default, stated here rather than guessed per call.
DATABRICKS_UNSCALED_DECIMAL = "decimal(38,18)"


@dataclass(frozen=True)
class PlatformProfile:
    """What the generator knows about one target platform."""

    name: TargetPlatform
    # The dbt adapter package the operator installs for this platform.
    dbt_adapter: str
    # The `type:` value of a profiles.yml target for the adapter.
    profile_type: str
    # Abstract seed type -> the physical type written into dbt_project.yml.
    seed_types: Mapping[str, str]
    # One line for the generated README: the profile keys the adapter needs.
    profile_hint: str

    def seed_type(self, abstract: str) -> str:
        """Translate one abstract seed type; unknown names are a programming error."""
        return self.seed_types[abstract]


PLATFORMS: Mapping[TargetPlatform, PlatformProfile] = {
    "postgres": PlatformProfile(
        name="postgres",
        dbt_adapter="dbt-postgres",
        profile_type="postgres",
        seed_types={t: t for t in SEED_TYPES},
        profile_hint="host, port, user, password, dbname, schema",
    ),
    "databricks": PlatformProfile(
        name="databricks",
        dbt_adapter="dbt-databricks",
        profile_type="databricks",
        seed_types={
            # STRING is the native character type; VARCHAR on Databricks requires a length.
            "varchar": "string",
            "bigint": "bigint",
            "numeric": DATABRICKS_UNSCALED_DECIMAL,
            "boolean": "boolean",
            "timestamp": "timestamp",
            "date": "date",
        },
        profile_hint="host, http_path, token (or OAuth), catalog, schema",
    ),
}

# Every Literal member has a profile and vice versa — checked at import so a platform added
# to one place and not the other fails at once, not at the first run that selects it.
assert set(get_args(TargetPlatform)) == set(PLATFORMS), "TargetPlatform and PLATFORMS diverge"
assert all(set(p.seed_types) == set(SEED_TYPES) for p in PLATFORMS.values()), (
    "every platform must translate every abstract seed type"
)


def platform_profile(name: TargetPlatform) -> PlatformProfile:
    """The profile for ``name``; the Literal keeps the CLI and state from passing anything else."""
    return PLATFORMS[name]
