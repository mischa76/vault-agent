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
from pydantic import BaseModel, Field, ValidationError, model_validator

# Where the shipped cases live; the runner and tests discover cases here by default.
DATASETS_ROOT = Path(__file__).parent / "datasets"

DATASET_FILENAME = "dataset.yml"

# The golden-mapping filename a case ships (or a generated case materialises); mirrored from
# eval.mapping.GOLDEN_MAPPING_FILENAME, kept local to avoid an import cycle at module load.
GOLDEN_MAPPING_FILENAME = "golden_mapping.yml"

# Mapping scorers keyed on the proposal's *concept* name (WP9/WP9.2). In "column"
# mapping_match mode the modeler's free-form names diverge from the golden vocabulary, so
# these become blind — reported but never a gate (WP14 §2.4). load_eval_case rejects a
# column-mode case that names any of them in expectations.min_scores.
_CONCEPT_COUPLED_SCORERS = frozenset(
    {"mapping_accuracy", "gap_detection", "confidence_calibration"}
)


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


class GenerateSpec(BaseModel):
    """A generated case (WP13): the inputs are synthesised on demand from ``(tables, seed)``
    by ``eval.scale.generate`` instead of committed, so the large scale steps (100/300) do
    not check hundreds of KB of synthetic YAML into the repo."""

    tables: int
    seed: int


class EvalCase(BaseModel):
    """One golden eval case. ``input_document``/``source_schema``/``profiling`` are resolved
    to absolute paths (relative paths in ``dataset.yml`` are taken relative to the file
    itself) for a committed case; a ``generate`` case leaves them unset until
    :func:`materialize_case` synthesises them. Exactly one of ``input_document`` / ``generate``
    must be given."""

    name: str
    input_document: Path | None = None
    source_schema: Path | None = None
    profiling: Path | None = None
    generate: GenerateSpec | None = None
    golden: GoldenModel
    expectations: Expectations = Field(default_factory=Expectations)
    # How the WP9 mapping scorers judge this case (WP14). "concept" (default) is the
    # name-aligned WP9/WP9.2 behaviour (bank/messy_insurance). "column" is the scale mode:
    # pair-based mapping_coverage + false_friend_hits, with the concept-coupled scorers
    # reported-only (and non-gateable — enforced in load_eval_case).
    mapping_match: Literal["concept", "column"] = "concept"

    @model_validator(mode="after")
    def _exactly_one_input_source(self) -> "EvalCase":
        if (self.input_document is None) == (self.generate is None):
            raise ValueError(
                "provide exactly one of 'input_document' (committed case) or 'generate' "
                "(synthesised case)"
            )
        if self.generate is not None and (
            self.source_schema is not None or self.profiling is not None
        ):
            raise ValueError(
                "a 'generate' case must not also declare 'source_schema'/'profiling' "
                "(they are synthesised)"
            )
        return self


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

    # A column-mode case must not gate a concept-coupled mapping scorer: those measure naming
    # alignment, not mapping quality, and are reported-only at scale (WP14 §2.4). Fail loudly
    # (house loader style: name the file, the field, and why) rather than silently gate a
    # score that cannot mean what the author intends.
    if case.mapping_match == "column":
        gated = sorted(set(case.expectations.min_scores) & _CONCEPT_COUPLED_SCORERS)
        if gated:
            raise ValueError(
                f"{path}: mapping_match='column' must not gate concept-coupled scorer(s) "
                f"{gated} in expectations.min_scores — they are reported-only at scale "
                f"(WP14); gate 'mapping_coverage'/'false_friend_hits' instead"
            )

    # A generated case leaves the input paths unset; they are synthesised by
    # materialize_case(). A committed case resolves them to existing files now.
    if case.generate is None:
        assert case.input_document is not None  # guaranteed by the model validator
        case.input_document = _resolve_existing(
            path.parent, case.input_document, "input_document", path
        )
        if case.source_schema is not None:
            case.source_schema = _resolve_existing(
                path.parent, case.source_schema, "source_schema", path
            )
        if case.profiling is not None:
            case.profiling = _resolve_existing(path.parent, case.profiling, "profiling", path)
    return case


def materialize_case(case: EvalCase, workdir: Path) -> tuple[EvalCase, Path | None]:
    """Resolve a case to concrete input files, synthesising a ``generate`` case on demand.

    For a committed case this is a near no-op: it returns the case unchanged plus the path to
    its shipped ``golden_mapping.yml`` (or ``None`` if it ships none). For a WP13 ``generate``
    case it runs :func:`eval.scale.generate.write_landscape` into ``workdir`` and returns a
    copy of the case bound to the synthesised ``requirements.md``/``source_schema.yml``/
    ``profiling.yml`` plus the synthesised ``golden_mapping.yml``. Deterministic: the same
    ``(tables, seed)`` yields byte-identical inputs (WP13 §2)."""
    if case.generate is None:
        golden = DATASETS_ROOT / case.name / GOLDEN_MAPPING_FILENAME
        return case, (golden if golden.is_file() else None)

    # Lazy import: keeps the loader light and the eval → src dependency direction explicit.
    from eval.scale.generate import generate_landscape, write_landscape

    landscape = generate_landscape(case.generate.tables, case.generate.seed)
    files = write_landscape(landscape, workdir)
    resolved = case.model_copy(
        update={
            "input_document": files["requirements"],
            "source_schema": files["source_schema"],
            "profiling": files["profiling"],
        }
    )
    return resolved, files["golden_mapping"]


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
