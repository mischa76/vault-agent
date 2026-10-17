"""The product's one-line meanings for its typed codes (WP68 §2.3).

``GATES`` names every validator code the way the console explains it; ``FLAGS`` every
:class:`~vault_agent.state.FlagKind`. The manual (operations chapter 8) carries the history and
the reasoning; this is the short answer the code owns. Guarded against the validator's source,
the enum and the chapter — a code added anywhere without a line here fails the suite.
"""
from __future__ import annotations

from vault_agent.state import FlagKind

GATES: dict[str, str] = {
    # --- model-wide
    "E_NO_HUBS": "The model has no hubs — nothing to validate; the parser found no entities.",
    "E_DUP_NAME": "Two constructs share one name; a naming collision in the modeler's proposal.",
    "E_BAD_NAME": (
        "A construct name is not hub_/link_/sat_ plus lowercase snake_case — it becomes a dbt "
        "model name and a file."
    ),
    "E_MISSING_COLUMN": (
        "A generated construct lacks a DV-required column (hash key, load datetime, record "
        "source, hashdiff) — a generator defect, not a modelling one."
    ),
    # --- hubs
    "E_HUB_NO_BK": "A hub without a business key: the concept is not identifiable.",
    "E_DUP_HUB": (
        "The same business key on the same source entity in two or more hubs — one concept "
        "modelled twice; keep exactly one."
    ),
    "E_HUB_HK_COLLISION": (
        "Hubs share a source entity but differ in business key, so they would derive the same "
        "hash-key column and staging model."
    ),
    "E_HUB_DUP_FEED": "A multi-source hub declares the same (table, column) feed twice.",
    "E_HUB_COMPOSITE_UNSUPPORTED": (
        "A composite-key hub is multi-source or takes part in a link with a role, alias or "
        "translation — shapes that need per-column mechanisms not built yet."
    ),
    "E_HUB_PAYLOAD_UNREAD": (
        "A hub of this increment is built from a declared table whose payload columns no "
        "satellite reads — the vault would silently drop them."
    ),
    "W_HUB_NO_SAT": (
        "A hub has no satellite: no descriptive data captured; fine for a pure reference hub."
    ),
    "W_BK_COLLISION_RISK": (
        "Different source entities share one business-key name across hubs; a collision code "
        "may be needed before their values merge."
    ),
    # --- links
    "E_LINK_TOO_FEW_HUBS": (
        "A link connects fewer than two hub participations — usually a satellite in disguise."
    ),
    "E_LINK_UNKNOWN_HUB": "A link references a hub that is not in the model.",
    "E_LINK_DUP_ROLE": (
        "The same hub participates twice with the same (or no) role; qualify each repeat with "
        "a distinct role."
    ),
    "E_DRIVING_KEY_NOT_IN_LINK": (
        "The declared driving key names participations the link does not have."
    ),
    "E_TXNLINK_NO_TIMESTAMP": (
        "A transactional link without an event timestamp; t_link needs it to order events."
    ),
    "E_LINK_KEY_NOT_IN_SOURCE": (
        "A participation aliases or translates the hub's key to a column the bound relation "
        "does not declare."
    ),
    "E_LINK_KEY_WRONG_COLUMN": (
        "A participation is hashed from a column that carries the hub's key name while the "
        "relation declares its foreign key into that hub on another column — the link would "
        "join the wrong entity."
    ),
    "E_LINK_TRANSLATION_UNRATIFIED": (
        "A participation carries a surrogate-to-natural-key translation that no ratified link "
        "proposal produced."
    ),
    "W_LINK_REDUNDANT_GRAIN": (
        "Two links connect the same participations with the same type — one unit of work "
        "modelled twice, or a grain error."
    ),
    # --- satellites
    "E_SAT_UNKNOWN_PARENT": "A satellite's parent is neither a known hub nor a known link.",
    "E_SAT_NO_PAYLOAD": "A satellite with no attributes: nothing to historise.",
    "E_SAT_DUP_ATTR": (
        "Two attribute labels (or an attribute and a child dependent key) normalise to the "
        "same column."
    ),
    "E_SAT_ATTR_OVERLAP": (
        "The same attribute in several satellites of one parent fed by the same relation — "
        "one column historised twice; the remedy keeps one."
    ),
    "E_MASAT_NO_CDK": (
        "A multi-active satellite without a child dependent key: concurrent rows would be "
        "indistinguishable."
    ),
    "W_SAT_WIDE": (
        "More than 30 attributes — a smell for mixed rates of change, sources or "
        "classifications."
    ),
    "W_SAT_ATTR_OVERLAP_CROSS_SOURCE": (
        "The same attribute label in several satellites of one parent, each fed by a "
        "different relation — different columns, nothing collides, worth a look."
    ),
    "W_MASAT_SHARED_GRAIN": (
        "A multi-active satellite without its own source_table shares the parent's staging "
        "and assumes equal grain."
    ),
    "E_SAT_SOURCE_TABLE_ON_MULTI_SOURCE_HUB": (
        "A satellite on a multi-source hub (two or more feeds, WP75) names a source_table "
        "that is not one of the hub's feeds."
    ),
    "E_SAT_TRANSLATION_UNRATIFIED": (
        "A satellite carries a key translation that no ratified subtype feed, key license or "
        "link proposal produced."
    ),
    "E_STAGE_COLUMN_NOT_IN_SOURCE": (
        "A staging model is bound to a declared relation that does not carry a column it hashes "
        "or derives — the stage would fail at dbt build; the binding, not the model, is wrong."
    ),
    "E_SAT_KEY_NOT_IN_SOURCE": (
        "A satellite's declared relation lacks the column its parent's hash key is computed "
        "from; its stage would fail at dbt build. The remedy names re-parent candidates."
    ),
    # --- effectivity
    "E_EFFSAT_DATES": (
        "An effectivity satellite must carry exactly two date attributes (start, end)."
    ),
    "E_EFFSAT_DATE_ORDER": "The effectivity satellite's two dates are recognisably reversed.",
    "E_EFFSAT_NO_DRIVING_KEY": (
        "The parent link declares no driving key, so end-dating is undefined."
    ),
    "E_EFFSAT_PARENT_NOT_LINK": (
        "An effectivity satellite on a hub; active periods describe relationships and belong "
        "on the link."
    ),
    "W_EFFSAT_DATE_ORDER_UNVERIFIED": (
        "The date tokens match no known from/to vocabulary, so their order cannot be "
        "verified."
    ),
    "W_SAT_MAYBE_EFFECTIVITY": (
        "A standard satellite on a link carries a from/to date pair — probably a mis-modelled "
        "effectivity satellite."
    ),
    # --- grounding
    "W_BK_NOT_IN_SOURCE": "A hub's business key matches no declared column.",
    "W_HUBSOURCE_BK_NOT_IN_SOURCE": (
        "A multi-source feed's physical key column is not in the schema."
    ),
    "W_ROLE_BK_NOT_IN_SOURCE": (
        "A role-qualified participation expects a role-prefixed column the schema does not "
        "declare."
    ),
    "W_ATTR_NOT_IN_SOURCE": "A satellite attribute matches no declared column.",
    # --- brownfield
    "E_EXISTING_REMOVED": (
        "An existing hub, link or satellite is absent from the extended model; an extension "
        "never drops what the vault contains."
    ),
    "E_EXISTING_BK_CHANGED": (
        "An existing hub's business key or source entity changed — a migration, not an "
        "extension."
    ),
    "E_EXISTING_GRAIN_CHANGED": (
        "An existing link's grain (its participations, roles included) or driving key "
        "changed."
    ),
    "E_EXISTING_SAT_RESHAPED": (
        "An existing satellite changed parent, type, child dependent key, source table or "
        "attribute set; new attributes belong in a new satellite."
    ),
}

FLAGS: dict[str, str] = {
    FlagKind.MISSING_INPUT: "A stage ran without its required upstream output.",
    FlagKind.DROPPED_RECORD: "An invalid model record was dropped rather than guessed at.",
    FlagKind.COLUMN_COLLISION: "Two labels normalise to the same identifier; one needs renaming.",
    FlagKind.GENERATION_GAP: "A construct could not be generated and needs a hand.",
    FlagKind.OWNER_PLACEHOLDER: (
        "A contract still carries the placeholder owner; assign a real one (blocking)."
    ),
    FlagKind.UNDETERMINED_TYPE: "A contract field's type is unknown and needs one.",
    FlagKind.NO_SOURCE_SCHEMA: "The contract was inferred from prose, not from a declared schema.",
    FlagKind.SOURCE_BINDING: (
        "The staging relation was inferred rather than declared; an ambiguous binding is a "
        "decision."
    ),
    FlagKind.INPUT_TRUNCATED: "An oversized input document was cut to the size guard.",
    FlagKind.INPUT_SEGMENTED: "The document was extracted over several bounded calls.",
    FlagKind.MAPPING_GAP: "A concept has no in-scope source; it belongs downstream.",
    FlagKind.MAPPING_UNRESOLVED: "A concept's source is undecided; the human ratifies the mapping.",
    FlagKind.EXTENSION_CONFLICT: "The merger refused a re-statement of an existing construct.",
    FlagKind.RESOLUTION_UNRESOLVED: (
        "Is this an existing construct or a new one? Undecided — ratify at the checkpoint."
    ),
    FlagKind.RESOLUTION_SAME_AS: (
        "Asserted equivalent to an existing construct but differently keyed; ratify."
    ),
    FlagKind.LINK_TRANSLATION: (
        "A link participation joins through another relation (a surrogate-to-natural-key "
        "translation); ratify."
    ),
    FlagKind.SAT_TRANSLATION: (
        "A satellite joins through another relation (a key translation); ratify."
    ),
    FlagKind.LINK_RELATIONSHIP_INCOMPLETE: (
        "A proposed link's relationship could not be completed; decide it."
    ),
    FlagKind.LINK_PROPOSAL_SKIPPED: "The link proposer declined a candidate; nothing to answer.",
    FlagKind.RETIRED_REEMITTED: (
        "A retired construct came back in a later attempt and the backstop dropped it again."
    ),
    FlagKind.RETIRED_ORPHAN: (
        "A dependent of a retired construct lost its parent; its payload needs a home."
    ),
    FlagKind.RETIRED_REPARENTED: "A dropped hub's payload moved to its kept twin.",
    FlagKind.LINK_COLLAPSED: "A one-hub link was collapsed; its satellite moved to the hub.",
    FlagKind.RELATION_INFERRED: (
        "The declared schema named a satellite's relation where the model left it open."
    ),
    FlagKind.BINDING_REJECTED: (
        "A binding to a declared relation lacking a column the stage hashes was refused; the "
        "stage reads the inferred relation until a human maps it."
    ),
    FlagKind.GENERIC: "Untyped work for a human; not provenance.",
}
