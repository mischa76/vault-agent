"""WP34 inertness guards, written and committed BEFORE the work package.

WP34 adds ``SourceTable.foreign_keys`` and a deterministic pass that PROPOSES links from
them. The invariant binds: a change that must leave existing output untouched commits its
pinning guard first, or it only proves the guard was written afterwards. So this module
pins, as a differential, that declaring foreign keys on a source table changes **nothing**
until a human ratifies a proposal:

* the generated staging models, their scaffolding, metadata and flags,
* the generated raw-vault artifacts,
* and both prompt sections the modeler is given.

The prompt assertion is not incidental — it is spec §3.8's design decision made
*enforceable*. Foreign keys are read only by the deterministic proposer and are
deliberately never rendered into the modeler's prompt, because rendering them would change
arm A's input as well and the arm comparison would then measure a changed input and a new
mechanism at once. That is the WP30.2 confound, and it is the reason that run still cannot
say which of its two simultaneous changes produced its 2 cross-domain links. A future edit
that quietly starts rendering foreign keys fails here.

**Honest about what this proves today.** ``SourceTable`` does not declare ``foreign_keys``
yet and pydantic silently drops unknown keys, so right now these guards pass *vacuously* —
the two schemas under comparison are equal after parsing. That is exactly why the two
``*_can_fail`` tests exist: each perturbs the schema in a way its own surface MUST react to
and asserts the comparison notices, so the machinery is known to have teeth before it is
trusted. The perturbations are deliberately different — an added column is invisible to
staging (which projects what the MODEL uses) and visible to the prompt (which renders
column names), so neither test would prove the other's point. After WP34 lands, the
assertions above pass *substantively*: the field is real, carries data, and nothing acts on
it unratified.
"""
from typing import Any

import pytest

from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.staging_generator import build_staging
from vault_agent.existing_model import render_extension_prompt_section
from vault_agent.grounding import render_schema_prompt_section
from vault_agent.state import (
    DVModel,
    Hub,
    Link,
    Satellite,
    SourceTable,
    VaultAgentState,
)

# The AdventureWorks shape this WP exists for, in miniature: Customer.PersonID references
# Person.BusinessEntityID, i.e. the RENAMED case (spec §3.4) that needs the staging alias.
_FOREIGN_KEYS: list[dict[str, Any]] = [
    {
        "columns": ["PersonID"],
        "references_table": "Person",
        "references_columns": ["BusinessEntityID"],
        "references_schema": "Person",
    }
]


def _vault() -> DVModel:
    """The existing vault an increment extends: hub_person is the link target."""
    return DVModel(
        hubs=[
            Hub(name="hub_person", business_key="BusinessEntityID", source_entity="person",
                description="A person."),
        ],
        satellites=[
            Satellite(name="sat_person_details", parent="hub_person",
                      attributes=["FirstName"], description="Person attributes."),
        ],
    )


def _delta() -> DVModel:
    """What the increment adds — deliberately WITHOUT the link WP34 would propose."""
    return DVModel(
        hubs=[
            Hub(name="hub_customer", business_key="CustomerID", source_entity="customer",
                description="A customer."),
        ],
        links=[
            Link(name="link_customer_store", connected_hubs=["hub_customer", "hub_person"],
                 description="An existing relationship, not a proposed one."),
        ],
        satellites=[
            Satellite(name="sat_customer_details", parent="hub_customer",
                      attributes=["AccountNumber"], description="Customer attributes."),
        ],
    )


def _schemas(
    *, foreign_keys: bool, moved: bool = False, extra_column: bool = False
) -> list[SourceTable]:
    """The same declared schema, differing ONLY in whether foreign keys are declared.

    ``moved`` relocates the table to a different physical schema — the deliberate
    perturbation the mutation test needs, and one that MUST reach the output because
    staging binds through a real dbt ``source()`` when a location is declared (WP7 §7.2).
    """
    customer: dict[str, Any] = {
        "table": "Customer",
        "schema": "Warehouse" if moved else "Sales",
        "columns": ["CustomerID", "PersonID", "AccountNumber"]
        + (["ModifiedDate"] if extra_column else []),
    }
    if foreign_keys:
        customer["foreign_keys"] = _FOREIGN_KEYS
    return [
        SourceTable(**customer),
        SourceTable(table="Person", schema="Person",
                    columns=["BusinessEntityID", "FirstName"]),
    ]


def _staging_fingerprint(schemas: list[SourceTable]) -> dict[str, Any]:
    result = build_staging(_delta(), source_schemas=schemas, existing=_vault())
    return {
        "models": result.models,
        "scaffolding": result.scaffolding,
        "metadata": result.metadata,
        "flags": [f.model_dump() for f in result.flags],
    }


async def _artifact_fingerprint(schemas: list[SourceTable]) -> dict[str, Any]:
    state = VaultAgentState(document_path="req.md")
    state.dv_model = _delta()
    state.existing_model = _vault()
    state.source_schemas = schemas
    state = await CodeGeneratorAgent().run(state)
    return {
        "dbt_models": state.artifacts.dbt_models,
        "staging_models": state.artifacts.staging_models,
        "scaffolding": state.artifacts.scaffolding,
        "automatedv_yaml": state.artifacts.automatedv_yaml,
    }


# ── §5.2 byte-identity: declared foreign keys change nothing unratified ────────────────


def test_declared_foreign_keys_do_not_change_staging() -> None:
    assert _staging_fingerprint(_schemas(foreign_keys=True)) == _staging_fingerprint(
        _schemas(foreign_keys=False)
    ), "declaring a foreign key changed the staging output with nothing ratified"


async def test_declared_foreign_keys_do_not_change_generated_artifacts() -> None:
    with_fks = await _artifact_fingerprint(_schemas(foreign_keys=True))
    without = await _artifact_fingerprint(_schemas(foreign_keys=False))
    assert with_fks == without, (
        "declaring a foreign key changed the generated dbt artifacts with nothing ratified"
    )


# ── §3.8 the render decision, pinned ───────────────────────────────────────────────────


def test_declared_foreign_keys_never_reach_the_modeler_prompt() -> None:
    """Spec §3.8: the proposer reads foreign keys; the modeler's prompt does not show them.

    Rendering them would change arm A's input too, confounding a changed input with a new
    mechanism — the WP30.2 mistake. If this ever becomes the desired behaviour it is a
    separate change measured in a separate run, and this guard is updated deliberately.
    """
    with_fks, without = _schemas(foreign_keys=True), _schemas(foreign_keys=False)

    assert render_schema_prompt_section(with_fks) == render_schema_prompt_section(without)
    assert render_extension_prompt_section(_vault()) == render_extension_prompt_section(
        _vault()
    )
    # The foreign key's own identifiers must appear nowhere in what the modeler is given.
    rendered = render_schema_prompt_section(with_fks) + render_extension_prompt_section(
        _vault()
    )
    assert "references_table" not in rendered
    assert "foreign_key" not in rendered.lower()


def test_greenfield_stays_inert_even_with_foreign_keys_declared() -> None:
    """No existing model -> no link target -> nothing to propose, and an empty section."""
    assert render_extension_prompt_section(None) == ""


# ── the guard's own teeth ──────────────────────────────────────────────────────────────


def test_the_comparison_can_fail() -> None:
    """Prove the fingerprints above are not trivially equal.

    Without this, a comparison that silently stopped covering anything would keep passing
    and the guards would be decorative.

    The first perturbation tried here was an extra declared column, and it did NOT show up —
    correctly, because staging projects what the MODEL uses, not everything the schema
    declares. Recorded rather than quietly swapped: the lesson is that "the schema changed"
    and "the output changed" are not the same statement, which is precisely the property
    WP34's proposer must not violate. Relocating the table is visible by construction, and
    the column that was invisible here is what gives the prompt guard its teeth below.
    """
    baseline = _staging_fingerprint(_schemas(foreign_keys=False))
    perturbed = _staging_fingerprint(_schemas(foreign_keys=False, moved=True))
    if baseline == perturbed:
        pytest.fail(
            "the staging fingerprint did not notice the table moving to another physical "
            "schema — it is too coarse to guard WP34; widen it before trusting the "
            "assertions above"
        )


def test_the_prompt_comparison_can_fail() -> None:
    """The prompt guard needs its own teeth, and a different perturbation than staging's.

    ``render_schema_prompt_section`` renders column NAMES, so the extra column that stays
    invisible to staging is exactly what must be visible here. The two perturbations are
    deliberately not interchangeable: each fingerprint is proven against the change its own
    surface is supposed to react to.
    """
    baseline = render_schema_prompt_section(_schemas(foreign_keys=False))
    perturbed = render_schema_prompt_section(
        _schemas(foreign_keys=False, extra_column=True)
    )
    if baseline == perturbed:
        pytest.fail(
            "the rendered schema section did not notice an added declared column — it "
            "cannot guard §3.8's decision that foreign keys stay out of the prompt"
        )
