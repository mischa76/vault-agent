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
NAMED_REGRESSIONS = ("hub_sales_representative",)


def named_regressions(final: dict[str, Any]) -> list[str]:
    """Constructs §6 names individually as symptoms that must not come back.

    A named regression is stricter than the zero-satellite count on purpose: WP30.3 invented
    this hub out of a prompt's phrasing, and it can return while carrying a satellite — which
    the count would not notice and a reader of the count would read as absence."""
    return sorted(hub for hub in NAMED_REGRESSIONS if hub in final["hubs"])


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
    return problems


def check(result: dict[str, Any]) -> tuple[bool, list[str]]:
    """Evaluate all four clauses. Returns (all held, one report line per clause)."""
    metrics = result.get("metrics", result)
    steps = metrics["chain_steps"]
    final = steps[-1]["model"]

    cross = cross_domain_links(steps)
    zero_sat = zero_satellite_hubs(final)
    returned = named_regressions(final)
    review = metrics["review_items_total"]
    aliases = unsound_aliases(steps)
    # The chain's validation_codes come from the FINAL state, whose report covers the whole
    # merged model — so any surviving unsound link shows here. Steps are still checked
    # independently by unsound_aliases above, which does not depend on the gate at all.
    gate_fires = metrics.get("validation_codes", {}).get("E_LINK_KEY_NOT_IN_SOURCE", 0)

    clauses = [
        (len(cross) >= 8, f"links:      {len(cross)} cross-domain (need >= 8; "
                          f"baseline {BASELINE_CROSS_DOMAIN}, arm A {ARM_A_CROSS_DOMAIN})"),
        (len(zero_sat) <= BASELINE_ZERO_SAT_HUBS and not returned,
         f"invention:  {len(zero_sat)} zero-satellite hub(s) "
         f"(must not exceed {BASELINE_ZERO_SAT_HUBS}): {zero_sat}"
         + (f"; NAMED REGRESSION present: {returned}" if returned else "")),
        (review < BASELINE_REVIEW_ITEMS,
         f"review:     {review} items (must FALL below {BASELINE_REVIEW_ITEMS})"),
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
