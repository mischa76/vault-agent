"""Deterministic synthetic-landscape generator (WP13 §2, Charter A).

``python -m eval.scale.generate --tables N --seed S --out <dir>`` writes a complete,
mutually-consistent input set for a landscape of ``N`` source tables across three synthetic
source systems — a cryptic DACH legacy system, an anglophone CRM, and a smaller peripheral
system — so the pipeline can be exercised at enterprise *breadth* before a customer finds
the first breakpoint.

Four artifacts, all derived from the same in-memory model so they never disagree:

* ``source_schema.yml`` — ``N`` tables with types + comments (the ADR-0008 precondition-(c)
  shape), seeded to carry the spike's five trap classes in reported proportions.
* ``profiling.yml`` — plausible per-column statistics, including the *statistics trap*
  (a technical GUID profiling flawlessly next to the true, slightly-warty business key).
* ``requirements.md`` — a requirements document naming the business entities/relationships,
  whose size scales with ``N``; the generator warns when it approaches ``MAX_DOCUMENT_CHARS``.
* ``golden_mapping.yml`` — for a sampled ~30-concept universe (WP9.2 semantics, *not* all
  ``N`` tables) the known-correct mappings / ambiguous synonyms / gaps — the generator
  *knows* the truth, which is the whole point of synthetic data.

Determinism: the same ``(tables, seed)`` yields byte-identical files (pinned test). All
generation is keyless and depends on ``vault_agent`` only for the ``MAX_DOCUMENT_CHARS``
value (what we measure against) and ``normalize_identifier`` (golden↔schema consistency),
keeping the WP6 ``eval → src`` dependency direction.
"""
from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from vault_agent.agents.requirements_parser import MAX_DOCUMENT_CHARS

# ── Controlled variables (seeded, reported): the scale-test's independent knobs ──────────
# Proportions are of the total table budget unless noted; kept as named constants so a run's
# trap density is auditable (the §5 tests assert these classes are present, not the exact
# strings). Rationale for each trap class: spike-mapping-results.md §4.
WIDE_FRACTION = 0.06  # tables that are wide (100–300 cols) → modeler satellite splitting
WIDE_MIN_COLS = 100
WIDE_MAX_COLS = 300
RELATIONSHIP_FRACTION = 0.22  # junction/child tables carrying FK-comment traps (WP9.1)
MULTISOURCE_FRACTION = 0.30  # of the *primary* entities: also present in the CRM (WP10 hub)
FALSE_FRIEND_FRACTION = 0.12  # tables seeded with a misleadingly-named column
GUID_SHADOW_FRACTION = 0.5  # entity tables carrying a technical GUID beside the real key
GOLDEN_SAMPLE_SIZE = 30  # hand-verifiable sampled concept universe (WP9.2), not all tables

SYSTEM_LEGACY = "legacy"
SYSTEM_CRM = "crm"
SYSTEM_PERIPHERAL = "peripheral"

_SCHEMA_BY_SYSTEM = {
    SYSTEM_LEGACY: "legacy_vektra",
    SYSTEM_CRM: "crm",
    SYSTEM_PERIPHERAL: "aux_avis",
}
_PREFIX_BY_SYSTEM = {SYSTEM_LEGACY: "VEKTRA", SYSTEM_CRM: "CRM", SYSTEM_PERIPHERAL: "AVIS"}


@dataclass(frozen=True)
class EntityDef:
    """A primary business entity: the golden concepts are sampled from these."""

    key: str  # slug used for table/relationship wiring, e.g. "partner"
    term: str  # the business-key concept as the requirements name it, e.g. "partner number"
    label_de: str  # German Fachbegriff for the requirements prose, e.g. "Partner"
    legacy_col: str  # cryptic legacy key column, e.g. "PARTN_NR"
    crm_col: str  # anglophone CRM key column, e.g. "ExternalPartnerNo"
    # (concept term, legacy column, type, comment) descriptive attributes
    attrs: tuple[tuple[str, str, str, str], ...] = ()


# The primary catalog: realistic Swiss/DACH insurance-&-banking entities with cryptic legacy
# names (abbreviation trap by construction) and anglophone CRM synonyms (synonym trap when an
# entity is multi-source). Golden concepts are drawn from here.
BASE_ENTITIES: tuple[EntityDef, ...] = (
    EntityDef("partner", "partner number", "Partner", "PARTN_NR", "ExternalPartnerNo", (
        ("partner name", "PARTN_NAME", "varchar(60)", "Primary name line (surname / company)."),
        ("date of birth", "GEB_DAT", "date", "Date of birth (natural persons only)."),
        ("partner type", "PARTN_TYP", "char(1)", "P = natural person, F = Firma (company)."),
    )),
    EntityDef("contract", "contract number", "Vertrag", "VERTR_NR", "ContractNo", (
        ("contract status", "VERTR_STAT", "char(2)", "A=active, S=suspended, T=terminated."),
        ("premium", "PRAEMIE", "numeric(12,2)", "Annual gross premium in CHF."),
    )),
    EntityDef("policy", "policy number", "Police", "POL_NR", "PolicyNo", (
        ("branch of insurance", "SPARTE", "varchar(20)", "Versicherungssparte (line of business)."),
    )),
    EntityDef("claim", "claim number", "Schaden", "SCHAD_NR", "ClaimNo", (
        ("loss date", "SCHAD_DAT", "date", "Schadendatum (date of loss)."),
        ("reserve amount", "RESERVE", "numeric(14,2)", "Case reserve in CHF."),
    )),
    EntityDef("account", "account number", "Konto", "KONTO_NR", "AccountNo", (
        ("iban", "IBAN", "varchar(34)", "IBAN of the account."),
        ("currency", "WHRG", "char(3)", "ISO currency code."),
    )),
    EntityDef("product", "product code", "Produkt", "PROD_CD", "ProductCode", (
        ("product name", "PROD_BEZ", "varchar(80)", "Produktbezeichnung."),
    )),
    EntityDef("invoice", "invoice number", "Rechnung", "RECHN_NR", "InvoiceNo", (
        ("invoice amount", "RECHN_BETR", "numeric(12,2)", "Rechnungsbetrag in CHF."),
        ("due date", "FAELLIG_DAT", "date", "Fälligkeitsdatum."),
    )),
    EntityDef("payment", "payment reference", "Zahlung", "ZAHL_REF", "PaymentRef", (
        ("payment amount", "ZAHL_BETR", "numeric(12,2)", "Zahlungsbetrag in CHF."),
    )),
    EntityDef("broker", "broker number", "Makler", "MAKLR_NR", "BrokerId", (
        ("broker name", "MAKLR_NAME", "varchar(60)", "Maklername."),
    )),
    EntityDef("agent", "agent number", "Agentur", "AGENT_NR", "AgentCode", (
        ("agency region", "AG_REGION", "varchar(20)", "Vertriebsregion."),
    )),
    EntityDef("coverage", "coverage number", "Deckung", "DECK_NR", "CoverageNo", (
        ("sum insured", "VS_SUMME", "numeric(14,2)", "Versicherungssumme."),
    )),
    EntityDef("household", "household number", "Haushalt", "HH_NR", "HouseholdId", (
        ("postal code", "HH_PLZ", "varchar(10)", "Postleitzahl."),
    )),
    EntityDef("vehicle", "vehicle number", "Fahrzeug", "FZG_NR", "VehicleNo", (
        ("license plate", "KONTROLLSCHILD", "varchar(12)", "Kontrollschild (license plate)."),
    )),
    EntityDef("tariff", "tariff code", "Tarif", "TARIF_CD", "TariffCode", (
        ("tariff group", "TARIF_GRP", "varchar(10)", "Tarifgruppe."),
    )),
)

# Concepts the requirements name but no OLTP source feeds — the honest gaps (derived KPIs and
# out-of-scope spreadsheets). The correct answer for each is 'gap', never a column.
GAP_CONCEPTS: tuple[tuple[str, str], ...] = (
    ("customer lifetime value", "derived KPI, computed in the mart — no source column"),
    ("loss ratio", "derived KPI (claims / premium) — computed downstream, not sourced"),
    ("broker commission plan", "maintained in a broker Excel list, out of the OLTP scope"),
)

# A pool of extra legacy entity names (breadth noise) used once the primary catalog is
# exhausted; golden concepts are NOT drawn from these — they exist to reach N and stress the
# validator / mapper at scale. Cryptic on purpose.
_EXTRA_ENTITY_ABBR = (
    "OBJEKT", "RISIKO", "BELEG", "MAHNUNG", "PROVISION", "BONUS", "SCHADENZAHL", "BEITRAG",
    "KLAUSEL", "SELBSTBEH", "INKASSO", "STORNO", "WANDLUNG", "BUCHUNG", "LIMITE", "SICHERHEIT",
    "MELDUNG", "VORGANG", "DOKUMENT", "AUFGABE", "FRIST", "KAMPAGNE", "SEGMENT", "SCORING",
)

_TYPE_CYCLE = (
    "varchar(40)", "varchar(20)", "integer", "numeric(12,2)", "date", "char(2)", "boolean",
    "timestamp", "varchar(80)", "bigint",
)


@dataclass
class Column:
    name: str
    type: str
    comment: str | None
    role: str  # bk | guid | fk | attr | false_friend | audit
    uniqueness: float = 0.5
    null_ratio: float = 0.0
    examples: tuple[str, ...] = ()


@dataclass
class Table:
    name: str
    system: str
    schema: str
    entity: str  # the entity slug this table is about (for wiring/golden)
    kind: str  # entity | relationship | reference | wide
    row_count: int
    columns: list[Column] = field(default_factory=list)


@dataclass
class Landscape:
    tables: list[Table]
    entities: dict[str, EntityDef]  # slug -> def, for primary entities present as tables
    multi_source: set[str]  # primary entity slugs present in >= 2 systems
    false_friend_tables: list[tuple[str, str]]  # (table, column) with the false-friend trap
    n_requested: int
    seed: int


# ── generation ──────────────────────────────────────────────────────────────────────────
def _audit_columns() -> list[Column]:
    """The load-audit tail every table carries (record-source style noise)."""
    return [
        Column("MUT_DAT", "timestamp", "Last-mutation timestamp (technical).", "audit", 1.0, 0.0),
        Column("MUT_USER", "varchar(20)", "Mutating user/job (technical).", "audit", 0.001, 0.0),
    ]


def _guid_column(rng: random.Random) -> Column:
    """A technical surrogate GUID — profiles flawlessly, is NEVER the business key."""
    return Column(
        "TECH_GUID", "char(36)",
        "Technical surrogate id (system-assigned). Not a business key — see the operational "
        "number column.",
        "guid", uniqueness=1.0, null_ratio=0.0,
        examples=tuple(_fake_guid(rng) for _ in range(2)),
    )


def _fake_guid(rng: random.Random) -> str:
    hexd = "0123456789abcdef"
    parts = [8, 4, 4, 4, 12]
    return "-".join("".join(rng.choice(hexd) for _ in range(n)) for n in parts)


def _false_friend_column() -> Column:
    """A column whose name tempts a lexical matcher but whose comment says otherwise."""
    return Column(
        "KD_NR", "varchar(6)",
        "Legacy Kreis-/Geschäftsstellencode (branch-office code). Historical misnomer — "
        "despite the KD_ (Kunde) prefix this is NOT a customer number; low cardinality.",
        "false_friend", uniqueness=0.00002, null_ratio=0.01, examples=("01", "07", "12"),
    )


def _bk_column(entity: EntityDef, system: str) -> Column:
    """The operational business-key column (the true key; carries a realistic null wart)."""
    if system == SYSTEM_CRM:
        return Column(
            entity.crm_col, "varchar(20)",
            f"CRM external reference for the {entity.key} ({entity.term}).",
            "bk", uniqueness=0.995, null_ratio=0.004, examples=("EXT-100234", "EXT-100987"),
        )
    return Column(
        entity.legacy_col, "varchar(12)",
        f"{entity.label_de}nummer — the operational id the legacy system keys on ({entity.term}).",
        "bk", uniqueness=0.998, null_ratio=0.002,
        examples=(f"{entity.legacy_col[:3]}000123", f"{entity.legacy_col[:3]}009987"),
    )


def _attr_columns(entity: EntityDef) -> list[Column]:
    cols = []
    for _term, name, typ, comment in entity.attrs:
        cols.append(Column(name, typ, comment, "attr", uniqueness=0.4, null_ratio=0.05))
    return cols


def _entity_table(entity: EntityDef, system: str, rng: random.Random, *, guid: bool) -> Table:
    prefix = _PREFIX_BY_SYSTEM[system]
    table = Table(
        name=f"{prefix}_{entity.key.upper()}",
        system=system,
        schema=_SCHEMA_BY_SYSTEM[system],
        entity=entity.key,
        kind="entity",
        row_count=rng.randrange(50_000, 3_000_000),
    )
    table.columns.append(_bk_column(entity, system))
    if guid:
        table.columns.append(_guid_column(rng))
    table.columns.extend(_attr_columns(entity))
    table.columns.extend(_audit_columns())
    return table


def _extra_entity_table(abbr: str, index: int, rng: random.Random) -> Table:
    """A breadth-noise legacy entity table (not golden-sampled)."""
    table = Table(
        name=f"VEKTRA_{abbr}",
        system=SYSTEM_LEGACY,
        schema=_SCHEMA_BY_SYSTEM[SYSTEM_LEGACY],
        entity=f"extra_{abbr.lower()}",
        kind="entity",
        row_count=rng.randrange(10_000, 2_000_000),
    )
    bk = Column(
        f"{abbr[:5]}_NR", "varchar(12)", f"{abbr.title()}-Nummer (operational id).",
        "bk", uniqueness=0.997, null_ratio=0.003, examples=(f"{abbr[:3]}00042",),
    )
    table.columns.append(bk)
    n_attrs = 3 + (index % 4)
    for a in range(n_attrs):
        table.columns.append(
            Column(
                f"{abbr[:4]}_ATTR_{a + 1:02d}", _TYPE_CYCLE[a % len(_TYPE_CYCLE)],
                None, "attr", uniqueness=0.3, null_ratio=0.1,
            )
        )
    table.columns.extend(_audit_columns())
    return table


def _relationship_table(
    left: Table, right: Table, index: int, rng: random.Random
) -> Table:
    """A junction/child table whose FK columns carry 'FK to <ANCHOR>' comments (WP9.1)."""
    left_key = left.columns[0]
    right_key = right.columns[0]
    table = Table(
        name=f"VEKTRA_{left.entity.upper()[:6]}_{right.entity.upper()[:6]}_{index:02d}",
        system=SYSTEM_LEGACY,
        schema=_SCHEMA_BY_SYSTEM[SYSTEM_LEGACY],
        entity=f"rel_{left.entity}_{right.entity}",
        kind="relationship",
        row_count=rng.randrange(100_000, 5_000_000),
    )
    table.columns.append(
        Column(
            left_key.name, left_key.type,
            f"FK to {left.name}.{left_key.name} ({left.entity}).",
            "fk", uniqueness=0.2, null_ratio=0.0,
        )
    )
    table.columns.append(
        Column(
            right_key.name, right_key.type,
            f"FK to {right.name}.{right_key.name} ({right.entity}).",
            "fk", uniqueness=0.2, null_ratio=0.0,
        )
    )
    table.columns.append(
        Column("GUELTIG_AB", "date", "Gültig-ab (relationship valid-from).", "attr", 0.6, 0.0)
    )
    table.columns.append(
        Column("GUELTIG_BIS", "date", "Gültig-bis (relationship valid-to; open = 9999-12-31).",
               "attr", 0.6, 0.4)
    )
    table.columns.extend(_audit_columns())
    return table


def _wide_table(anchor: Table, index: int, rng: random.Random) -> Table:
    """A wide detail/characteristics table (100–300 cols) to ride the width axis."""
    n_cols = rng.randrange(WIDE_MIN_COLS, WIDE_MAX_COLS + 1)
    anchor_key = anchor.columns[0]
    table = Table(
        name=f"VEKTRA_{anchor.entity.upper()[:6]}_MERKMALE_{index:02d}",
        system=SYSTEM_LEGACY,
        schema=_SCHEMA_BY_SYSTEM[SYSTEM_LEGACY],
        entity=f"wide_{anchor.entity}",
        kind="wide",
        row_count=rng.randrange(50_000, 2_000_000),
    )
    table.columns.append(
        Column(anchor_key.name, anchor_key.type,
               f"FK to {anchor.name}.{anchor_key.name} ({anchor.entity}).", "fk", 1.0, 0.0)
    )
    for c in range(n_cols):
        table.columns.append(
            Column(f"MERKMAL_{c + 1:03d}", _TYPE_CYCLE[c % len(_TYPE_CYCLE)],
                   None, "attr", uniqueness=0.3, null_ratio=0.2)
        )
    table.columns.extend(_audit_columns())
    return table


def generate_landscape(tables: int, seed: int) -> Landscape:
    """Build the in-memory landscape deterministically from ``(tables, seed)``."""
    if tables < 1:
        raise ValueError(f"--tables must be >= 1, got {tables}")
    rng = random.Random(seed)

    n_wide = round(tables * WIDE_FRACTION)
    n_rel = round(tables * RELATIONSHIP_FRACTION)
    n_entity = max(1, tables - n_wide - n_rel)

    built: list[Table] = []
    primary_present: dict[str, EntityDef] = {}
    multi_source: set[str] = set()

    # 1. Entity tables — primary catalog first (legacy), then breadth-noise extras.
    n_multi = round(len(BASE_ENTITIES) * MULTISOURCE_FRACTION)
    multi_slugs = {BASE_ENTITIES[i].key for i in range(n_multi)}
    slots_used = 0
    extra_idx = 0
    entity_index = 0
    while slots_used < n_entity:
        if entity_index < len(BASE_ENTITIES):
            entity = BASE_ENTITIES[entity_index]
            entity_index += 1
            guid = rng.random() < GUID_SHADOW_FRACTION
            built.append(_entity_table(entity, SYSTEM_LEGACY, rng, guid=guid))
            primary_present[entity.key] = entity
            slots_used += 1
            # A multi-source entity also appears in the CRM (differing key column → WP10 hub).
            if entity.key in multi_slugs and slots_used < n_entity:
                built.append(_entity_table(entity, SYSTEM_CRM, rng, guid=False))
                multi_source.add(entity.key)
                slots_used += 1
        else:
            abbr = _EXTRA_ENTITY_ABBR[extra_idx % len(_EXTRA_ENTITY_ABBR)]
            suffix = extra_idx // len(_EXTRA_ENTITY_ABBR)
            name_abbr = abbr if suffix == 0 else f"{abbr}_{suffix + 1}"
            built.append(_extra_entity_table(name_abbr, extra_idx, rng))
            extra_idx += 1
            slots_used += 1

    entity_tables = [t for t in built if t.kind == "entity"]

    # 2. Relationship tables — connect pairs of existing entity tables (FK-comment trap).
    for i in range(n_rel):
        left = entity_tables[i % len(entity_tables)]
        right = entity_tables[(i * 2 + 1) % len(entity_tables)]
        if right is left:
            right = entity_tables[(i + 1) % len(entity_tables)]
        built.append(_relationship_table(left, right, i, rng))

    # 3. Wide tables — hang off an entity as a characteristics table (width axis).
    for i in range(n_wide):
        anchor = entity_tables[(i * 3) % len(entity_tables)]
        built.append(_wide_table(anchor, i, rng))

    # 4. False-friend trap — seed a fraction of tables with the misleading branch-code column.
    n_ff = round(len(built) * FALSE_FRIEND_FRACTION)
    false_friends: list[tuple[str, str]] = []
    ff_stride = max(1, len(built) // n_ff) if n_ff else 0
    for i in range(n_ff):
        target = built[(i * ff_stride) % len(built)]
        ff = _false_friend_column()
        # Insert after the key so it looks like a plausible second identifier.
        target.columns.insert(1, ff)
        false_friends.append((target.name, ff.name))

    return Landscape(
        tables=built,
        entities=primary_present,
        multi_source=multi_source,
        false_friend_tables=false_friends,
        n_requested=tables,
        seed=seed,
    )


# ── serialisation (byte-deterministic) ────────────────────────────────────────────────────
def _dump_yaml(data: Any) -> str:
    """One stable YAML emitter for every artifact — insertion order preserved, wide wrap."""
    return yaml.safe_dump(
        data, sort_keys=False, default_flow_style=False, allow_unicode=True, width=100
    )


def render_source_schema(landscape: Landscape) -> str:
    tables = []
    for t in landscape.tables:
        cols = []
        for c in t.columns:
            entry: dict[str, Any] = {"name": c.name, "type": c.type}
            if c.comment is not None:
                entry["comment"] = c.comment
            cols.append(entry)
        tables.append({"table": t.name, "schema": t.schema, "columns": cols})
    header = (
        f"# Synthetic scale-test source schema — {len(landscape.tables)} tables across 3 "
        f"systems\n# Generated by eval.scale.generate (tables={landscape.n_requested}, "
        f"seed={landscape.seed}). Do not edit by hand.\n"
    )
    return header + _dump_yaml({"source_schemas": tables})


def render_profiling(landscape: Landscape) -> str:
    tables = []
    for t in landscape.tables:
        # Wide tables profile only their key/first columns to keep the file bounded; every
        # other table profiles all columns (the statistics trap lives in entity tables).
        cols_to_profile = t.columns[:3] if t.kind == "wide" else t.columns
        columns = []
        for c in cols_to_profile:
            if c.role == "audit":
                continue
            distinct = max(1, int(round(t.row_count * c.uniqueness)))
            entry: dict[str, Any] = {
                "name": c.name,
                "uniqueness_ratio": round(c.uniqueness, 6),
                "null_ratio": round(c.null_ratio, 6),
                "distinct_count": distinct,
            }
            if c.examples:
                entry["example_values"] = list(c.examples)
            columns.append(entry)
        tables.append({"table": t.name, "row_count": t.row_count, "columns": columns})
    header = (
        "# Synthetic scale-test profiling — plausible statistics, incl. the statistics trap\n"
        "# (technical GUID uniqueness 1.0 vs. the true key's realistic null wart).\n"
        f"# Generated by eval.scale.generate (tables={landscape.n_requested}, "
        f"seed={landscape.seed}). Do not edit by hand.\n"
    )
    return header + _dump_yaml({"tables": tables})


def _extra_entity_label(table: Table) -> tuple[str, str]:
    """A readable (label, business-term) for a breadth-noise entity table."""
    label = table.name.split("_", 1)[-1].replace("_", " ").title()
    return label, f"{label.lower()} number"


def render_requirements(landscape: Landscape) -> str:
    lines: list[str] = []
    lines.append("# Data Vault requirements — synthetic enterprise landscape\n")
    lines.append(
        f"This landscape spans {len(landscape.tables)} source tables across three systems: "
        "a legacy core system (VEKTRA), a CRM, and a peripheral system (AVIS). The business "
        "entities and their relationships to model are described below. The full physical "
        "schema (column names, types, comments) is supplied separately as the source schema; "
        "this document names the business concepts, not every physical table.\n"
    )
    lines.append("## Core business entities\n")
    for slug, entity in landscape.entities.items():
        multi = (
            f" It is mastered in both the legacy core and the CRM, where it is known as "
            f"'{entity.crm_col}'."
            if slug in landscape.multi_source else ""
        )
        attr_terms = ", ".join(a[0] for a in entity.attrs) or "core descriptive attributes"
        lines.append(
            f"- **{entity.label_de}** — each {entity.label_de.lower()} is identified by a "
            f"{entity.term}.{multi} We track {attr_terms} for each {entity.label_de.lower()}."
        )

    # The breadth-noise entity tables ARE additional business entities the model must cover;
    # naming them (compactly) is what makes the requirements grow with N — a real, parser-
    # legible increase, NOT an exhaustive physical-table dump.
    extra = [t for t in landscape.tables if t.kind == "entity" and t.entity.startswith("extra_")]
    if extra:
        lines.append("\n## Further business entities\n")
        for t in extra:
            label, term = _extra_entity_label(t)
            lines.append(f"- **{label}** — each {label.lower()} is identified by a {term}.")

    lines.append("\n## Relationships\n")
    for t in (t for t in landscape.tables if t.kind == "relationship"):
        parts = t.entity.split("_")
        left, right = parts[1], parts[-1]
        lines.append(
            f"- A {left} relates to a {right} over an active period (valid-from / valid-to); "
            f"model this as a link with its effectivity."
        )

    lines.append("\n## Derived measures (out of raw-vault scope)\n")
    for term, reason in GAP_CONCEPTS:
        lines.append(f"- **{term}** — {reason}.")

    return "\n".join(lines) + "\n"


def render_golden_mapping(landscape: Landscape) -> str:
    """Sample ~GOLDEN_SAMPLE_SIZE hand-verifiable concepts (WP9.2 universe), with the truth."""
    mappings: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    false_friends: list[dict[str, Any]] = []

    legacy_by_entity = {
        t.entity: t for t in landscape.tables if t.kind == "entity" and t.system == SYSTEM_LEGACY
    }
    crm_by_entity = {
        t.entity: t for t in landscape.tables if t.kind == "entity" and t.system == SYSTEM_CRM
    }

    budget = GOLDEN_SAMPLE_SIZE
    for slug, entity in landscape.entities.items():
        if budget <= 0:
            break
        legacy_table = legacy_by_entity.get(slug)
        if legacy_table is None:
            continue
        if slug in landscape.multi_source and slug in crm_by_entity:
            # Synonym trap → ambiguous: either the legacy or the CRM key is acceptable.
            ambiguous.append({
                "concept": entity.term,
                "entity": slug,
                "kind": "business_key",
                "candidates": [
                    {"table": legacy_table.name, "column": entity.legacy_col},
                    {"table": crm_by_entity[slug].name, "column": entity.crm_col},
                ],
            })
        else:
            mappings.append({
                "concept": entity.term,
                "entity": slug,
                "source_table": legacy_table.name,
                "source_column": entity.legacy_col,
                "kind": "business_key",
            })
        budget -= 1
        # One descriptive attribute per entity, while budget remains.
        if entity.attrs and budget > 0:
            term, col, _typ, _comment = entity.attrs[0]
            mappings.append({
                "concept": term,
                "entity": slug,
                "source_table": legacy_table.name,
                "source_column": col,
                "kind": "attribute",
            })
            budget -= 1

    for term, reason in GAP_CONCEPTS:
        gaps.append({"concept": term, "reason": reason, "kind": "attribute"})

    # False friends: the seeded misleading columns — no concept legitimately maps here.
    seen_ff: set[tuple[str, str]] = set()
    for table, column in landscape.false_friend_tables:
        if (table, column) in seen_ff:
            continue
        seen_ff.add((table, column))
        false_friends.append({
            "table": table, "column": column,
            "note": "legacy branch-office code despite the KD_ prefix; not a customer number",
        })

    header = (
        "# Synthetic scale-test golden mapping — sampled hand-verifiable concept universe\n"
        f"# (WP9.2 semantics: ~{GOLDEN_SAMPLE_SIZE} concepts, NOT all "
        f"{len(landscape.tables)} tables).\n"
        f"# Generated by eval.scale.generate (tables={landscape.n_requested}, "
        f"seed={landscape.seed}). Do not edit by hand.\n"
    )
    return header + _dump_yaml({
        "mappings": mappings,
        "ambiguous": ambiguous,
        "gaps": gaps,
        "false_friends": false_friends,
    })


def write_landscape(landscape: Landscape, out: Path) -> dict[str, Path]:
    """Write the four artifacts under ``out``; returns the written paths by kind."""
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "source_schema": out / "source_schema.yml",
        "profiling": out / "profiling.yml",
        "requirements": out / "requirements.md",
        "golden_mapping": out / "golden_mapping.yml",
    }
    files["source_schema"].write_text(render_source_schema(landscape), encoding="utf-8")
    files["profiling"].write_text(render_profiling(landscape), encoding="utf-8")
    files["requirements"].write_text(render_requirements(landscape), encoding="utf-8")
    files["golden_mapping"].write_text(render_golden_mapping(landscape), encoding="utf-8")
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m eval.scale.generate",
        description="Generate a deterministic synthetic source landscape (WP13 §2).",
    )
    parser.add_argument("--tables", type=int, required=True, help="number of source tables")
    parser.add_argument("--seed", type=int, required=True, help="RNG seed (byte-determinism)")
    parser.add_argument("--out", type=Path, required=True, help="output directory")
    args = parser.parse_args(argv)

    landscape = generate_landscape(args.tables, args.seed)
    files = write_landscape(landscape, args.out)

    req_len = len(files["requirements"].read_text(encoding="utf-8"))
    print(
        f"Wrote {len(landscape.tables)} tables to {args.out}/ "
        f"(entities={len(landscape.entities)}, multi-source={len(landscape.multi_source)}, "
        f"wide={sum(1 for t in landscape.tables if t.kind == 'wide')}, "
        f"relationships={sum(1 for t in landscape.tables if t.kind == 'relationship')}, "
        f"false-friends={len(landscape.false_friend_tables)})",
        file=sys.stderr,
    )
    print(
        f"requirements.md: {req_len} chars "
        f"({req_len / MAX_DOCUMENT_CHARS:.1%} of MAX_DOCUMENT_CHARS={MAX_DOCUMENT_CHARS})",
        file=sys.stderr,
    )
    if req_len >= 0.9 * MAX_DOCUMENT_CHARS:
        print(
            f"WARNING: requirements.md is within 10% of MAX_DOCUMENT_CHARS "
            f"({req_len}/{MAX_DOCUMENT_CHARS}); the WP3 input-size guard will truncate + flag "
            "at this landscape size — this is a measurement, not a bug.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
