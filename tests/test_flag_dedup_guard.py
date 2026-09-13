"""Guard written FIRST, 2026-09-13, from the third WP30 rerun.

Steps 4 and 5 of `20260913T021958659285Z` exhausted the re-model loop. Each attempt re-runs the
modeler (and the link applier inside it), the code generator and the validator, and every one of
them APPENDS its flags; only the mapper's `rebind_staging` ever deduplicated (the `source_binding`
kind alone), and the mapper does not run on the exhausted path. Three attempts left three copies:
`source_binding` 182 in step 4 against 50 the day before, `link_translation` 9 for 3 translations.
The review clause of wp34 §6 measured that accumulation, not the model.

Pinned here: after the validator has run, the flag list carries no two flags that are identical
in agent, kind, severity, asset and message — whatever the loop, the resume or a caller repeated.
"""
from __future__ import annotations

from tests.test_wp36_translation import _ratified_state
from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.link_proposal import apply_ratified_link_proposals
from vault_agent.state import DVModel, FlagKind, Hub


def _identity(flag):  # type: ignore[no-untyped-def]
    return (flag.agent, flag.kind, flag.severity, flag.asset, flag.message)


async def test_a_second_modelling_attempt_leaves_one_copy_of_each_flag() -> None:
    state = _ratified_state(with_product=True)
    delta = DVModel(hubs=[Hub(name="hub_shopping_cart_item", business_key="ShoppingCartItemID",
                              source_entity="shopping cart item", description="A cart line.")])
    # Attempt 1, as the pipeline runs it: applier (inside the modeler) → generator → validator.
    state = await CodeGeneratorAgent().run(state)
    state = await ValidatorAgent().run(state)
    once = [_identity(f) for f in state.flags]
    assert any(k == FlagKind.LINK_TRANSLATION for _, k, *_ in once)
    # Attempt 2: the same three run again over the same delta (what the re-model loop does when
    # the modeler emits the same thing), nothing in between deduplicates.
    apply_ratified_link_proposals(delta, state.existing_model, state)  # type: ignore[arg-type]
    state = await CodeGeneratorAgent().run(state)
    state = await ValidatorAgent().run(state)
    twice = [_identity(f) for f in state.flags]
    assert len(twice) == len(set(twice)), "a re-emitted flag must be one review item, not two"
    assert sorted(twice) == sorted(set(once) | set(twice))  # nothing lost, nothing new
