"""The physical naming profile the generator writes under (WP114, backlog C3).

What a Data Vault's technical names look like is a house style, not a rule of the method:
the staging model's prefix, the hash-key and hashdiff suffixes, the load-date, record-source
and effectivity columns, and whether technical names are upper or lower snake case. This
module holds that style as one typed, frozen value; ``DEFAULT_NAMING`` is the style every
fixture, demo and chain was generated under, and the six constants in ``dv2_rules`` are its
values. A run carries its profile on the state (``VaultAgentState.naming``), the generators
read it from there — never a module-level switch — and an output persists a non-default
profile as ``metadata/naming.yml``, which an extension adopts (the generated names must hit
the tables that hold history).

Deliberately NOT here: construct prefixes (``hub_``/``link_``/``sat_`` are the modeler's and
``E_BAD_NAME``'s — the profile names what the generator writes, not what the model is called),
CamelCase or quoted identifiers (AutomateDV renders columns unquoted; C3 defers them until
quoting everywhere and a build per platform exist).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

TechnicalCase = Literal["upper", "lower"]


class NamingProfile(BaseModel):
    """One house style. Frozen: a run's profile never changes after the state is built."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    staging_prefix: str = "stg_"
    hashkey_suffix: str = "_HK"
    hashdiff_suffix: str = "_HASHDIFF"
    load_datetime: str = "LOAD_DATETIME"
    record_source: str = "RECORD_SOURCE"
    applied_dts: str = "APPLIED_DTS"
    technical_case: TechnicalCase = "upper"

    @field_validator("staging_prefix", "hashkey_suffix", "hashdiff_suffix", "load_datetime",
                     "record_source", "applied_dts")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("a naming profile value must not be empty")
        return value

    def fold(self, name: str) -> str:
        """A technical name in the profile's case."""
        return name.upper() if self.technical_case == "upper" else name.lower()

    def hashkey(self, base: str) -> str:
        """``CUSTOMER`` -> ``CUSTOMER_HK`` under the default."""
        return self.fold(base + self.hashkey_suffix)

    def hashdiff(self, base: str) -> str:
        return self.fold(base + self.hashdiff_suffix)

    @property
    def load_datetime_column(self) -> str:
        return self.fold(self.load_datetime)

    @property
    def record_source_column(self) -> str:
        return self.fold(self.record_source)

    @property
    def applied_column(self) -> str:
        return self.fold(self.applied_dts)

    def stage(self, construct_name: str) -> str:
        """The staging model of a construct — the one rule, in ``dv2_rules``."""
        from vault_agent.rules.dv2_rules import stage_model_name

        return stage_model_name(construct_name, self)

    def is_default(self) -> bool:
        return self == DEFAULT_NAMING


DEFAULT_NAMING = NamingProfile()
