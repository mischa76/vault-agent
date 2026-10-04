"""W_HUB_NO_SAT fires once per satellite-less hub — written first, failing (2026-10-04).

The paid chain `20261004T013339024833Z` reported `W_HUB_NO_SAT` 55 times in step 5, all for
`hub_shopping_cart`: 55 is the number of links. WP45's insertion of the composite-key link loop
into `ValidatorAgent.run` left the per-hub satellite check inside that loop, so it ran once per
link for whichever hub the hub loop had ended on. Two hubs, the first without a satellite, two
links: exactly one warning, naming the first hub.
"""
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import DVModel, Hub, Link, Satellite, VaultAgentState


async def test_w_hub_no_sat_fires_once_per_hub_without_a_satellite() -> None:
    model = DVModel(
        hubs=[
            Hub(name="hub_cart", business_key="CartID", source_entity="Cart", description="c"),
            Hub(name="hub_product", business_key="ProductNumber", source_entity="Product",
                description="p"),
        ],
        links=[
            Link(name="link_cart_product", connected_hubs=["hub_cart", "hub_product"],
                 description="l1"),
            Link(name="link_cart_product_again", connected_hubs=["hub_cart", "hub_product"],
                 description="l2"),
        ],
        satellites=[
            Satellite(name="sat_product_detail", parent="hub_product", attributes=["Name"],
                      description="s"),
        ],
    )
    state = await ValidatorAgent().run(VaultAgentState(dv_model=model))
    no_sat = [i for i in state.validation_report.issues if i.code == "W_HUB_NO_SAT"]
    assert [i.construct for i in no_sat] == ["hub_cart"]
