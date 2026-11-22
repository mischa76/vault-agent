"""E_LINK_KEY_WRONG_COLUMN — written FIRST, 2026-09-15.

The paid chain `20260915T013719090467Z` built `link_business_entity_contact` with an unqualified
`hub_person` participation. Its stage hashes `PERSON_HK` from `BUSINESSENTITYID`, the column
`hub_person` is keyed on — but in `BusinessEntityContact` that column is the organisation
(`BusinessEntityID → BusinessEntity`); the table declares the person as `PersonID → Person`. The
column exists, so the stage builds and the link joins the wrong entity, with no error and no
warning. Audited over the five chains with persisted models: present in step 1 of three.

The signature needs nothing but the declared catalogue: the relation the link binds to declares a
single-column foreign key that resolves to the participation's hub (`resolve_fk_target`, the
proposer's rule) on a column other than the one staging hashes, and declares none on that column.
Refused at model time, where the re-model loop can still act.

Out of scope: role-qualified participations (their column is `role_bk_column`'s — a separate
candidate), participations an alias or translation already repairs, a hashed column the relation
does not have (that fails loudly at build, not silently), relations without declared foreign keys
(WP34 inertness), undeclared relations, pre-existing links.
"""
from __future__ import annotations

from vault_agent.agents.validator import ValidatorAgent
from vault_agent.state import (
    DVModel,
    ForeignKeyRef,
    Hub,
    Link,
    LinkHubRef,
    SourceTable,
    VaultAgentState,
)

CODE = "E_LINK_KEY_WRONG_COLUMN"


def _hub(name: str, key: str, entity: str) -> Hub:
    return Hub(name=name, business_key=key, source_entity=entity, description=entity)


HUBS = [
    _hub("hub_business_entity", "BusinessEntityID", "BusinessEntity"),
    _hub("hub_person", "BusinessEntityID", "Person"),
    _hub("hub_contact_type", "ContactTypeID", "ContactType"),
    _hub("hub_phone_number_type", "PhoneNumberTypeID", "PhoneNumberType"),
]


def _fk(column: str, table: str, referenced: str) -> ForeignKeyRef:
    return ForeignKeyRef(columns=[column], references_table=table, references_columns=[referenced])


CONTACT_FKS = [
    _fk("PersonID", "Person", "BusinessEntityID"),
    _fk("ContactTypeID", "ContactType", "ContactTypeID"),
    _fk("BusinessEntityID", "BusinessEntity", "BusinessEntityID"),
]
CONTACT_COLUMNS = ["BusinessEntityID", "PersonID", "ContactTypeID", "ModifiedDate"]
BASE = [
    SourceTable(table="BusinessEntity", columns=["BusinessEntityID"]),
    SourceTable(table="Person", columns=["BusinessEntityID", "FirstName"]),
    SourceTable(table="ContactType", columns=["ContactTypeID", "Name"]),
    SourceTable(
        table="PersonPhone",
        columns=["BusinessEntityID", "PhoneNumber", "PhoneNumberTypeID"],
        foreign_keys=[
            _fk("BusinessEntityID", "Person", "BusinessEntityID"),
            _fk("PhoneNumberTypeID", "PhoneNumberType", "PhoneNumberTypeID"),
        ],
    ),
]


def _schemas(
    columns: list[str] = CONTACT_COLUMNS, fks: list[ForeignKeyRef] = CONTACT_FKS
) -> list[SourceTable]:
    contact = SourceTable(table="BusinessEntityContact", columns=list(columns),
                          foreign_keys=list(fks))
    return [*BASE, contact]


def _contact_link(role: str | None = None, alias: str | None = None) -> Link:
    return Link(
        name="link_business_entity_contact",
        description="A person is a contact of an organisation.",
        connected_hubs=[
            LinkHubRef(hub="hub_business_entity", role="organisation"),
            LinkHubRef(hub="hub_person", role=role, source_key_column=alias),
            LinkHubRef(hub="hub_contact_type"),
        ],
    )


async def _codes(
    model: DVModel,
    *,
    schemas: list[SourceTable] | None = None,
    existing: DVModel | None = None,
) -> list[tuple[str, str]]:
    state = VaultAgentState(
        dv_model=model,
        source_schemas=_schemas() if schemas is None else schemas,
        existing_model=existing,
    )
    report = (await ValidatorAgent().run(state)).validation_report
    return [(i.code, i.construct) for i in report.issues if i.code == CODE]


async def test_the_person_hashed_from_the_organisation_column_is_refused() -> None:
    codes = await _codes(DVModel(hubs=HUBS, links=[_contact_link()]))
    assert codes == [(CODE, "link_business_entity_contact")]


async def test_a_relation_that_declares_the_key_on_the_hashed_column_passes() -> None:
    phone = Link(name="link_person_phone", description="phone",
                 connected_hubs=["hub_person", "hub_phone_number_type"])
    assert await _codes(DVModel(hubs=HUBS, links=[phone])) == []


async def test_a_ratified_alias_is_the_repair_and_passes() -> None:
    assert await _codes(DVModel(hubs=HUBS, links=[_contact_link(alias="PersonID")])) == []


async def test_out_of_scope_shapes_pass() -> None:
    model = DVModel(hubs=HUBS, links=[_contact_link()])
    # role-qualified: its column is role_bk_column's, not the bare key
    assert await _codes(DVModel(hubs=HUBS, links=[_contact_link(role="contact")])) == []
    # no declared foreign keys: WP34 inertness
    assert await _codes(model, schemas=_schemas(fks=[])) == []
    # the hashed column is absent: a loud build failure, not a silent wrong join
    assert await _codes(model, schemas=_schemas(columns=["PersonID", "ContactTypeID"])) == []
    # ungrounded, and pre-existing
    assert await _codes(model, schemas=[]) == []
    assert await _codes(model, existing=DVModel(hubs=HUBS, links=[_contact_link()])) == []
