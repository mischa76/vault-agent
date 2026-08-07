"""Typed golden set + proposal shape for entity resolution (brownfield Phase 2 spike, D1/D2).

Mirrors :mod:`eval.mapping` (WP9's spike assets), which survived its spike because it is an
eval asset rather than prototype code. The same is intended here: the loader, the result
shape and the scorers outlive whatever mechanism the spike ends up recommending — or not
recommending.

The one thing that is deliberately NOT like the mapping spike is the class asymmetry. See
:data:`RESOLUTION_CLASSES` and the charter's §2: a false merge feeds foreign business keys
into a hub that holds live history, while a miss in the other direction costs a redundant
hub someone deletes at the checkpoint. The scorers keep the two apart and never average
them.
"""
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

# WP29 promoted the proposal shape into the product (state.py) — the answer the pipeline
# produces and the answer a scorer reads must be ONE type, or the eval measures something the
# product does not emit. Re-exported here so the eval assets keep their own import surface,
# exactly as eval/mapping.py does for WP9's Proposal.
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import (
    RESOLUTION_CLASSES,
    RESOLUTION_NEW,
    RESOLUTION_SAME_AS,
    RESOLUTION_UNRESOLVED,
    EntityResolution,
    ResolutionProposal,
    split_concept_key,
)

# Explicit re-export surface: strict mypy does not treat an import as an export, and these
# names ARE this module's public vocabulary for the scorers and the golden loader.
__all__ = [
    "NEW",
    "RESOLUTION_CLASSES",
    "SAME_AS",
    "UNRESOLVED",
    "GoldenConstruct",
    "GoldenResolution",
    "GoldenResolutionSet",
    "ProposedResolution",
    "ResolutionResult",
    "load_golden_resolution",
    "key_ref",
    "proposals_by_key",
]

# The vocabulary lives in the product; these aliases keep the eval-side names readable.
NEW = RESOLUTION_NEW
SAME_AS = RESOLUTION_SAME_AS
UNRESOLVED = RESOLUTION_UNRESOLVED


class GoldenResolution(BaseModel):
    """One expected answer, with the trap class it belongs to."""

    concept: str
    source_table: str
    source_key: str
    expected: str  # an existing construct name, or NEW / same_as_candidate
    trap: str = ""
    same_as: str | None = None  # the construct the same-as candidate corresponds to
    rationale: str = ""


class GoldenConstruct(BaseModel):
    name: str
    business_key: str


class GoldenResolutionSet(BaseModel):
    existing_constructs: list[GoldenConstruct] = Field(default_factory=list)
    resolutions: list[GoldenResolution] = Field(default_factory=list)

    def by_concept(self) -> dict[str, GoldenResolution]:
        return {entry.concept: entry for entry in self.resolutions}

    def by_key(self) -> dict[str, GoldenResolution]:
        """Keyed on the normalised **business-key column** — the WP29.2 anchor.

        The golden's judgement is about a key's VALUE SPACE, not about a table: "partn_nr is the
        national customer ID and belongs to hub_customer" holds wherever that column appears.
        Grounded rather than assumed — every multi-table occurrence in this case is a foreign
        key to its primary occurrence, and the column comments say so
        (``vic_kontakt.partn_nr`` "FK auf vic_partner.partn_nr", ``vic_vertrag.vp_nummer``,
        ``crm_xref_partner.crm_guid``). A foreign key shares its target's value space by
        definition.

        **When this stops being true**, and the next author must check it: a golden whose
        ``source_key`` is a GENERIC label — ``name``, ``id``, ``code``. WP24 found exactly that
        in AdventureWorks, where three unrelated reference tables were keyed on ``Name``, and
        matching those across tables would fold three concepts into one. This case has no such
        key; :func:`load_golden_resolution` asserts the keys are distinct, which is the cheap
        half of the protection. The expensive half — declaring per entry whether the judgement
        is value-space or table-scoped — is deliberately deferred until a dataset needs it,
        because a field with one possible value is ceremony, not a safeguard."""
        return {normalize_identifier(e.source_key): e for e in self.resolutions}



# One definition, two names: the scorers were written against these, the pipeline emits the
# state models. Aliases rather than subclasses so an object crosses the boundary unchanged.
ProposedResolution = ResolutionProposal
ResolutionResult = EntityResolution


def load_golden_resolution(path: Path) -> GoldenResolutionSet:
    """Load a golden resolution set; attributable errors in the house loader style."""
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"{path}: could not be read ({exc})") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: not valid YAML ({exc})") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a mapping, got {type(raw).__name__}")
    try:
        golden = GoldenResolutionSet.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"{path}: not a valid golden resolution set ({exc})") from exc
    if not golden.resolutions:
        raise ValueError(f"{path}: declares no resolutions — nothing to score")

    # WP29.2: the business-key column is the ANCHOR the scorers match on, so it has to identify
    # an entry uniquely. Enforced at load rather than trusted: a golden that later gains a
    # colliding key must fail loudly here instead of silently scoring two concepts as one.
    seen: dict[str, str] = {}
    for entry in golden.resolutions:
        key = normalize_identifier(entry.source_key)
        if key in seen:
            raise ValueError(
                f"{path}: source_key {entry.source_key!r} identifies both {seen[key]!r} and "
                f"{entry.concept!r}. The scorers match on the key column, so it must be unique "
                f"across the golden — give the two concepts distinct keys, or the case needs "
                f"table-scoped matching (see GoldenResolutionSet.by_key)"
            )
        seen[key] = entry.concept
    known = {c.name for c in golden.existing_constructs}
    for entry in golden.resolutions:
        target = entry.expected
        if target not in RESOLUTION_CLASSES and target not in known:
            raise ValueError(
                f"{path}: concept {entry.concept!r} expects {target!r}, which is neither a "
                f"declared existing construct {sorted(known)} nor one of {RESOLUTION_CLASSES}"
            )
        if entry.expected == SAME_AS and entry.same_as not in known:
            raise ValueError(
                f"{path}: concept {entry.concept!r} is a same-as candidate but its "
                f"`same_as` target {entry.same_as!r} is not a declared existing construct"
            )
    return golden


def key_ref(concept_key: str) -> str:
    """The normalised business-key column from a pipeline concept key (WP29.2 anchor).

    The pipeline emits ``business_entity::column`` — and the business entity is the name the
    MODEL gave the concept from the requirements text (``partner``), not the physical table
    (``vic_partner``). The binding between the two is the source mapper's output, and that node
    runs AFTER the resolver, so at resolution time no physical table exists to match on.

    Measured on the 2026-08-01 probe: the column half matched 7/7, the table half 0/7. Hence the
    key column is the join. See :meth:`GoldenResolutionSet.by_key` for the semantic claim this
    rests on and for when it stops holding."""
    field, _entity = split_concept_key(concept_key)
    return normalize_identifier(field)


def proposals_by_key(
    result: ResolutionResult,
) -> dict[str, list[ResolutionProposal]]:
    """Proposals grouped by key column — a LIST per key, never one winner.

    Several proposals can concern the same key: the probe answered for both ``crm_kunde`` and
    the xref table's occurrence of ``crm_guid``, and they disagreed. Collapsing them into a dict
    would silently drop one of the two — and in that run it would have dropped the false merge,
    which is the one thing this instrument exists to catch."""
    grouped: dict[str, list[ResolutionProposal]] = {}
    for proposal in result.proposals:
        grouped.setdefault(key_ref(proposal.concept), []).append(proposal)
    return grouped
