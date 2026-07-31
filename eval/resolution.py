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
from vault_agent.state import (
    RESOLUTION_CLASSES,
    RESOLUTION_NEW,
    RESOLUTION_SAME_AS,
    RESOLUTION_UNRESOLVED,
    EntityResolution,
    ResolutionProposal,
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
