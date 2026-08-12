"""The result file's SHAPE is an interface, and this pins it before it grows again (WP34).

Every analysis of a paid run reads these files, including archived ones nobody will ever
re-run: `eval/wp34_check` reproduces the 2026-08-09 chains from them, which is the only reason
its constants are recomputed rather than quoted. `eval/results/` is gitignored, so no committed
fixture can hold a real one — the guard has to be the key set itself.

Two properties matter, and neither is checked anywhere else:

* **`model_shape["hubs"]` is a list of plain strings.** `hub_origin` and `zero_satellite_hubs`
  both index it directly. Enriching it into a list of objects would read as an additive change
  and would silently break every archived comparison.
* **`run_metrics` only ever GROWS.** A key that disappears or is renamed takes the archived
  runs with it, because those files cannot be regenerated at any price.

Written before the telemetry the 2026-08-12 run showed to be missing (proposer skips, hub key
columns) is added, so that "additive" is asserted rather than intended.
"""
from __future__ import annotations

from eval.run import UsageTotals, model_shape, run_metrics
from vault_agent.state import DVModel, Hub, Link, Satellite, VaultAgentState

# The keys every result file written since WP34 carries. New telemetry ADDS to this set;
# removing or renaming a member orphans the archived runs, which is why this is exhaustive
# rather than a subset check.
METRICS_KEYS = {
    "wall_clock_seconds",
    "usage",
    "review_items_total",
    "review_queue_lines",
    "constructs",
    "model",
    "flags",
    "validation_codes",
    "backstop_fires",
}


def _model() -> DVModel:
    return DVModel(
        hubs=[
            Hub(name="hub_person", business_key="business_entity_id",
                source_entity="person", description="x"),
        ],
        links=[
            Link(name="link_person_store", connected_hubs=["hub_person", "hub_store"],
                 description="x"),
        ],
        satellites=[
            Satellite(name="sat_person_details", parent="hub_person", sat_type="standard",
                      description="x"),
        ],
    )


def _metrics() -> dict[str, object]:
    state = VaultAgentState(input_documents=["r.md"])
    state.dv_model = _model()
    return run_metrics(state, 1.0, UsageTotals())


def test_the_hub_list_stays_a_list_of_names() -> None:
    """`wp34_check` indexes `step["model"]["hubs"]` as strings, and archived runs cannot be
    re-emitted in any richer form. Hub key columns therefore belong BESIDE this, never in it."""
    shape = model_shape(_model())

    assert shape["hubs"] == ["hub_person"]
    assert all(isinstance(name, str) for name in shape["hubs"])


def test_the_satellite_and_link_entries_keep_their_established_keys() -> None:
    """A link carries name and grain, plus `aliases` only where one exists (WP34); a satellite
    carries name and parent. Anything else added here changes what every archived file means."""
    shape = model_shape(_model())

    assert set(shape["links"][0]) == {"name", "hubs"}
    assert set(shape["satellites"][0]) == {"name", "parent"}


def test_run_metrics_never_loses_a_key() -> None:
    """The additive contract, stated as an equality so a rename fails here and not six weeks
    later when an archived run is re-read."""
    assert METRICS_KEYS <= set(_metrics())


def test_the_established_keys_keep_their_established_types() -> None:
    """`flags` is a count today. If it ever becomes a breakdown it must do so under a NEW key —
    an archived integer and a fresh dict cannot be compared, and the comparison is the point."""
    metrics = _metrics()

    assert isinstance(metrics["flags"], int)
    assert isinstance(metrics["validation_codes"], dict)
    assert isinstance(metrics["backstop_fires"], dict)
    assert set(metrics["constructs"]) == {"hubs", "links", "satellites"}  # type: ignore[arg-type]
