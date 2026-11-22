"""Typed result + golden model for the business↔source mapping spike (charter D1/D2).

The mapping prototypes (``spike/``, throwaway) emit a :class:`ProposedMapping`; the
deterministic scorers in :mod:`eval.scorers` consume it against a :class:`GoldenMapping`
loaded from ``eval/datasets/<case>/golden_mapping.yml``.

Both the result shape and the golden loader are **permanent eval assets** (charter §3 D2,
the prototypes are not). Whether ``ProposedMapping`` holds up as the WP9 pipeline state
model is memo question §7 Q3, so it is written as a real typed contract, not a scratch dict.

Loading follows the WP6 dataset-loader convention (:func:`eval.datasets.load_eval_case` /
:func:`vault_agent.source_schema.load_source_schemas`): I/O + pydantic validation, a
malformed file raises a clear ``ValueError`` naming the file and the problem. All matching
downstream is *structural* through :func:`vault_agent.rules.normalize_identifier`.
"""
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

# The prototypes' / agent's output shape is the promoted state model (WP9 §5): one definition
# for the pipeline (state.mappings) and the scorers, re-exported here for the spike's callers.
from vault_agent.state import Proposal, ProposedMapping

__all__ = ["Proposal", "ProposedMapping"]

ConceptKind = Literal["business_key", "attribute"]


# ── The golden ground truth (loaded from golden_mapping.yml) ────────────────────────────
class GoldenCandidate(BaseModel):
    table: str
    column: str


class GoldenMappingEntry(BaseModel):
    """A concept with exactly one correct (table, column)."""

    concept: str
    entity: str | None = None
    source_table: str
    source_column: str
    kind: ConceptKind = "attribute"


class AmbiguousEntry(BaseModel):
    """A concept with several legitimate sources — ANY listed candidate scores correct."""

    concept: str
    entity: str | None = None
    candidates: list[GoldenCandidate]
    # Reference concepts behave like keys for the BK-plausibility heuristic (variant A).
    kind: ConceptKind = "business_key"


class GapEntry(BaseModel):
    """A concept with no in-scope source — the correct answer is 'gap', never a proposal."""

    concept: str
    reason: str = ""
    entity: str | None = None
    kind: ConceptKind = "attribute"


class FalseFriend(BaseModel):
    """A column a lexical matcher is tempted by, but which NO concept legitimately maps to."""

    table: str
    column: str
    note: str = ""


class GoldenMapping(BaseModel):
    mappings: list[GoldenMappingEntry] = Field(default_factory=list)
    ambiguous: list[AmbiguousEntry] = Field(default_factory=list)
    gaps: list[GapEntry] = Field(default_factory=list)
    false_friends: list[FalseFriend] = Field(default_factory=list)


class ConceptRef(BaseModel):
    """One unit of work handed to a prototype — deliberately WITHOUT the answer.

    The prototype receives concept + entity + kind (all known in the real pipeline: the
    modeler has already classified the construct) and must find its source or call it a
    gap. It must NOT be able to tell mappable concepts from gaps by position or shape."""

    concept: str
    entity: str | None = None
    kind: ConceptKind = "attribute"


GOLDEN_MAPPING_FILENAME = "golden_mapping.yml"


def load_golden_mapping(path: Path) -> GoldenMapping:
    """Load one ``golden_mapping.yml`` into a typed :class:`GoldenMapping`.

    Raises ``FileNotFoundError`` if missing, and a clear ``ValueError`` naming the file for
    malformed YAML or an invalid document (same contract as the WP6 loaders)."""
    raw = path.read_text(encoding="utf-8")
    try:
        document: Any = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: not valid YAML ({exc})") from exc
    if document is None:
        document = {}
    if not isinstance(document, dict):
        raise ValueError(
            f"{path}: expected a mapping with mappings/ambiguous/gaps/false_friends, "
            f"got {type(document).__name__}"
        )
    try:
        return GoldenMapping.model_validate(document)
    except ValidationError as exc:
        raise ValueError(f"{path}: invalid golden mapping: {exc}") from exc


def concepts_for_prototype(golden: GoldenMapping) -> list[ConceptRef]:
    """The concept work-list handed to both prototypes — mappable and gap concepts mixed.

    Sorted by (entity, concept) so gaps do not cluster at the end and betray themselves;
    deterministic so repeated runs are comparable. Duplicate concept labels (a concept that
    is both mappable and, say, ambiguous) are not expected and the first wins."""
    refs: dict[str, ConceptRef] = {}
    for m in golden.mappings:
        refs.setdefault(m.concept, ConceptRef(concept=m.concept, entity=m.entity, kind=m.kind))
    for a in golden.ambiguous:
        refs.setdefault(a.concept, ConceptRef(concept=a.concept, entity=a.entity, kind=a.kind))
    for g in golden.gaps:
        refs.setdefault(g.concept, ConceptRef(concept=g.concept, entity=g.entity, kind=g.kind))
    return sorted(refs.values(), key=lambda r: ((r.entity or ""), r.concept))
