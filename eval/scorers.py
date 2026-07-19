"""Deterministic scorers for eval runs (wp6-eval-harness-spec.md §4).

Pure functions ``(state, case) -> ScorerResult`` — keyless, no LLM, unit-tested like
everything else. Golden matching is *structural*, never textual: names, business keys,
connected-hub sets, driving-key sets, and attribute sets are compared through
``rules.normalize_identifier``, so ``"national customer ID"`` matches a generated
``NATIONAL_CUSTOMER_ID`` and construct names match regardless of label casing/spacing.
"""
from collections.abc import Callable, Iterable
from typing import Literal

from pydantic import BaseModel

from eval.datasets import EvalCase
from eval.mapping import GoldenMapping, ProposedMapping
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
        # Match on the set of connected hub names; role-qualified participations
        # (ADR-0009) collapse to their hub for this structural comparison.
        normalize_identifier(link.name): _norm_set(ref.hub for ref in link.hub_refs)
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


# ── Mapping scorers (spike D2) ──────────────────────────────────────────────────────────
# A separate family from the pipeline scorers above: these score a ``ProposedMapping``
# (from a spike prototype) against a ``GoldenMapping``, not a ``VaultAgentState``. They are
# permanent eval assets (charter §3 D2) even though the prototypes that feed them are not.
# Matching is structural through ``normalize_identifier`` on concept, table, and column.
MappingScorer = Callable[[ProposedMapping, GoldenMapping], ScorerResult]


def _norm_pair(table: str, column: str) -> tuple[str, str]:
    return (normalize_identifier(table), normalize_identifier(column))


def _acceptable_pairs(golden: GoldenMapping) -> dict[str, set[tuple[str, str]]]:
    """Normalised concept → the set of (table, column) pairs that score correct.

    A plain mapping contributes one pair; an ``ambiguous`` concept contributes one per
    listed candidate (any of them is correct)."""
    out: dict[str, set[tuple[str, str]]] = {}
    for m in golden.mappings:
        out.setdefault(normalize_identifier(m.concept), set()).add(
            _norm_pair(m.source_table, m.source_column)
        )
    for a in golden.ambiguous:
        bucket = out.setdefault(normalize_identifier(a.concept), set())
        for candidate in a.candidates:
            bucket.add(_norm_pair(candidate.table, candidate.column))
    return out


def _gap_concepts(golden: GoldenMapping) -> set[str]:
    return {normalize_identifier(g.concept) for g in golden.gaps}


def _golden_universe(golden: GoldenMapping) -> set[str]:
    """The normalised concepts the golden mapping actually covers (WP9.2): mappings + gaps +
    ambiguous. The live pipeline maps the *generated* model's concepts, which routinely
    include constructs the golden set does not judge (the bank modeler adds
    transactions/addresses); those must not be scored as wrong — only concepts in this
    universe are scored."""
    return (
        {normalize_identifier(m.concept) for m in golden.mappings}
        | _gap_concepts(golden)
        | {normalize_identifier(a.concept) for a in golden.ambiguous}
    )


def _false_friend_pairs(golden: GoldenMapping) -> set[tuple[str, str]]:
    return {_norm_pair(f.table, f.column) for f in golden.false_friends}


def mapping_accuracy(proposed: ProposedMapping, golden: GoldenMapping) -> ScorerResult:
    """F1 over proposed ``concept → (table, column)`` pairs vs. the golden mappings.

    Only proposals whose concept is in the **golden universe** (``mappings`` + ``gaps`` +
    ``ambiguous``, WP9.2) are scored: the live pipeline maps the generated model's concepts,
    and constructs the golden set does not cover must not count as wrong. The precision
    denominator is the *scored* proposals; recall is over the mappable concepts (``mappings``
    + ``ambiguous``), an ``ambiguous`` concept scoring for any listed candidate. A force-fit
    of a gap concept or a false-friend column still costs score (both are in the universe).
    Out-of-universe proposals are reported, not penalised."""
    acceptable = _acceptable_pairs(golden)
    false_friends = _false_friend_pairs(golden)
    universe = _golden_universe(golden)
    n_mappable = len(acceptable)

    scored = [p for p in proposed.proposals if normalize_identifier(p.concept) in universe]
    out_of_universe = len(proposed.proposals) - len(scored)

    correct_proposals = 0
    correct_concepts: set[str] = set()
    ff_hits: list[str] = []
    for p in scored:
        cnorm = normalize_identifier(p.concept)
        pair = _norm_pair(p.table, p.column)
        if cnorm in acceptable and pair in acceptable[cnorm]:
            correct_proposals += 1
            correct_concepts.add(cnorm)
        if pair in false_friends:
            ff_hits.append(f"{p.concept} → {p.table}.{p.column}")

    if n_mappable == 0 and not scored:
        details = "no mappable concepts"
        if out_of_universe:
            details += f"; {out_of_universe} proposals outside the golden universe, unscored"
        return ScorerResult(name="mapping_accuracy", score=1.0, details=details)
    precision = correct_proposals / len(scored) if scored else 0.0
    recall = len(correct_concepts) / n_mappable if n_mappable else 0.0
    f1 = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)

    details = (
        f"F1={f1:.2f} (precision={precision:.2f} {correct_proposals}/{len(scored)}, "
        f"recall={recall:.2f} {len(correct_concepts)}/{n_mappable})"
    )
    if out_of_universe:
        details += f"; {out_of_universe} proposals outside the golden universe, unscored"
    if ff_hits:
        details += f"; FALSE-FRIEND HIT(S): {', '.join(ff_hits)}"
    return ScorerResult(name="mapping_accuracy", score=f1, details=details)


def gap_detection(
    proposed: ProposedMapping, golden: GoldenMapping, *, reported_only: bool = False
) -> ScorerResult:
    """Recall over golden gaps: fraction of no-source concepts correctly called a gap.

    A golden gap that got *mapped* anywhere (force-fit) is the worst failure mode and is
    named in the details (charter §5). Concepts parked in ``unresolved`` are honest
    non-answers — they lower recall but are not force-fits.

    Both halves (gap recall and the force-fit check) are keyed on the proposal's *concept*
    name, so in the scale cases' column mode — where the modeler's free-form concept names
    diverge from the golden's vocabulary (WP14) — this scorer is blind. ``reported_only``
    prefixes the details to mark the score non-gateable there; the loader rejects a
    column-mode case that gates it (``datasets.load_eval_case``)."""
    prefix = "concept-coupled — reported only in column mode; " if reported_only else ""
    gap_concepts = _gap_concepts(golden)
    if not gap_concepts:
        return ScorerResult(name="gap_detection", score=1.0, details=prefix + "no golden gaps")

    proposed_gaps = {normalize_identifier(g) for g in proposed.gaps}
    proposed_concepts = {normalize_identifier(p.concept) for p in proposed.proposals}
    caught = gap_concepts & proposed_gaps
    force_fit = sorted(gap_concepts & proposed_concepts)
    recall = len(caught) / len(gap_concepts)

    details = f"{prefix}gap recall={recall:.2f} ({len(caught)}/{len(gap_concepts)})"
    if force_fit:
        # Report using the original concept labels for readability.
        labels = [g.concept for g in golden.gaps if normalize_identifier(g.concept) in force_fit]
        details += f"; FORCE-FIT (mapped a gap): {', '.join(labels)}"
    return ScorerResult(name="gap_detection", score=recall, details=details)


# ── Column-based mapping scorers (WP14) ───────────────────────────────────────────────────
# The scale cases (WP13) feed the *generated* model's free-form concept names, which diverge
# almost entirely from the golden's sampled vocabulary — so concept-keyed mapping_accuracy
# measures naming alignment, not mapping quality (scale-test-findings.md Candidate #2). These
# two scorers judge the mapper on its actual job — binding the right physical column — by
# matching normalised (table, column) pairs, with no concept or entity coupling.
def mapping_coverage(proposed: ProposedMapping, golden: GoldenMapping) -> ScorerResult:
    """Column-based recall: fraction of golden mappable entries whose ``(table, column)`` pair
    is bound by *some* proposal (an ``ambiguous`` entry is covered by any listed candidate).

    Deliberately pair-only — no ``entity`` coupling (entity naming diverges exactly like
    concept naming) and no synthetic precision/F1 (naming it ``mapping_coverage`` keeps the
    honest semantics visible in every result JSON and gate). The statistics trap survives:
    binding the shadow GUID is a different pair, so it never covers the real key. Proposals
    binding a column outside the golden mappable set are counted and reported, never penalised
    (WP9.2 tradition)."""
    acceptable = _acceptable_pairs(golden)  # normalised concept → set of acceptable pairs
    n_mappable = len(acceptable)
    proposed_pairs = {_norm_pair(p.table, p.column) for p in proposed.proposals}
    golden_pairs = {pair for pairs in acceptable.values() for pair in pairs}
    out_of_golden = sum(
        1 for p in proposed.proposals if _norm_pair(p.table, p.column) not in golden_pairs
    )

    if n_mappable == 0:
        details = "no mappable golden entries"
        if out_of_golden:
            details += f"; {out_of_golden} proposal(s) outside the golden column set, unscored"
        return ScorerResult(name="mapping_coverage", score=1.0, details=details)

    recalled = 0
    missed: list[str] = []
    for pairs in acceptable.values():
        if proposed_pairs & pairs:
            recalled += 1
        else:
            missed.append("|".join(f"{table}.{column}" for table, column in sorted(pairs)))
    score = recalled / n_mappable
    details = f"coverage={score:.2f} ({recalled}/{n_mappable} golden pairs bound)"
    if missed:
        shown = ", ".join(sorted(missed)[:5])
        more = f" (+{len(missed) - 5} more)" if len(missed) > 5 else ""
        details += f"; missed: {shown}{more}"
    if out_of_golden:
        details += f"; {out_of_golden} proposal(s) outside the golden column set, unscored"
    return ScorerResult(name="mapping_coverage", score=score, details=details)


def false_friend_hits(proposed: ProposedMapping, golden: GoldenMapping) -> ScorerResult:
    """Gateable false-friend guard (column mode): **1.0 when no proposal binds a golden
    ``false_friends`` pair, else 0.0**, every hit named in the details.

    Vacuously 1.0 when the golden declares no false friends. This keeps the findings-review
    gate — "coverage ≥ 0.8 AND zero false-friend hits" — expressible as two ``min_scores``
    lines (``mapping_coverage``/``false_friend_hits``)."""
    friends = _false_friend_pairs(golden)
    hits = [
        f"{p.concept} → {p.table}.{p.column}"
        for p in proposed.proposals
        if _norm_pair(p.table, p.column) in friends
    ]
    if hits:
        return ScorerResult(
            name="false_friend_hits",
            score=0.0,
            details=f"{len(hits)} FALSE-FRIEND HIT(S): {', '.join(hits)}",
        )
    watched = f"{len(friends)} false-friend column(s) watched" if friends else "none declared"
    return ScorerResult(
        name="false_friend_hits", score=1.0, details=f"no false-friend columns bound ({watched})"
    )


def confidence_calibration(proposed: ProposedMapping, golden: GoldenMapping) -> ScorerResult:
    """Details-only (no gate): does confidence separate correct proposals from wrong ones?

    Score is the *calibration margin* = mean confidence of correct proposals minus mean of
    wrong ones, clamped to [0, 1]. Only **golden-universe** proposals are considered (WP9.2),
    so a confident-but-out-of-universe generated concept can't masquerade as a "wrong"
    proposal and collapse the margin. With no wrong proposals to separate from, the margin is
    **1.0** by definition (perfect separation), not the mean confidence. The ADR-0008
    degraded-mode story (low confidence = review harder) only holds if this margin is
    meaningfully positive (memo §7 Q2)."""
    acceptable = _acceptable_pairs(golden)
    universe = _golden_universe(golden)
    correct_conf: list[float] = []
    wrong_conf: list[float] = []
    for p in proposed.proposals:
        cnorm = normalize_identifier(p.concept)
        if cnorm not in universe:
            continue
        pair = _norm_pair(p.table, p.column)
        if cnorm in acceptable and pair in acceptable[cnorm]:
            correct_conf.append(p.confidence)
        else:
            wrong_conf.append(p.confidence)

    if not correct_conf and not wrong_conf:
        return ScorerResult(name="confidence_calibration", score=0.0, details="no scored proposals")
    mean_correct = sum(correct_conf) / len(correct_conf) if correct_conf else 0.0
    mean_wrong = sum(wrong_conf) / len(wrong_conf) if wrong_conf else 0.0
    if not wrong_conf:
        # No wrong proposals to separate from: perfect separation by definition (1.0), not
        # the mean confidence (which would understate a flawless run).
        return ScorerResult(
            name="confidence_calibration",
            score=1.0,
            details=(
                f"margin=1.00; mean confidence correct={mean_correct:.2f} "
                f"(n={len(correct_conf)}), no wrong proposals to separate from"
            ),
        )
    margin = max(0.0, min(1.0, mean_correct - mean_wrong))
    details = (
        f"margin={margin:.2f}; mean confidence correct={mean_correct:.2f} "
        f"(n={len(correct_conf)}), wrong={mean_wrong:.2f} (n={len(wrong_conf)})"
    )
    return ScorerResult(name="confidence_calibration", score=margin, details=details)


MAPPING_SCORERS: dict[str, MappingScorer] = {
    "mapping_accuracy": mapping_accuracy,
    "gap_detection": gap_detection,
    "confidence_calibration": confidence_calibration,
}

MappingMatchMode = Literal["concept", "column"]


def score_mapping(
    proposed: ProposedMapping, golden: GoldenMapping, *, mode: MappingMatchMode = "concept"
) -> list[ScorerResult]:
    """Apply the mapping scorers for the case's ``mapping_match`` mode (WP14).

    ``concept`` (default) is the WP9/WP9.2 behaviour — byte-identical, name-aligned goldens
    (``bank``/``messy_insurance``). ``column`` is the honest scale mode: pair-based
    ``mapping_coverage`` + gateable ``false_friend_hits`` + ``gap_detection`` reported-only
    (it is concept-coupled and blind at scale; the loader rejects gating it there)."""
    if mode == "column":
        return [
            mapping_coverage(proposed, golden),
            false_friend_hits(proposed, golden),
            gap_detection(proposed, golden, reported_only=True),
        ]
    return [scorer(proposed, golden) for scorer in MAPPING_SCORERS.values()]
