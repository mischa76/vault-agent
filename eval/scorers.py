"""Deterministic scorers for eval runs (wp6-eval-harness-spec.md §4).

Pure functions ``(state, case) -> ScorerResult`` — keyless, no LLM, unit-tested like
everything else. Golden matching is *structural*, never textual: names, business keys,
connected-hub sets, driving-key sets, and attribute sets are compared through
``rules.normalize_identifier``, so ``"national customer ID"`` matches a generated
``NATIONAL_CUSTOMER_ID`` and construct names match regardless of label casing/spacing.

``normalize_identifier`` folds casing and separators but not word *order*, so a name is
only a reliable key where the golden and the modeller agree on it. Links therefore resolve
on their grain instead (:func:`_resolve_link`) — ``link_policy_insured_person`` and
``link_insured_person_policy`` are one construct. Hubs and satellites remain name-keyed;
see the caveat in ``eval/README.md``.
"""
from collections.abc import Callable, Iterable
from typing import Literal

from pydantic import BaseModel

from eval.datasets import EvalCase, GoldenLink
from eval.mapping import GoldenMapping, ProposedMapping
from eval.resolution import (
    NEW,
    RESOLUTION_CLASSES,
    SAME_AS,
    GoldenResolutionSet,
    ResolutionResult,
    key_ref,
    proposals_by_key,
)
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import Link, VaultAgentState, split_concept_key


class ScorerResult(BaseModel):
    """One scorer's verdict for one run: a 0..1 score plus a human-readable diagnosis."""

    name: str
    score: float  # 0.0 .. 1.0
    details: str


Scorer = Callable[[VaultAgentState, EvalCase], ScorerResult]

# One vacuity convention for every scorer (WP18 §2.2): a scorer with **nothing to check**
# returns score 1.0 and details starting with this prefix. An empty golden makes no claim, so
# scoring it as a failure (the pre-2026-07-28 ``construct_f1`` 0.000) is misleading — but the
# 1.0 must be recognisable as "nothing was checked", which is what the prefix is for:
# ``eval.run.vacuous_scorers`` keys on it to mark the console summary AND to refuse a gate on
# a scorer that was vacuous in every repeat. Never emit a vacuous verdict without it.
VACUOUS_PREFIX = "vacuous — "


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


def _link_grain(hubs: Iterable[str]) -> tuple[str, ...]:
    """A link's structural identity: the sorted *multiset* of its normalised hubs.

    Sorted, so ``[hub_policy, hub_person]`` and ``[hub_person, hub_policy]`` are the same
    grain; a multiset rather than a set, so a self-referencing link (the same hub twice,
    ADR-0009) stays distinguishable from a single participation."""
    return tuple(sorted(normalize_identifier(hub) for hub in hubs))


def _resolve_link(golden: GoldenLink, generated: list[Link]) -> Link | None:
    """The generated link a golden link refers to, matched on grain — not on name.

    A link's name is free-form modeller output: ``link_policy_insured_person`` and
    ``link_insured_person_policy`` are the same DV construct, so keying on the name scores
    a correct model as a miss. The grain (which hubs participate, ADR-0009 roles collapsed
    to their hub) is the structural identity. The name only breaks a tie when two generated
    links share a grain — which the validator already flags as W_LINK_REDUNDANT_GRAIN, so
    it is a degenerate case rather than the norm; an unresolvable tie is left unmatched."""
    grain = _link_grain(golden.connected_hubs)
    candidates = [
        link for link in generated if _link_grain(ref.hub for ref in link.hub_refs) == grain
    ]
    if len(candidates) == 1:
        return candidates[0]
    for candidate in candidates:
        if normalize_identifier(candidate.name) == normalize_identifier(golden.name):
            return candidate
    return None


def _matched_links(state: VaultAgentState, case: EvalCase) -> int:
    """Golden links matched structurally on their grain (see :func:`_resolve_link`)."""
    return sum(
        1
        for golden in case.golden.links
        if _resolve_link(golden, state.dv_model.links) is not None
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
    """Mean F1 over the construct kinds the golden actually declares.

    A kind the golden says nothing about is EXCLUDED from the mean rather than scored 0.0.
    Scoring it would punish the model for generating against an absent expectation: the
    synthetic scale cases ship a golden *mapping* and no golden *model*, and used to read
    ``construct_f1 0.000`` — which looks like total failure and means "nothing was
    checked". A golden that declares nothing at all is vacuous (1.0, like
    :func:`driving_key_accuracy`), and ``load_eval_case`` refuses to let a case gate it —
    a vacuous score must never be able to pass a gate."""
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
    declared = [kind for kind in kinds if kind[3] > 0]
    scores = [_f1(matched, n_gen, n_gold) for _, matched, n_gen, n_gold in declared]
    details = "; ".join(
        f"{kind}: {matched}/{n_gold} golden matched, {n_gen} generated, F1={score:.2f}"
        for (kind, matched, n_gen, n_gold), score in zip(declared, scores, strict=True)
    )
    undeclared = [
        f"{kind}: not declared by the golden ({n_gen} generated, unscored)"
        for kind, _, n_gen, n_gold in kinds
        if n_gold == 0
    ]
    details = "; ".join(filter(None, [details, *undeclared]))
    if not scores:
        return ScorerResult(
            name="construct_f1",
            score=1.0,
            details=f"{VACUOUS_PREFIX}the golden declares no constructs ({details})",
        )
    return ScorerResult(name="construct_f1", score=sum(scores) / len(scores), details=details)


def driving_key_accuracy(state: VaultAgentState, case: EvalCase) -> ScorerResult:
    """Fraction of golden links with declared driving keys whose generated counterpart
    (resolved on grain, see :func:`_resolve_link`) declares the same normalised
    driving-key set."""
    golden_links = [link for link in case.golden.links if link.driving_key]
    if not golden_links:
        return ScorerResult(
            name="driving_key_accuracy",
            score=1.0,
            details=f"{VACUOUS_PREFIX}no golden driving keys declared",
        )
    misses: list[str] = []
    for golden in golden_links:
        counterpart = _resolve_link(golden, state.dv_model.links)
        declared = _norm_set(counterpart.driving_key) if counterpart is not None else None
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
def existing_construct_preservation(state: VaultAgentState, case: EvalCase) -> ScorerResult:
    """Did the extension run leave the vault it extends exactly as it was? (WP23, charter §6)

    Deterministic and binary in spirit: this is the promise brownfield mode makes, so the
    gate is 1.0 and anything less is a defect, not a quality signal. It checks the three
    things a rebuild would notice — a construct that disappeared, a hub whose business key
    moved, a satellite whose payload changed shape — against the model the run was told to
    extend.

    It deliberately duplicates what the validator's ``E_EXISTING_*`` gates enforce in the
    product. That is the point of an eval scorer: the gates could themselves be wrong or be
    bypassed by a future re-model mode, and this measures the OUTCOME rather than trusting
    the mechanism. Vacuous (1.0, prefixed) for a greenfield case, which never had a vault to
    preserve — and ``load_eval_case`` refuses to let such a case gate it."""
    prior = state.existing_model
    if prior is None:
        return ScorerResult(
            name="existing_construct_preservation",
            score=1.0,
            details=f"{VACUOUS_PREFIX}greenfield case: no existing vault to preserve",
        )
    merged = state.dv_model
    hubs = {hub.name: hub for hub in merged.hubs}
    sats = {sat.name: sat for sat in merged.satellites}
    present = set(hubs) | {link.name for link in merged.links} | set(sats)

    violations: list[str] = []
    total = len(prior.hubs) + len(prior.links) + len(prior.satellites)
    for hub in prior.hubs:
        if hub.name not in present:
            violations.append(f"{hub.name} removed")
        elif _norm_set([hubs[hub.name].business_key]) != _norm_set([hub.business_key]):
            violations.append(f"{hub.name} business key changed")
    for link in prior.links:
        if link.name not in present:
            violations.append(f"{link.name} removed")
    for sat in prior.satellites:
        if sat.name not in present:
            violations.append(f"{sat.name} removed")
        elif _norm_set(sats[sat.name].attributes) != _norm_set(sat.attributes):
            violations.append(f"{sat.name} payload reshaped")

    kept = total - len(violations)
    score = kept / total if total else 1.0
    details = (
        f"{kept}/{total} existing construct(s) preserved"
        if not violations
        else f"{kept}/{total} preserved; violations: {', '.join(violations)}"
    )
    return ScorerResult(
        name="existing_construct_preservation", score=score, details=details
    )


SCORERS: dict[str, Scorer] = {
    "construct_f1": construct_f1,
    "driving_key_accuracy": driving_key_accuracy,
    "validation_gate": validation_gate,
    "pipeline_health": pipeline_health,
    # WP23: inert (vacuous 1.0) on greenfield cases, the gate on extension cases.
    "existing_construct_preservation": existing_construct_preservation,
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
        details = f"{VACUOUS_PREFIX}no mappable concepts"
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
    column-mode case that gates it (``datasets.load_eval_case``).

    With no golden gaps the verdict is vacuous (WP18 §2.2): the ``vacuous`` marker comes
    **first** and the reported-only note after it, so ``vacuous_scorers``' ``startswith`` key
    holds in both modes."""
    prefix = "concept-coupled — reported only in column mode; " if reported_only else ""
    gap_concepts = _gap_concepts(golden)
    if not gap_concepts:
        return ScorerResult(
            name="gap_detection", score=1.0, details=f"{VACUOUS_PREFIX}{prefix}no golden gaps"
        )

    # WP32: `proposed.gaps` holds concept KEYS ("<entity>::<label>"), because a bare label is
    # not an identity — three reference hubs can each be keyed "Name". A golden gap is written
    # as a label, so compare on the label half; the entity-less form is unchanged.
    proposed_gaps = {normalize_identifier(split_concept_key(g)[0]) for g in proposed.gaps}
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
        details = f"{VACUOUS_PREFIX}no mappable golden entries"
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
    if not friends:
        # Nothing declared to watch for: vacuous, not a clean bill of health (WP18 §2.2).
        return ScorerResult(
            name="false_friend_hits",
            score=1.0,
            details=f"{VACUOUS_PREFIX}the golden declares no false friends",
        )
    return ScorerResult(
        name="false_friend_hits",
        score=1.0,
        details=(
            f"no false-friend columns bound ({len(friends)} false-friend column(s) watched)"
        ),
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
        # Nothing to separate: vacuous 1.0, not 0.0 (WP18 §2.2 polarity fix). Scoring
        # "nothing to check" as total failure is the pre-2026-07-28 ``construct_f1`` defect
        # mirrored; the prefix keeps the 1.0 from reading as perfect calibration and stops
        # the runner from letting it satisfy a gate.
        return ScorerResult(
            name="confidence_calibration",
            score=1.0,
            details=f"{VACUOUS_PREFIX}no scored proposals",
        )
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

# --- Brownfield Phase 2: entity resolution (spike D2) --------------------------------------
# These are scored against a GoldenResolutionSet + a mechanism's ResolutionResult, not against
# a pipeline state — the spike measures prototypes, and the production integration (if any) is
# what the spike decides. They survive the spike as eval assets, like the WP9 mapping scorers.


def _is_merge(resolution: str) -> bool:
    """True when a resolution claims the concept IS an existing construct.

    ``same_as_candidate`` is deliberately NOT a merge: it produces two constructs plus a flag,
    which is the charter's required output for asserted-equivalent-but-different keys."""
    return resolution not in RESOLUTION_CLASSES


def false_merge_rate(golden: GoldenResolutionSet, result: ResolutionResult) -> ScorerResult:
    """**The primary metric.** 1.0 iff the mechanism never merged a concept it should not have.

    A false merge declares a new source's concept to BE an existing construct when the golden
    says otherwise — feeding foreign business keys into a hub that holds live history. That is
    the destructive migration the brownfield charter refuses, so this is scored as a hard
    property, not a rate to optimise: any violation drops it to 0.0 and names the offenders.

    Merging onto the WRONG existing construct counts too. Answering ``unresolved`` never does:
    the honest non-answer is the behaviour we want when the mechanism cannot tell."""
    expected = golden.by_key()
    offenders: list[str] = []
    merges = 0
    unscored = 0
    for proposal in result.proposals:
        if not _is_merge(proposal.resolution):
            continue
        want = expected.get(key_ref(proposal.concept))
        if want is None:
            # OUT OF UNIVERSE, not an offence (the WP14 semantics). The golden is deliberately
            # seven traps, not every concept the pipeline will meet; counting an unmatched
            # proposal as a false merge would turn the golden's own narrowness into a product
            # defect, and did — before WP29.1 nothing matched at all, so every correct merge
            # scored as a false one.
            unscored += 1
            continue
        merges += 1
        if want.expected != proposal.resolution:
            offenders.append(
                f"{proposal.concept} -> {proposal.resolution} (golden: {want.expected})"
            )
    tail = f"; {unscored} merge(s) outside the golden set, unscored" if unscored else ""
    if not merges:
        return ScorerResult(
            name="false_merge_rate", score=1.0,
            details=f"{VACUOUS_PREFIX}no merge onto a golden concept{tail}",
        )
    if offenders:
        return ScorerResult(
            name="false_merge_rate", score=0.0,
            details=(
                f"{len(offenders)} FALSE MERGE(S) of {merges}: " + "; ".join(offenders) + tail
            ),
        )
    return ScorerResult(
        name="false_merge_rate", score=1.0,
        details=(
            f"{merges} merge(s), all correct — no foreign key entered an existing hub{tail}"
        ),
    )


def resolution_accuracy(golden: GoldenResolutionSet, result: ResolutionResult) -> ScorerResult:
    """Share of golden concepts answered exactly right. SECONDARY to false_merge_rate.

    ``unresolved`` scores as wrong here (it is not the answer) while scoring as safe in
    false_merge_rate — that split is the point: the memo must be able to see a mechanism that
    is honest but unhelpful, and tell it apart from one that is helpful but dangerous."""
    expected = golden.by_key()
    proposals = proposals_by_key(result)
    correct: list[str] = []
    wrong: list[str] = []
    for ref, want in expected.items():
        concept = want.concept
        got = proposals.get(ref, [])
        if not got:
            # A MISS, never a correct answer. Before WP29.2 an unmatched entry was read as
            # `unresolved` — and trap 5 expects exactly that, so it scored as right having
            # measured nothing. "Not found" and "answered unresolved" are different facts.
            wrong.append(f"{concept}: no answer (want {want.expected})")
            continue
        answers = {p.resolution for p in got}
        if len(answers) > 1:
            # Several proposals concern this key and disagree. Neither is "the" answer, and
            # picking one would hide the contradiction — which in the 2026-08-01 probe was a
            # false merge sitting beside a correct same-as.
            wrong.append(f"{concept}: proposals disagree ({', '.join(sorted(answers))})")
            continue
        answer = got[0].resolution
        same_as_ok = want.expected != SAME_AS or all(p.same_as == want.same_as for p in got)
        if answer == want.expected and same_as_ok:
            correct.append(concept)
        else:
            wrong.append(f"{concept}: {answer} (want {want.expected})")
    score = len(correct) / len(expected) if expected else 1.0
    details = f"{len(correct)}/{len(expected)} correct"
    if wrong:
        details += "; wrong: " + "; ".join(wrong)
    return ScorerResult(name="resolution_accuracy", score=score, details=details)


def new_hub_detection(golden: GoldenResolutionSet, result: ResolutionResult) -> ScorerResult:
    """Recall over concepts that must NOT be merged (``NEW`` and ``same_as_candidate``).

    The complement of the merge risk: a mechanism can trivially score 1.0 on false_merge_rate
    by never merging, and this is what catches that — it measures whether the non-merge
    answers are actually *right* rather than merely safe."""
    must_not_merge = [e for e in golden.resolutions if e.expected in (NEW, SAME_AS)]
    if not must_not_merge:
        return ScorerResult(
            name="new_hub_detection", score=1.0,
            details=f"{VACUOUS_PREFIX}the golden declares no non-merge concepts",
        )
    proposals = proposals_by_key(result)
    hits = [
        e.concept for e in must_not_merge
        if (found := proposals.get(normalize_identifier(e.source_key)))
        and all(p.resolution == e.expected for p in found)
    ]
    missed = sorted({e.concept for e in must_not_merge} - set(hits))
    details = f"{len(hits)}/{len(must_not_merge)} identified"
    if missed:
        details += f"; missed: {', '.join(missed)}"
    return ScorerResult(
        name="new_hub_detection", score=len(hits) / len(must_not_merge), details=details
    )


def resolution_calibration(
    golden: GoldenResolutionSet, result: ResolutionResult
) -> ScorerResult:
    """Does confidence separate right answers from wrong ones? (WP9 §7's question, again.)

    The margin between the mean confidence of correct and of incorrect proposals, clamped to
    0..1. 1.0 when there are no wrong proposals to separate (perfect separation is vacuous but
    honest — the same convention mapping's calibration scorer settled on)."""
    expected = golden.by_key()
    right: list[float] = []
    wrong: list[float] = []
    for proposal in result.proposals:
        want = expected.get(key_ref(proposal.concept))
        if want is None:
            continue
        (right if proposal.resolution == want.expected else wrong).append(proposal.confidence)
    if not wrong:
        return ScorerResult(
            name="resolution_calibration", score=1.0,
            details=f"{VACUOUS_PREFIX}no wrong proposals to separate",
        )
    if not right:
        return ScorerResult(
            name="resolution_calibration", score=0.0,
            details="no correct proposals — nothing to separate wrong answers from",
        )
    margin = sum(right) / len(right) - sum(wrong) / len(wrong)
    return ScorerResult(
        name="resolution_calibration", score=max(0.0, min(1.0, margin)),
        details=(
            f"mean confidence correct={sum(right)/len(right):.2f} "
            f"wrong={sum(wrong)/len(wrong):.2f} margin={margin:.2f}"
        ),
    )


RESOLUTION_SCORERS = {
    "false_merge_rate": false_merge_rate,       # primary — a hard property
    "resolution_accuracy": resolution_accuracy,
    "new_hub_detection": new_hub_detection,
    "resolution_calibration": resolution_calibration,
}


def score_resolution(
    golden: GoldenResolutionSet, result: ResolutionResult
) -> list[ScorerResult]:
    return [scorer(golden, result) for scorer in RESOLUTION_SCORERS.values()]

