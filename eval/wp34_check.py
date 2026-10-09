"""WP34 §6: compute the four-clause bar from a chain result. Written BEFORE the run.

The point of this file is its commit date. WP30.3 met a bar it had written in advance and the
model regressed elsewhere while satisfying it, and the post-mortem named the reason: *a
criterion a change can meet while making the result worse is a bad criterion*. So §6 is a
CONJUNCTION, and this computes every clause from the recorded result rather than from a
reading of it — a number produced after the fact explains anything.

Usage::

    uv run python -m eval.wp34_check eval/results/<chain-result>.json

Keyless and pure; it reads a result file and the checked-in case assets, and calls nothing.
"""
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

from eval.adventureworks.derive import ARM_B_ORDER, case_dir_name
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.source_schema import load_source_schemas

DATASETS = Path("eval") / "datasets"

# The WP30.2 run these clauses are measured against — the standing state after WP30.3 was
# reverted. RECOMPUTED from the stored result file with the functions below, not quoted from
# prose: running this module's own logic over the four archived 2026-08-09 chains reproduces
# the log's table exactly (cross-domain 0, 0, 2, 2 and review 456, 489, 619, 777), which is
# both the checker's validation and the source of these numbers.
#
# `BASELINE_ZERO_SAT_HUBS` was first written here as 3 from a reading of the prose, which was
# wrong: WP30.2 left **2** (`hub_contact_type`, `hub_shopping_cart`). The correction is the
# reason this comment exists — a criterion carrying a guessed constant judges nothing.
BASELINE_CROSS_DOMAIN = 2
BASELINE_REVIEW_ITEMS = 619
BASELINE_ZERO_SAT_HUBS = 2
# 2026-10-05 (user's decision, `docs/log.md` of that day): the review clause reads
# `review_decisions` — the items a human must answer (WP43) — not the signal count. WP43 took
# the extension inventory (159 items on the 2026-09-17 chain) out of the queue, so the signal
# count fell below 619 by construction and judged nothing.
#
# 2026-10-07 (WP53, user's decision): the ceiling is no longer one chain's number (148, the
# first chain that carried decisions) but a distribution — every completed normal chain of
# `adventureworks_incremental` that carries `review_decisions`, as (stamp, decisions), read from
# the result files. A chain is judged against the chains BEFORE it (its own stamp is excluded),
# by the one-sided 95 % prediction bound of the next observation. A chain enters this record in
# the docs commit of its run whether or not it met the clause: the record measures the modeler's
# spread, not the chains the clause liked. The clause is a regression guard for the chain, not
# yet an arm comparison — arm A has one decision count (134) and no distribution.
# WP62 (2026-10-09): one record per MODELER model — a model generation is its own population.
# The 4.8 record keeps the eleven chains of 2026-10-04 → 2026-10-09; the 5.5 record starts
# empty (the twelfth chain, 238, carried the WP61 contract defect and is not a sample) and
# the clause reports "cannot be judged" until MIN_REVIEW_SAMPLES chains are recorded.
REVIEW_DECISION_SAMPLES: dict[str, tuple[tuple[str, int], ...]] = {
    "claude-opus-4-8": (
        ("20261004T013339024833Z", 148),  # first chain, 2026-10-04 (red)
        ("20261004T140130528908Z", 135),  # second, 2026-10-05 — the first all-green chain
        ("20261005T160357535338Z", 142),  # third, 2026-10-05 (red)
        ("20261005T234048650821Z", 138),  # fourth, 2026-10-06 (red)
        ("20261006T032619166848Z", 139),  # fifth, 2026-10-06 (green)
        ("20261006T172859787765Z", 156),  # sixth, 2026-10-06 (green; failed the 148 ceiling)
        ("20261007T010229861435Z", 127),  # seventh, 2026-10-07 (green; resumed at step 5 from
        #                                   20261007T001520705532Z — the count is the sum over
        #                                   both stamps' step files, see tests/test_wp53)
        ("20261007T041647752430Z", 126),  # eighth, 2026-10-07 (green; resumed at step 5 from
        #                                   20261007T032723285872Z after an exhausted credit)
        ("20261008T005807208141Z", 143),  # ninth, 2026-10-08 (green; WP34 §6 held, 0 zero-sat hubs)
        ("20261008T223946700186Z", 137),  # tenth, 2026-10-09 (step 3 red on E_HUB_PAYLOAD_UNREAD)
        ("20261009T133146634551Z", 136),  # eleventh, 2026-10-09 (green; resumed at step 4 from
        #                                   20261009T124133681291Z; WP34 §6 held; WP57 live)
    ),
    "claude-opus-5-5": (
        ("20261009T213238859667Z", 84),  # fourteenth chain, 2026-10-09 — the first free of the
        #                                   WP61/WP63 review artefacts (green, 20.8 min, 4.38 USD)
    ),
}
DEFAULT_RECORD_MODEL = "claude-opus-4-8"  # every archived result without `models`
MIN_REVIEW_SAMPLES = 3
# One-sided 95 % Student-t quantiles by degrees of freedom (df 1..30; above that, normal).
_T95 = {
    1: 6.314, 2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015, 6: 1.943, 7: 1.895, 8: 1.860, 9: 1.833,
    10: 1.812, 11: 1.796, 12: 1.782, 13: 1.771, 14: 1.761, 15: 1.753, 16: 1.746, 17: 1.740,
    18: 1.734, 19: 1.729, 20: 1.725, 21: 1.721, 22: 1.717, 23: 1.714, 24: 1.711, 25: 1.708,
    26: 1.706, 27: 1.703, 28: 1.701, 29: 1.699, 30: 1.697,
}


def review_ceiling(samples: list[int]) -> float:
    """The one-sided 95 % prediction bound for the next chain's decisions over `samples`:
    mean + t(0.95, n-1) * sd * sqrt(1 + 1/n), with the sample standard deviation. Needs at
    least MIN_REVIEW_SAMPLES samples; the caller decides what fewer means."""
    n = len(samples)
    if n < MIN_REVIEW_SAMPLES:
        raise ValueError(f"need at least {MIN_REVIEW_SAMPLES} samples, got {n}")
    mean = statistics.mean(samples)
    sd = statistics.stdev(samples)
    t = _T95.get(n - 1, 1.645)
    return mean + t * sd * math.sqrt(1 + 1 / n)
ARM_A_CROSS_DOMAIN = 16


def hub_origin(steps: list[dict[str, Any]]) -> dict[str, str]:
    """Which step first introduced each hub — the only way to say "cross-domain" at all.

    A link spans two domains when its two hubs entered the vault at different steps. The
    per-step shapes make that computable; nothing else in the result does."""
    origin: dict[str, str] = {}
    for step in steps:
        for hub in step["model"]["hubs"]:
            origin.setdefault(hub, step["case"])
    return origin


def cross_domain_links(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Links whose participating hubs came from different steps, with where each appeared."""
    origin = hub_origin(steps)
    seen: set[str] = set()
    found: list[dict[str, Any]] = []
    for step in steps:
        for link in step["model"]["links"]:
            grain = tuple(sorted(link["hubs"]))
            key = "|".join(grain)
            if key in seen:
                continue
            domains = {origin.get(hub, "?") for hub in link["hubs"]}
            if len(domains) > 1:
                seen.add(key)
                found.append(
                    {
                        "name": link["name"],
                        "hubs": link["hubs"],
                        "domains": sorted(domains),
                        "built_at": step["case"],
                        "aliases": link.get("aliases", {}),
                    }
                )
    return found


def zero_satellite_hubs(final: dict[str, Any]) -> list[str]:
    """Hubs carrying no satellite — the invention symptom WP30.3 regressed on."""
    parents = {sat["parent"] for sat in final["satellites"]}
    return sorted(hub for hub in final["hubs"] if hub not in parents)


# §6's invention clause has TWO halves and only one was implemented. The spec: "Zero-satellite
# hubs must not rise above the WP30.2 baseline, **and `hub_sales_representative` must not
# return**. This is the clause WP30.3 failed." The named half was missing from this file
# entirely, so both 2026-08-12 runs were reported against a clause that was never computed —
# and the hub was present in both. Added 2026-08-12 as an IMPLEMENTATION of what §6 already
# required, deliberately not a re-derivation: nothing here is loosened, a clause that was
# always in the pre-registration simply started being checked.
#
# CORRECTED 2026-09-14 — the named half no longer fails the run; it is reported. Traced on the
# chain `20260913T230429748887Z`: the resolver proposes `sales representative` as
# `same_as_candidate → hub_employee` (SalesPerson's key is a foreign key to Employee; hub_employee
# is keyed on NationalIDNumber, SalesPerson carries only BusinessEntityID), the ratified same-as
# reaches the modeler through WP29's prompt section, and that section SAYS "keyed differently:
# model it as its OWN hub". The hub is the pipeline's prescribed outcome, not the modeler's
# invention, in every repeat since the resolution checkpoint became reachable. A pre-registered
# clause that penalises a rule of the product is a wrong criterion; changing it after the fact
# is recorded as exactly that (`docs/log.md` 2026-09-14, wp34 §11). The count half stands. The
# hub stays named in the output so its absence, once WP38 lands, is visible as a change.
NAMED_HUBS = ("hub_sales_representative",)


def named_hubs(final: dict[str, Any]) -> list[str]:
    """Constructs §6 named individually — reported, since 2026-09-14 no longer a failure.

    Stricter than the zero-satellite count on purpose: the hub can return while carrying a
    satellite, which the count would not notice and a reader would read as absence."""
    return sorted(hub for hub in NAMED_HUBS if hub in final["hubs"])


def unsound_aliases(steps: list[dict[str, Any]]) -> list[str]:
    """Every alias checked against the columns its referencing table actually declares.

    §6's fourth clause, computed rather than trusted. ``E_LINK_KEY_NOT_IN_SOURCE`` is the gate
    that should make this impossible, so a non-empty result means BOTH a wrong join and a gate
    that did not hold — which is why it is checked independently of the gate."""
    declared: dict[str, set[str]] = {}
    for area in ARM_B_ORDER:
        path = DATASETS / case_dir_name(area) / "source_schema.yml"
        for table in load_source_schemas(path):
            declared.setdefault(normalize_identifier(table.table), set()).update(
                normalize_identifier(c) for c in table.column_names
            )

    problems: list[str] = []
    for step in steps:
        for link in step["model"]["links"]:
            for hub, column in link.get("aliases", {}).items():
                if not any(
                    normalize_identifier(column) in columns for columns in declared.values()
                ):
                    problems.append(
                        f"{step['case']}: {link['name']} aliases {column!r} for {hub}, "
                        f"which no declared table carries"
                    )
            # WP36: a translation has no alias; its soundness is that the referencing
            # relation declares the surrogate it joins on, and the referenced relation
            # declares both columns of the join.
            for hub, t in link.get("translations", {}).items():
                for column, label in (
                    (t["referencing_column"], "joins on"),
                    (t["surrogate_column"], "joins through"),
                    (t["natural_key_column"], "projects"),
                ):
                    if not any(
                        normalize_identifier(column) in columns for columns in declared.values()
                    ):
                        problems.append(
                            f"{step['case']}: {link['name']} {label} {column!r} for {hub} "
                            f"(translation through {t['through_table']}), which no declared "
                            f"table carries"
                        )
    return problems


def _review_clause(
    decisions: int | None, used: list[tuple[str, int]], excluded: bool, review: int
) -> tuple[bool, str]:
    """The review clause (WP53): decisions against the prediction bound of the recorded chains."""
    samples = [count for _, count in used]
    reported = (f" · {review} items reported, not judged (the pre-2026-10-05 clause read them "
                f"against {BASELINE_REVIEW_ITEMS})")
    if decisions is None:
        return False, (f"review:     no review_decisions in this result (pre-WP43, signals only: "
                       f"{review} items) — the clause cannot be judged on it")
    if len(samples) < MIN_REVIEW_SAMPLES:
        return False, (f"review:     {decisions} decision(s) — cannot be judged: "
                       f"{len(samples)} recorded chain(s), need {MIN_REVIEW_SAMPLES}")
    ceiling = review_ceiling(samples)
    stamps = [stamp for stamp, _ in used]
    # (the record is the judged model's own — WP62)
    return decisions <= ceiling, (
        f"review:     {decisions} decision(s) (ceiling {ceiling:.1f} — the one-sided 95 % "
        f"prediction bound of {len(samples)} recorded chain(s), mean "
        f"{statistics.mean(samples):.1f}, sd {statistics.stdev(samples):.1f}, "
        f"{stamps[0][:8]} → {stamps[-1][:8]}"
        f"{'; this run and later ones excluded' if excluded else ''})" + reported
    )


def check(result: dict[str, Any]) -> tuple[bool, list[str]]:
    """Evaluate all four clauses. Returns (all held, one report line per clause)."""
    metrics = result.get("metrics", result)
    steps = metrics["chain_steps"]
    final = steps[-1]["model"]

    cross = cross_domain_links(steps)
    zero_sat = zero_satellite_hubs(final)
    named = named_hubs(final)
    review = metrics["review_items_total"]
    decisions = metrics.get("review_decisions")
    # WP53: judged against the chains BEFORE it — stamps sort chronologically, so an archived
    # chain re-checked later is still judged by its predecessors only, never by itself or by
    # what came after it. A result without a stamp (a chain not yet recorded) sees them all.
    own_stamp = result.get("timestamp")
    record_model = (result.get("models") or {}).get("heavy_model") or DEFAULT_RECORD_MODEL
    record = REVIEW_DECISION_SAMPLES.get(record_model, ())
    used = [(stamp, count) for stamp, count in record
            if own_stamp is None or stamp < own_stamp]
    excluded = len(used) < len(record)
    aliases = unsound_aliases(steps)
    # The chain's validation_codes come from the FINAL state, whose report covers the whole
    # merged model — so any surviving unsound link shows here. Steps are still checked
    # independently by unsound_aliases above, which does not depend on the gate at all.
    gate_fires = metrics.get("validation_codes", {}).get("E_LINK_KEY_NOT_IN_SOURCE", 0)

    clauses = [
        (len(cross) >= 8, f"links:      {len(cross)} cross-domain (need >= 8; "
                          f"baseline {BASELINE_CROSS_DOMAIN}, arm A {ARM_A_CROSS_DOMAIN})"),
        (len(zero_sat) <= BASELINE_ZERO_SAT_HUBS,
         f"invention:  {len(zero_sat)} zero-satellite hub(s) "
         f"(must not exceed {BASELINE_ZERO_SAT_HUBS}): {zero_sat}"
         + (f"; named hub present, reported not failing since 2026-09-14 "
            f"(WP29 same-as outcome): {named}" if named else "")),
        _review_clause(decisions, used, excluded, review),
        (not aliases and gate_fires == 0,
         f"joins:      {len(aliases)} unsound alias(es), "
         f"{gate_fires} E_LINK_KEY_NOT_IN_SOURCE fire(s) — both must be 0"),
    ]
    lines = [f"[{'HELD' if ok else 'FAILED'}] {text}" for ok, text in clauses]
    lines += [f"    cross-domain link: {c['name']} {c['domains']} @ {c['built_at']}"
              for c in cross]
    lines += [f"    UNSOUND: {p}" for p in aliases]
    return all(ok for ok, _ in clauses), lines


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    held, lines = check(result)
    print("\n".join(lines))
    print(
        "\nWP34 §6: "
        + ("ALL FOUR CLAUSES HELD" if held else "NOT MET — the conjunction failed")
    )
    # A conjunction that fails is a finding to record, not a bar to move. See the WP30.3
    # post-mortem in docs/log.md before touching any number in this file.
    return 0 if held else 1


if __name__ == "__main__":
    sys.exit(main())
