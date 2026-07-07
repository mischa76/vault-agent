"""Typed loader for the golden eval datasets (wp6-eval-harness-spec.md §3).

One directory per case under ``eval/datasets/``, each with a ``dataset.yml`` holding the
input document, an optional declared source schema, the golden DV model, and tolerance
expectations. Loading is I/O plus pydantic validation — deterministic and key-free, in the
style of :func:`vault_agent.source_schema.load_source_schemas`: a malformed document raises
a clear, attributable ``ValueError`` naming the file and the problem.

Golden matching is *structural*, not textual: the scorers compare names and keys through
``rules.normalize_identifier`` (see :mod:`eval.scorers`), so golden values may be written
as business labels ("national customer ID") or identifiers (``NATIONAL_CUSTOMER_ID``).
"""
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

# Where the shipped cases live; the runner and tests discover cases here by default.
DATASETS_ROOT = Path(__file__).parent / "datasets"

DATASET_FILENAME = "dataset.yml"


class GoldenHub(BaseModel):
    """Expected hub: matched on normalised name *and* normalised business key."""

    name: str
    business_key: str


class GoldenLink(BaseModel):
    """Expected link: matched on normalised name *and* normalised connected-hub set.

    ``driving_key`` (optional) feeds the ``driving_key_accuracy`` scorer; it is not part
    of the ``construct_f1`` match."""

    name: str
    connected_hubs: list[str]
    driving_key: list[str] = Field(default_factory=list)


class GoldenSatellite(BaseModel):
    """Expected satellite: matched on normalised name, parent, and ``sat_type``.

    ``attributes`` may optionally be listed; the match then additionally requires the
    generated satellite's normalised attribute *set* to equal the golden one."""

    name: str
    parent: str
    sat_type: Literal["standard", "multi_active", "effectivity"] = "standard"
    attributes: list[str] | None = None


class GoldenModel(BaseModel):
    hubs: list[GoldenHub] = Field(default_factory=list)
    links: list[GoldenLink] = Field(default_factory=list)
    satellites: list[GoldenSatellite] = Field(default_factory=list)


class Expectations(BaseModel):
    """Tolerances, not exactness: LLM output varies between runs (see docs/demos/README)."""

    validation_passed: bool = True
    # None = no warning-count gate; otherwise the validation_gate scorer fails the case
    # when the run produced more warnings than this.
    max_validation_warnings: int | None = None
    # Optional per-scorer minimum *mean* scores: the live runner exits non-zero when a
    # mean falls below its threshold (a manual pre-release gate, spec §5).
    min_scores: dict[str, float] = Field(default_factory=dict)


class EvalCase(BaseModel):
    """One golden eval case. ``input_document``/``source_schema`` are resolved to absolute
    paths (relative paths in ``dataset.yml`` are taken relative to the file itself)."""

    name: str
    input_document: Path
    source_schema: Path | None = None
    golden: GoldenModel
    expectations: Expectations = Field(default_factory=Expectations)


def _resolve_existing(base: Path, candidate: Path, field: str, source: Path) -> Path:
    """Resolve ``candidate`` against ``base`` and require it to exist (attributable)."""
    resolved = (base / candidate).resolve()
    if not resolved.is_file():
        raise ValueError(f"{source}: {field} '{candidate}' does not exist (resolved to {resolved})")
    return resolved


def load_eval_case(path: Path) -> EvalCase:
    """Load one ``dataset.yml`` into a typed :class:`EvalCase`.

    Raises ``FileNotFoundError`` if the file is missing and a clear ``ValueError`` naming
    the file and the problem for malformed YAML, an invalid case, or a dangling
    ``input_document``/``source_schema`` reference."""
    raw = path.read_text(encoding="utf-8")
    try:
        document: Any = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: not valid YAML ({exc})") from exc

    if not isinstance(document, dict):
        raise ValueError(
            f"{path}: expected a mapping with name/input_document/golden, "
            f"got {type(document).__name__}"
        )
    try:
        case = EvalCase.model_validate(document)
    except ValidationError as exc:
        raise ValueError(f"{path}: invalid eval case: {exc}") from exc

    case.input_document = _resolve_existing(
        path.parent, case.input_document, "input_document", path
    )
    if case.source_schema is not None:
        case.source_schema = _resolve_existing(
            path.parent, case.source_schema, "source_schema", path
        )
    return case


def load_all_cases(root: Path = DATASETS_ROOT) -> list[EvalCase]:
    """Load every ``<root>/<dir>/dataset.yml``, sorted by directory name.

    Case names must be unique (they key result directories and LangSmith datasets)."""
    cases: list[EvalCase] = []
    seen: dict[str, Path] = {}
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        dataset = directory / DATASET_FILENAME
        if not dataset.is_file():
            continue
        case = load_eval_case(dataset)
        if case.name in seen:
            raise ValueError(
                f"{dataset}: duplicate case name '{case.name}' (already used by {seen[case.name]})"
            )
        seen[case.name] = dataset
        cases.append(case)
    return cases
