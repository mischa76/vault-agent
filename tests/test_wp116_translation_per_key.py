"""WP116 (C42) — a translation is ratified once per key: the per-construct `link_translation`
and `sat_translation` flags carry their key as a typed reason and are disclosures under one
decision per key. Committed red before the change. Keyless."""
from __future__ import annotations

import re
from pathlib import Path

from eval.wp34_check import REVIEW_DECISION_SAMPLES
from tests.test_wp36_translation import _ratified_state
from vault_agent.agents.orchestrator import (
    assemble_review_queue,
    render_review_queue_md,
    review_queue_layout,
)
from vault_agent.rules.dv2_rules import translation_key
from vault_agent.state import FlagKind, KeyTranslation, VaultAgentState

SRC = Path(__file__).resolve().parents[1] / "src" / "vault_agent"


def _t(through: str = "Product", natural: str = "PRODUCTNUMBER") -> KeyTranslation:
    return KeyTranslation(referencing_column="ProductID", through_table=through,
                          surrogate_column="ProductID", natural_key_column=natural)


def test_the_key_is_the_hub_the_relation_and_the_natural_key() -> None:
    assert translation_key(_t(), "hub_product") == "hub_product=Product.PRODUCTNUMBER"
    composite = KeyTranslation(referencing_column="RateID", through_table="CurrencyRate",
                               surrogate_column="CurrencyRateID", natural_key_column="FROM",
                               natural_key_columns=["FROM", "TO", "DATE"])
    assert (translation_key(composite, "hub_currency_rate")
            == "hub_currency_rate=CurrencyRate.FROM+TO+DATE")
    # the referencing column is not part of the key: two surrogates to one hub are one key
    other = KeyTranslation(referencing_column="SizeUnitMeasureCode", through_table="Product",
                           surrogate_column="ProductID", natural_key_column="PRODUCTNUMBER")
    assert translation_key(other, "hub_product") == translation_key(_t(), "hub_product")


def test_the_proposers_translated_link_carries_its_key_and_the_queue_asks_once() -> None:
    state = _ratified_state(with_product=True)
    [flag] = [f for f in state.flags if f.kind == FlagKind.LINK_TRANSLATION]
    assert flag.reason == "hub_product=Product.PRODUCTNUMBER"
    queue = assemble_review_queue(state)
    decisions = [i for i in queue.decisions if i.kind == "review_flag"]
    assert [i.asset for i in decisions] == ["hub_product=Product.PRODUCTNUMBER"]
    assert "1 construct" in decisions[0].summary and "Product" in decisions[0].summary
    assert flag.asset in decisions[0].detail
    [disclosed] = [i for i in queue.disclosures if i.kind == "review_flag"]
    assert disclosed.asset == flag.asset
    assert disclosed.group == "translation:hub_product=Product.PRODUCTNUMBER"


def _five_flags_two_keys() -> VaultAgentState:
    state = VaultAgentState()
    product = translation_key(_t(), "hub_product")
    model = translation_key(_t("ProductModel", "NAME"), "hub_product_model")
    for n in range(3):
        state.flag("link_proposer", f"link {n} translates", kind=FlagKind.LINK_TRANSLATION,
                   asset=f"Table{n}.ProductID", reason=product)
    state.flag("link_proposer", "sat translates", kind=FlagKind.SAT_TRANSLATION,
               asset="sat_product_cost_history", reason=product)
    state.flag("subtype_feed", "sat translates", kind=FlagKind.SAT_TRANSLATION,
               asset="sat_product_model_details", reason=model)
    return state


def test_five_flags_over_two_keys_are_two_decisions_and_five_disclosures() -> None:
    queue = assemble_review_queue(_five_flags_two_keys())
    assert [i.asset for i in queue.decisions] == [
        "hub_product=Product.PRODUCTNUMBER", "hub_product_model=ProductModel.NAME",
    ]
    assert "4 construct(s)" in queue.decisions[0].summary
    detail = queue.decisions[0].detail
    assert all(a in detail for a in ("Table0.ProductID", "sat_product_cost_history"))
    assert len(queue.disclosures) == 5
    assert {i.group for i in queue.disclosures} == {
        "translation:hub_product=Product.PRODUCTNUMBER",
        "translation:hub_product_model=ProductModel.NAME",
    }


def test_the_larger_key_group_collapses_to_a_line_naming_the_key() -> None:
    layout = review_queue_layout(assemble_review_queue(_five_flags_two_keys()))
    disclosed = next(items for role, kind, items in layout
                     if role == "disclosure" and kind == "review_flag")
    assert len(disclosed) == 2  # four product constructs collapsed, the model one alone
    collapsed = next(i for i in disclosed if i.summary.startswith("4×"))
    assert "Product" in collapsed.summary and "PRODUCTNUMBER" in collapsed.summary
    md = render_review_queue_md(assemble_review_queue(_five_flags_two_keys()))
    decisions_section = md.split("## Disclosures")[0]
    assert "hub_product=Product.PRODUCTNUMBER" in decisions_section
    assert "Table0.ProductID" in decisions_section  # the constructs listed under the decision


def test_a_translation_flag_without_a_key_stays_a_decision() -> None:
    state = VaultAgentState()
    state.flag("link_proposer", "translation", kind=FlagKind.LINK_TRANSLATION, asset="link_a_b")
    queue = assemble_review_queue(state)
    assert [i.asset for i in queue.decisions] == ["link_a_b"] and queue.disclosures == []


def test_every_raise_site_of_the_two_kinds_passes_its_key() -> None:
    sites = 0
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"kind=FlagKind\.(LINK|SAT)_TRANSLATION", text):
            window = text[max(0, match.start() - 800): match.end() + 200]
            call = window[window.rfind("state.flag("):]
            assert "reason=" in call, f"{path.name}: a translation flag without its key"
            sites += 1
    assert sites >= 6


def test_the_second_generations_samples_are_re_read_under_the_rule() -> None:
    samples = dict(REVIEW_DECISION_SAMPLES["claude-opus-5-5"])
    assert samples["20261030T184653194084Z"] == 90  # twenty-second: 91 − 4 flags + 3 keys
    assert samples["20261031T032606335763Z"] == 94  # twenty-third: 95 − 4 + 3
