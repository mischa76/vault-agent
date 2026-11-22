"""WP58 — `hub:role` in `connected_hubs` is a role-qualified participation (spec §3).
Committed before the change, failing."""
from __future__ import annotations

from tests.test_agents.test_dv2_modeler import StubExtractor, _state, _valid_payload
from vault_agent.agents.dv2_modeler import Dv2ModelerAgent
from vault_agent.state import FlagKind, Link


def test_a_colon_string_reads_as_hub_and_role() -> None:
    link = Link(name="link_sales_order_address", description="d",
                connected_hubs=["hub_address", "hub_address:ship_to", {"hub": "hub_sales_order"}])
    refs = link.hub_refs
    assert [(r.hub, r.role) for r in refs] == [
        ("hub_address", None), ("hub_address", "ship_to"), ("hub_sales_order", None)
    ]


async def test_the_parser_keeps_a_link_written_in_colon_form() -> None:
    payload = _valid_payload()
    payload["hubs"].append({"name": "hub_currency", "business_key": "CurrencyCode",
                            "source_entity": "Currency", "description": "A currency."})
    payload["links"].append({"name": "link_currency_rate_currency",
                             "connected_hubs": ["hub_currency:from", "hub_currency:to"],
                             "description": "The two currencies of a rate."})
    state = await Dv2ModelerAgent(extractor=StubExtractor(payload)).run(_state())
    [link] = [lk for lk in state.dv_model.links if lk.name == "link_currency_rate_currency"]
    assert [(r.hub, r.role) for r in link.hub_refs] == [("hub_currency", "from"),
                                                        ("hub_currency", "to")]
    assert not [f for f in state.flags
                if f.kind == FlagKind.DROPPED_RECORD and f.asset == "link_currency_rate_currency"]
