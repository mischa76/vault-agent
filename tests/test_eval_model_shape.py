"""WP30.1 — the eval result records WHICH constructs were built, not only how many.

The arm comparison's open question is why arm B builds 73% of arm A's links (WP30 §7.3). It
cannot be answered from anything on disk: the result JSON stored `len(dv_model.links)` and
nothing else, `write_step_vault` wrote the model into a temp workdir that the run deletes, and
the traces carry the re-model loop's DISCARDED attempts — reconstructing from them gave 84
links where the run reported 51.

So the instrument measured the size of its answer and never the answer. This pins the fix.

Structural, not by name (WP14): a link is identified by its GRAIN — the multiset of hubs it
connects — because two runs may name the same relationship differently and a name-keyed
comparison would call that a difference.
"""
from __future__ import annotations

from eval.run import UsageTotals, model_shape, run_metrics
from vault_agent.state import (
    DVModel,
    Hub,
    Link,
    Satellite,
    VaultAgentState,
)


def _model() -> DVModel:
    return DVModel(
        hubs=[
            Hub(name="hub_person", business_key="business_entity_id",
                source_entity="person", description="x"),
            Hub(name="hub_store", business_key="store_id", source_entity="store",
                description="x"),
        ],
        links=[
            Link(name="link_store_person",
                 connected_hubs=["hub_store", "hub_person"],
                 description="x"),
        ],
        satellites=[
            Satellite(name="sat_person_details", parent="hub_person", sat_type="standard",
                      description="x"),
        ],
    )


def test_the_shape_carries_the_link_grain() -> None:
    """The grain is what the question needs: which hubs a link spans, so a later analysis can
    ask whether they came from different subject areas."""
    shape = model_shape(_model())

    assert shape["hubs"] == ["hub_person", "hub_store"]
    assert shape["links"] == [
        {"name": "link_store_person", "hubs": ["hub_person", "hub_store"]}
    ], shape["links"]
    assert shape["satellites"] == [{"name": "sat_person_details", "parent": "hub_person"}]


def test_the_grain_is_order_independent() -> None:
    """Two runs may emit the same relationship with its hubs in either order; sorting makes the
    grain comparable rather than making a difference out of emission order."""
    a = Link(name="l", connected_hubs=["hub_b", "hub_a"],
             description="x")
    b = Link(name="l", connected_hubs=["hub_a", "hub_b"],
             description="x")

    shape_a = model_shape(DVModel(links=[a]))
    shape_b = model_shape(DVModel(links=[b]))

    assert shape_a["links"] == shape_b["links"]


def test_run_metrics_carries_the_shape_beside_the_counts() -> None:
    """The counts stay — every existing consumer reads them — and the shape joins them."""
    state = VaultAgentState(input_documents=["r.md"])
    state.dv_model = _model()

    metrics = run_metrics(state, 1.0, UsageTotals())

    assert metrics["constructs"] == {"hubs": 2, "links": 1, "satellites": 1}
    assert metrics["model"]["links"][0]["hubs"] == ["hub_person", "hub_store"]
