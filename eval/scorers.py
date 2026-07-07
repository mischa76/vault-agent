"""Deterministic scorers for eval runs (wp6-eval-harness-spec.md §4).

Pure functions ``(state, case) -> ScorerResult`` — keyless, no LLM, unit-tested like
everything else. Golden matching is *structural*, never textual: names, business keys,
connected-hub sets, driving-key sets, and attribute sets are compared through
``rules.normalize_identifier``, so ``"national customer ID"`` matches a generated
``NATIONAL_CUSTOMER_ID`` and construct names match regardless of label casing/spacing.
"""
from collections.abc import Callable, Iterable

from pydantic import BaseModel

from eval.datasets import EvalCase
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import VaultAgentState


class ScorerResult(BaseModel):
    """One scorer's verdict for one run: a 0..1 score plus a human-readable diagnosis."""

    name: str
    score: float  # 0.0 .. 1.0
    details: str


Scorer = Callable[[VaultAgentState, EvalCase], ScorerResult]


def _norm_set(labels: Iterable[str]) -> frozenset[str]:
    return frozenset(normalize_identifier(label) for label in labels)


def _f1(matched: int, n_generated: int, n_golden: int) -> float:
    """Harmonic mean of precision and recall; 1.0 when both sides are empty (vacuous)."""
    if n_golden == 0 and n_generated == 0:
        return 1.0
    if matched == 0:
        return 0.0
    precision = matched / n_generated
    recall = matched / n_golden
    return 2 * precision * recall / (precision + recall)


def _matched_hubs(state: VaultAgentState, case: EvalCase) -> int:
    """Golden hubs matched on normalised (name, business_key)."""
    generated = {
        normalize_identifier(hub.name): normalize_identifier(hub.business_key)
        for hub in state.dv_model.hubs
    }
    return sum(
        1
        for golden in case.golden.hubs
        if generated.get(normalize_identifier(golden.name))
        == normalize_identifier(golden.business_key)
    )


def _matched_links(state: VaultAgentState, case: EvalCase) -> int:
    """Golden links matched on normalised name + normalised connected-hub *set*."""
    generated = {
        normalize_identifier(link.name): _norm_set(link.connected_hubs)
        for link in state.dv_model.links
    }
    return sum(
        1
        for golden in case.golden.links
        if generated.get(normalize_identifier(golden.name)) == _norm_set(golden.connected_hubs)
    )


def _matched_satellites(state: VaultAgentState, case: EvalCase) -> int:
    """Golden satellites matched on normalised name + parent + sat_type; when the golden
    lists attributes, the normalised attribute set must match too."""
    generated = {
        normalize_identifier(sat.name): (
            normalize_identifier(sat.parent),
            sat.sat_type,
            _norm_set(sat.attributes),
        )
        for sat in state.dv_model.satellites
    }
    matched = 0
    for golden in case.golden.satellites:
        candidate = generated.get(normalize_identifier(golden.name))
        if candidate is None:
            continue
        parent, sat_type, attributes = candidate
        if parent != normalize_identifier(golden.parent) or sat_type != golden.sat_type:
            continue
        if golden.attributes is not None and attributes != _norm_set(golden.attributes):
            continue
        matched += 1
    return matched


def construct_f1(state: VaultAgentState, case: EvalCase) -> ScorerResult:
    """Mean F1 of generated vs golden constructs across the three construct kinds."""
    kinds = (
        ("hubs", _matched_hubs(state, case), len(state.dv_model.hubs), len(case.golden.hubs)),
        ("links", _matched_links(state, case), len(state.dv_model.links), len(case.golden.links)),
        (
            "satellites",
            _matched_satellites(state, case),
            len(state.dv_model.satellites),
            len(case.golden.satellites),
        ),
    )
    scores = [_f1(matched, n_gen, n_gold) for _, matched, n_gen, n_gold in kinds]
    details = "; ".join(
        f"{kind}: {matched}/{n_gold} golden matched, {n_gen} generated, F1={score:.2f}"
        for (kind, matched, n_gen, n_gold), score in zip(kinds, scores, strict=True)
    )
    return ScorerResult(name="construct_f1", score=sum(scores) / len(scores), details=details)


def driving_key_accuracy(state: VaultAgentState, case: EvalCase) -> ScorerResult:
    """Fraction of golden links with declared driving keys whose generated counterpart
    (matched on normalised name) declares the same normalised driving-key set."""
    golden_links = [link for link in case.golden.links if link.driving_key]
    if not golden_links:
        return ScorerResult(
            name="driving_key_accuracy",
            score=1.0,
            details="no golden driving keys declared",
        )
    generated = {
        normalize_identifier(link.name): _norm_set(link.driving_key)
        for link in state.dv_model.links
    }
    misses: list[str] = []
    for golden in golden_links:
        declared = generated.get(normalize_identifier(golden.name))
        if declared is None:
            misses.append(f"{golden.name}: no generated counterpart")
        elif declared != _norm_set(golden.driving_key):
            misses.append(
                f"{golden.name}: expected {sorted(_norm_set(golden.driving_key))}, "
                f"got {sorted(declared)}"
            )
    correct = len(golden_links) - len(misses)
    details = "; ".join(misses) if misses else f"all {correct} golden driving key(s) correct"
    return ScorerResult(
        name="driving_key_accuracy", score=correct / len(golden_links), details=details
    )


def validation_gate(state: VaultAgentState, case: EvalCase) -> ScorerResult:
    """1.0 iff the validation outcome matches ``expectations.validation_passed`` and the
    warning count stays within ``expectations.max_validation_warnings`` (when set)."""
    report = state.validation_report
    expected = case.expectations
    n_warnings = sum(1 for issue in report.issues if issue.severity == "warning")
    problems: list[str] = []
    if report.passed != expected.validation_passed:
        problems.append(f"validation passed={report.passed}, expected {expected.validation_passed}")
    tolerance = expected.max_validation_warnings
    if tolerance is not None and n_warnings > tolerance:
        problems.append(
            f"{n_warnings} warning(s) exceed the tolerance of {tolerance}"
        )
    if problems:
        return ScorerResult(name="validation_gate", score=0.0, details="; ".join(problems))
    return ScorerResult(
        name="validation_gate",
        score=1.0,
        details=f"passed={report.passed}, {n_warnings} warning(s) within tolerance",
    )


def pipeline_health(state: VaultAgentState, case: EvalCase) -> ScorerResult:
    """1.0 iff no agent raised a ``PipelineFlag`` with ``severity == "error"``."""
    errors = [flag for flag in state.flags if flag.severity == "error"]
    if not errors:
        return ScorerResult(name="pipeline_health", score=1.0, details="no error flags")
    details = "; ".join(
        f"{flag.agent}: {flag.kind}" + (f" ({flag.asset})" if flag.asset else "")
        for flag in errors
    )
    return ScorerResult(name="pipeline_health", score=0.0, details=details)


# All scorers, keyed by their result name — the runner applies every one of these and the
# min_scores gate looks thresholds up by the same key.
SCORERS: dict[str, Scorer] = {
    "construct_f1": construct_f1,
    "driving_key_accuracy": driving_key_accuracy,
    "validation_gate": validation_gate,
    "pipeline_health": pipeline_health,
}


def score_state(state: VaultAgentState, case: EvalCase) -> list[ScorerResult]:
    """Apply every scorer to one finished run."""
    return [scorer(state, case) for scorer in SCORERS.values()]
