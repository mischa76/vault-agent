"""WP23 brownfield mode: loader, merger, additive gates, grandfathering.

All keyless — the modeler's LLM stays injectable and everything under test here is
deterministic. The greenfield byte-identity guard lives in ``test_greenfield_inertness.py``
and runs first by design; these cover what the flag switches on.
"""
from pathlib import Path

import pytest
import yaml

from vault_agent.agents.code_generator import CodeGeneratorAgent
from vault_agent.agents.model_merger import merge_models
from vault_agent.agents.staging_generator import legacy_feeds, multi_source_staging_name
from vault_agent.agents.validator import ValidatorAgent
from vault_agent.existing_model import (
    DV_MODEL_FILENAME,
    load_existing_model,
    render_extension_prompt_section,
)
from vault_agent.state import (
    DVModel,
    FlagKind,
    Hub,
    HubSource,
    Link,
    Satellite,
    VaultAgentState,
)


def _vault() -> DVModel:
    """A small existing vault: one hub with a satellite, one link, one hub without."""
    return DVModel(
        hubs=[
            Hub(name="hub_customer", business_key="customer_id", source_entity="customer",
                description="The customer."),
            Hub(name="hub_account", business_key="account_number", source_entity="account",
                description="The account."),
        ],
        links=[
            Link(name="link_account_customer", connected_hubs=["hub_account", "hub_customer"],
                 description="Ownership."),
        ],
        satellites=[
            Satellite(name="sat_customer_details", parent="hub_customer",
                      attributes=["full_name"], description="Customer attributes."),
        ],
    )


def _state(existing: DVModel | None = None, merged: DVModel | None = None) -> VaultAgentState:
    state = VaultAgentState(document_path="req.md")
    state.existing_model = existing
    if merged is not None:
        state.dv_model = merged
    return state


# ── §2.1 the loader ───────────────────────────────────────────────────────────────────────
def _write_vault(tmp_path: Path, model: DVModel) -> Path:
    out = tmp_path / "vault"
    (out / "metadata").mkdir(parents=True)
    (out / "metadata" / DV_MODEL_FILENAME).write_text(
        yaml.safe_dump(model.model_dump(mode="json"), sort_keys=True), encoding="utf-8"
    )
    return out


def test_loader_round_trips_a_written_vault(tmp_path: Path) -> None:
    """§3.2: what write_outputs writes is exactly what --existing reads back."""
    original = _vault()
    loaded = load_existing_model(_write_vault(tmp_path, original))

    assert loaded is not None
    assert loaded.model_dump() == original.model_dump()


def test_loader_accepts_the_yaml_file_directly(tmp_path: Path) -> None:
    out = _write_vault(tmp_path, _vault())
    loaded = load_existing_model(out / "metadata" / DV_MODEL_FILENAME)

    assert loaded is not None and len(loaded.hubs) == 2


def test_loader_reports_a_pre_wp23_output_directory_attributably(tmp_path: Path) -> None:
    """A directory that predates dv_model.yml is never guessed at from automatedv.yml."""
    out = tmp_path / "old"
    (out / "metadata").mkdir(parents=True)
    (out / "metadata" / "automatedv.yml").write_text("hubs: {}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="regenerate that vault once"):
        load_existing_model(out)


@pytest.mark.parametrize(
    ("content", "match"),
    [("[1, 2]", "expected a mapping"), ("hubs: 5", "not a valid Data Vault model")],
)
def test_loader_rejects_malformed_documents(tmp_path: Path, content: str, match: str) -> None:
    path = tmp_path / "model.yml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=match):
        load_existing_model(path)


def test_loader_treats_an_empty_document_as_greenfield(tmp_path: Path) -> None:
    """The ADR-0004 inertness convention: empty input means "nothing", never an error."""
    path = tmp_path / "model.yml"
    path.write_text("", encoding="utf-8")

    assert load_existing_model(path) is None


def test_missing_path_is_attributable(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no such file or directory"):
        load_existing_model(tmp_path / "nope")


# ── §2.4 the merger ───────────────────────────────────────────────────────────────────────
def test_new_constructs_append_after_the_existing_ones() -> None:
    existing = _vault()
    delta = DVModel(
        hubs=[Hub(name="hub_claim", business_key="claim_id", source_entity="claim",
                  description="A claim.")],
        links=[Link(name="link_claim_account", connected_hubs=["hub_claim", "hub_account"],
                    description="Claim on an account.")],
        satellites=[Satellite(name="sat_claim_details", parent="hub_claim",
                              attributes=["amount"], description="Claim payload.")],
    )
    state = _state(existing)

    merged = merge_models(existing, delta, state)

    assert [h.name for h in merged.hubs] == ["hub_customer", "hub_account", "hub_claim"]
    assert [s.name for s in merged.satellites] == ["sat_customer_details", "sat_claim_details"]
    assert not state.flags


def test_merge_never_mutates_the_existing_model() -> None:
    """The existing model stays the comparison baseline for the gates and the diff."""
    existing = _vault()
    before = existing.model_dump()
    delta = DVModel(hubs=[Hub(name="hub_customer", business_key="customer_id",
                              source_entity="customer", description="",
                              sources=[HubSource(source_table="crm_account",
                                                 business_key_column="cust_no")])])

    merge_models(existing, delta, _state(existing))

    assert existing.model_dump() == before


def test_a_new_feed_on_an_existing_hub_materialises_the_legacy_feed_too() -> None:
    """S1: the hub was single-source, so its original feed is implicit and must be made
    explicit — otherwise the merge would silently drop it when sources becomes non-empty."""
    existing = _vault()
    delta = DVModel(hubs=[Hub(name="hub_customer", business_key="customer_id",
                              source_entity="customer", description="",
                              sources=[HubSource(source_table="crm_account",
                                                 business_key_column="customer_id")])])

    merged = merge_models(existing, delta, _state(existing))

    hub = merged.hubs[0]
    assert [(s.source_table, s.business_key_column) for s in hub.sources] == [
        ("customer", "customer_id"),      # the legacy feed, materialised
        ("crm_account", "customer_id"),   # the extension's new feed
    ]


def test_a_feed_already_present_is_not_added_twice() -> None:
    existing = DVModel(hubs=[Hub(name="hub_customer", business_key="customer_id",
                                 source_entity="customer", description="",
                                 sources=[HubSource(source_table="legacy_cust",
                                                    business_key_column="cust_id")])])
    delta = DVModel(hubs=[Hub(name="hub_customer", business_key="customer_id",
                              source_entity="customer", description="",
                              sources=[HubSource(source_table="LEGACY_CUST",
                                                 business_key_column="CUST_ID")])])

    merged = merge_models(existing, delta, _state(existing))

    assert len(merged.hubs[0].sources) == 1  # normalised dedup, per E_HUB_DUP_FEED semantics


def test_changing_an_existing_hubs_business_key_is_a_flagged_conflict() -> None:
    existing = _vault()
    delta = DVModel(hubs=[Hub(name="hub_customer", business_key="crm_guid",
                              source_entity="customer", description="")])
    state = _state(existing)

    merged = merge_models(existing, delta, state)

    assert merged.hubs[0].business_key == "customer_id"  # unchanged, never applied
    [flag] = [f for f in state.flags if f.kind == FlagKind.EXTENSION_CONFLICT]
    assert flag.severity == "error" and flag.asset == "hub_customer"


@pytest.mark.parametrize("kind", ["link", "satellite"])
def test_restating_an_existing_link_or_satellite_is_a_flagged_conflict(kind: str) -> None:
    existing = _vault()
    delta = (
        DVModel(links=[Link(name="link_account_customer",
                            connected_hubs=["hub_account", "hub_customer"],
                            description="restated")])
        if kind == "link"
        else DVModel(satellites=[Satellite(name="sat_customer_details", parent="hub_customer",
                                           attributes=["full_name", "email"],
                                           description="restated")])
    )
    state = _state(existing)

    merged = merge_models(existing, delta, state)

    [flag] = [f for f in state.flags if f.kind == FlagKind.EXTENSION_CONFLICT]
    assert flag.severity == "error"
    # The existing construct survives untouched — the conflicting delta is dropped.
    assert merged.satellites[0].attributes == ["full_name"]
    assert len(merged.links) == 1


# ── §2.5 the additive gates ───────────────────────────────────────────────────────────────
async def _codes(existing: DVModel, merged: DVModel) -> list[str]:
    state = await ValidatorAgent().run(_state(existing, merged))
    return [issue.code for issue in state.validation_report.issues]


async def test_gates_are_inert_on_a_greenfield_run() -> None:
    codes = await _codes_greenfield()
    assert not [c for c in codes if c.startswith(("E_EXISTING", "W_EXISTING"))]


async def _codes_greenfield() -> list[str]:
    state = await ValidatorAgent().run(_state(None, _vault()))
    return [issue.code for issue in state.validation_report.issues]


async def test_removing_an_existing_construct_is_an_error() -> None:
    existing = _vault()
    merged = existing.model_copy(deep=True)
    merged.satellites.clear()

    assert "E_EXISTING_REMOVED" in await _codes(existing, merged)


async def test_changing_an_existing_business_key_is_an_error() -> None:
    existing = _vault()
    merged = existing.model_copy(deep=True)
    merged.hubs[0].business_key = "something_else"

    assert "E_EXISTING_BK_CHANGED" in await _codes(existing, merged)


async def test_changing_an_existing_links_grain_is_an_error() -> None:
    existing = _vault()
    merged = existing.model_copy(deep=True)
    merged.links[0].connected_hubs = ["hub_account", "hub_customer", "hub_customer"]

    assert "E_EXISTING_GRAIN_CHANGED" in await _codes(existing, merged)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda sat: sat.attributes.append("email"), id="attribute-growth"),
        pytest.param(lambda sat: sat.attributes.clear(), id="attribute-shrink"),
        pytest.param(lambda sat: setattr(sat, "sat_type", "multi_active"), id="type-change"),
        pytest.param(lambda sat: setattr(sat, "parent", "hub_account"), id="parent-change"),
        pytest.param(lambda sat: setattr(sat, "source_table", "raw_x"), id="source-change"),
    ],
)
async def test_reshaping_an_existing_satellite_is_an_error(mutate) -> None:  # type: ignore[no-untyped-def]
    """Charter Q3: GROWTH counts too — a new attribute on a satellite with history is a
    backfill, so it is a migration, not an extension."""
    existing = _vault()
    merged = existing.model_copy(deep=True)
    mutate(merged.satellites[0])

    assert "E_EXISTING_SAT_RESHAPED" in await _codes(existing, merged)


async def test_legitimate_extensions_are_inventoried_as_warnings() -> None:
    """W_EXISTING_EXTENDED is the review queue's extension category (charter Q5)."""
    existing = _vault()
    merged = existing.model_copy(deep=True)
    merged.hubs[0].sources = [
        HubSource(source_table="customer", business_key_column="customer_id"),
        HubSource(source_table="crm_account", business_key_column="cust_no"),
    ]
    merged.satellites.append(
        Satellite(name="sat_customer_marketing", parent="hub_customer",
                  attributes=["segment"], description="New concern, new satellite.")
    )
    state = await ValidatorAgent().run(_state(existing, merged))

    extended = [i for i in state.validation_report.issues if i.code == "W_EXISTING_EXTENDED"]
    assert {i.construct for i in extended} == {"hub_customer", "sat_customer_marketing"}
    assert state.validation_report.passed  # advisory only: an extension is not a failure


# ── §2.6 grandfathering ───────────────────────────────────────────────────────────────────
def test_a_grandfathered_feed_keeps_its_legacy_staging_name() -> None:
    """Renaming a materialised staging model would drop and rebuild a table with history."""
    existing = _vault()
    hub = Hub(name="hub_customer", business_key="customer_id", source_entity="customer",
              description="", sources=[
                  HubSource(source_table="customer", business_key_column="customer_id"),
                  HubSource(source_table="crm_account", business_key_column="cust_no"),
              ])
    legacy = legacy_feeds(existing)

    assert multi_source_staging_name(hub, hub.sources[0], legacy) == "stg_customer"
    assert multi_source_staging_name(hub, hub.sources[1], legacy) == "stg_customer_crm_account"


def test_greenfield_multi_source_naming_stays_symmetric() -> None:
    """No existing model = nothing grandfathered: the WP10 shape is untouched."""
    hub = Hub(name="hub_customer", business_key="customer_id", source_entity="customer",
              description="", sources=[
                  HubSource(source_table="crm", business_key_column="cust_no"),
                  HubSource(source_table="victor", business_key_column="partn_id"),
              ])

    assert multi_source_staging_name(hub, hub.sources[0], set()) == "stg_customer_crm"
    assert multi_source_staging_name(hub, hub.sources[1], set()) == "stg_customer_victor"


async def test_an_existing_satellite_is_not_split_when_its_hub_gains_a_feed() -> None:
    """Charter Q2: existing satellites keep their names and their legacy binding; only NEW
    satellites on that hub follow the WP10 per-source shape."""
    existing = _vault()
    merged = existing.model_copy(deep=True)
    merged.hubs[0].sources = [
        HubSource(source_table="customer", business_key_column="customer_id"),
        HubSource(source_table="crm_account", business_key_column="cust_no"),
    ]
    merged.satellites.append(
        Satellite(name="sat_customer_marketing", parent="hub_customer",
                  attributes=["segment"], description="")
    )
    state = _state(existing, merged)

    await CodeGeneratorAgent().run(state)

    generated = set(state.artifacts.dbt_models)
    # The pre-existing satellite: one model, original name, no per-source split.
    assert "sat_customer_details" in generated
    assert not [n for n in generated if n.startswith("sat_customer_details_")]
    # The new satellite: split per feed, WP10 naming.
    assert "sat_customer_marketing_customer" in generated
    assert "sat_customer_marketing_crm_account" in generated
    # The legacy staging model keeps its name; only the new feed gains a suffixed one.
    assert "stg_customer" in state.artifacts.staging_models
    assert "stg_customer_crm_account" in state.artifacts.staging_models
    assert "stg_customer_customer" not in state.artifacts.staging_models


# ── §2.3 the extension prompt section ─────────────────────────────────────────────────────
def test_extension_prompt_section_is_empty_on_a_greenfield_run() -> None:
    """Byte-identical greenfield prompt — the WP16 fixture and prompt caching are untouched."""
    assert render_extension_prompt_section(None) == ""


def test_extension_prompt_section_inventories_the_existing_vault() -> None:
    section = render_extension_prompt_section(_vault())

    assert "IMMUTABLE" in section
    assert "hub **hub_customer** — business key `customer_id`" in section
    assert "link **link_account_customer** — connects hub_account, hub_customer" in section
    assert "satellite **sat_customer_details** — standard, on hub_customer" in section
    assert "Emit ONLY the delta" in section
    assert "NEW satellite on the same parent" in section


def test_an_already_multi_source_hub_keeps_its_suffixed_names() -> None:
    """Only ONE feed can own the unsuffixed stg_<entity> name — the implicit feed of a hub
    that was single-source. A hub already multi-source in the existing vault had WP10
    suffixed names generated for it; grandfathering those would both rename them and
    collapse every one of them onto the same name."""
    existing = DVModel(hubs=[
        Hub(name="hub_customer", business_key="customer_id", source_entity="customer",
            description="", sources=[
                HubSource(source_table="crm", business_key_column="cust_no"),
                HubSource(source_table="victor", business_key_column="partn_id"),
            ])
    ])
    extended = existing.hubs[0].model_copy(deep=True)
    extended.sources.append(HubSource(source_table="sap", business_key_column="kunde"))
    legacy = legacy_feeds(existing)

    names = [multi_source_staging_name(extended, s, legacy) for s in extended.sources]

    assert names == ["stg_customer_crm", "stg_customer_victor", "stg_customer_sap"]
    assert len(set(names)) == 3  # no collision


# ── §2.7 the diff artifact ────────────────────────────────────────────────────────────────
async def _extended_state() -> VaultAgentState:
    """A mixed S1+S2 extension: an existing hub gains a feed and a new satellite; a whole
    new hub+satellite arrive."""
    existing = _vault()
    merged = existing.model_copy(deep=True)
    merged.hubs[0].sources = [
        HubSource(source_table="customer", business_key_column="customer_id"),
        HubSource(source_table="crm_account", business_key_column="cust_no"),
    ]
    merged.satellites.append(
        Satellite(name="sat_customer_marketing", parent="hub_customer",
                  attributes=["segment"], description="New concern.")
    )
    merged.hubs.append(
        Hub(name="hub_campaign", business_key="campaign_id", source_entity="campaign",
            description="A campaign.")
    )
    merged.satellites.append(
        Satellite(name="sat_campaign_details", parent="hub_campaign",
                  attributes=["title"], description="Campaign payload.")
    )
    state = _state(existing, merged)
    state.existing_source = "output/bank"
    await CodeGeneratorAgent().run(state)
    return state


async def test_extension_diff_classifies_unchanged_extended_and_new() -> None:
    state = await _extended_state()
    diff = state.artifacts.extension_diff

    assert set(diff["extended"]) == {"hub_customer"}
    assert "1 source feed(s): crm_account.cust_no" in diff["extended"]["hub_customer"][0]
    assert "sat_customer_marketing" in diff["extended"]["hub_customer"][1]
    assert set(diff["new"]) == {
        "hub_campaign", "sat_customer_marketing", "sat_campaign_details"
    }
    assert set(diff["unchanged"]) == {
        "hub_account", "link_account_customer", "sat_customer_details"
    }


async def test_extension_diff_names_the_hub_sql_that_actually_changed() -> None:
    """§3.6: file-change attribution must name the hub SQL (it now unions a second staging
    model) and NOT the untouched satellites."""
    state = await _extended_state()
    changed = state.artifacts.extension_diff["changed_files"]

    assert "models/raw_vault/hub_customer.sql" in changed["hub_customer"]
    assert "sat_customer_details" not in changed
    assert "link_account_customer" not in changed


async def test_extension_diff_markdown_renders_the_three_sections(tmp_path: Path) -> None:
    from vault_agent.cli import write_outputs
    from vault_agent.extension_diff import DIFF_FILENAME

    state = await _extended_state()
    counts = write_outputs(state, tmp_path / "out")
    text = (tmp_path / "out" / DIFF_FILENAME).read_text(encoding="utf-8")

    assert counts["extension_diff"] == 1
    assert "extended the vault at `output/bank`" in text
    assert "## Unchanged (3)" in text and "## Extended (1)" in text and "## New (3)" in text
    assert "changed file: `models/raw_vault/hub_customer.sql`" in text


# ── §2.8 the delta-ADR ────────────────────────────────────────────────────────────────────
async def test_delta_adr_documents_only_the_delta_and_says_what_it_extends() -> None:
    from vault_agent.agents.adr_author import AdrAuthorAgent

    state = await _extended_state()
    result = await AdrAuthorAgent(today="2026-07-29").run(state)
    adr = result.adrs[0]

    assert "## Extends" in adr
    assert "`output/bank`" in adr
    assert "2 hub(s), 1 link(s) and 1 satellite(s)" in adr
    assert "extension-diff.md" in adr
    # Only the delta is listed; the existing constructs are not re-documented.
    assert "### Hubs (1)" in adr and "**hub_campaign**" in adr
    assert "**hub_account**" not in adr
    assert "**sat_customer_details**" not in adr
    assert "**sat_customer_marketing**" in adr


async def test_greenfield_adr_has_no_extends_section() -> None:
    from vault_agent.agents.adr_author import AdrAuthorAgent

    state = _state(None, _vault())
    result = await AdrAuthorAgent(today="2026-07-29").run(state)

    assert "## Extends" not in result.adrs[0]
    assert "**hub_account**" in result.adrs[0]  # greenfield lists everything, as before


async def test_report_extension_section_renders_the_same_data(tmp_path: Path) -> None:
    from vault_agent.report import build_report

    state = await _extended_state()
    html = build_report(state)

    assert "<h2>Extension</h2>" in html
    assert "hub_customer" in html and "models/raw_vault/hub_customer.sql" in html
    assert "hub_campaign" in html


def test_report_has_no_extension_section_on_a_greenfield_run() -> None:
    from vault_agent.report import build_report

    assert "<h2>Extension</h2>" not in build_report(_state(None, _vault()))


async def test_extension_section_escapes_hostile_construct_names() -> None:
    """report.py's posture: every state string is hostile — including a diff's keys."""
    from vault_agent.report import build_report

    state = _state(_vault(), _vault())
    state.artifacts.extension_diff = {
        "unchanged": [], "extended": {"<script>x</script>": ["gained"]},
        "changed_files": {}, "new": {},
    }
    html = build_report(state)

    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


async def test_grounding_skips_pre_existing_constructs_on_an_extension_run() -> None:
    """The declared schema describes the NEW source; the existing constructs were grounded
    against a different one when they were created. Re-checking them is noise — found by
    the live bank_extension run, which it pushed over its warning tolerance."""
    from vault_agent.state import SourceTable

    existing = _vault()
    merged = existing.model_copy(deep=True)
    merged.hubs.append(
        Hub(name="hub_campaign", business_key="nowhere_column", source_entity="campaign",
            description="")
    )
    state = _state(existing, merged)
    state.source_schemas = [SourceTable(table="crm_campaign", columns=["campaign_code"])]

    result = await ValidatorAgent().run(state)
    ungrounded = [
        i for i in result.validation_report.issues if i.code == "W_BK_NOT_IN_SOURCE"
    ]

    # Only the NEW hub is judged against the CRM schema; hub_customer/hub_account are not.
    assert [i.construct for i in ungrounded] == ["hub_campaign"]


def test_a_restated_hub_naming_the_new_source_entity_is_not_a_conflict() -> None:
    """Hub.source_entity is required, so a delta adding a feed must supply one — and the only
    sensible value it has is the NEW source's. Flagging that as a conflict fired on all three
    live runs against a delta that was correct."""
    existing = _vault()
    delta = DVModel(hubs=[Hub(name="hub_customer", business_key="customer_id",
                              source_entity="crm_contact", description="",
                              sources=[HubSource(source_table="crm_contact",
                                                 business_key_column="customer_id")])])
    state = _state(existing)

    merged = merge_models(existing, delta, state)

    assert not [f for f in state.flags if f.kind == FlagKind.EXTENSION_CONFLICT]
    assert merged.hubs[0].source_entity == "customer"  # the existing value is kept


# ── ADR-0011 / WP28: satellite feed binding ───────────────────────────────────────────────
def _multi_source_hub(*feeds: tuple[str, str]) -> Hub:
    return Hub(
        name="hub_customer", business_key="customer_id", source_entity="customer",
        description="",
        sources=[HubSource(source_table=t, business_key_column=c) for t, c in feeds],
    )


def _sat_with(source_table: str | None, sat_type: str = "standard") -> Satellite:
    return Satellite(
        name="sat_customer_marketing", parent="hub_customer",
        attributes=["marketing_segment"], description="", source_table=source_table,
        sat_type=sat_type,  # type: ignore[arg-type]
        child_dependent_key=["marketing_segment"] if sat_type == "multi_active" else [],
    )


@pytest.mark.parametrize(
    ("source_table", "expected"),
    [
        pytest.param("crm_contact", False, id="names-a-feed"),
        pytest.param("CRM_CONTACT", False, id="names-a-feed-normalised"),
        pytest.param("crm_contact_address", True, id="names-a-non-feed"),
        pytest.param(None, False, id="no-source-table"),
    ],
)
def test_predicate_errors_only_on_a_table_that_is_not_a_feed(
    source_table: str | None, expected: bool
) -> None:
    from vault_agent.rules.dv2_rules import source_table_on_multi_source_hub

    hub = _multi_source_hub(("customer", "customer_id"), ("crm_contact", "customer_id"))

    assert source_table_on_multi_source_hub(_sat_with(source_table), hub) is expected


def test_a_grandfathered_legacy_feed_counts_as_a_feed() -> None:
    """WP23's merger materialises a single-source hub's implicit feed, so the brownfield case
    — the one that motivated ADR-0011 — needs no special case. Asserted, not assumed."""
    from vault_agent.rules.dv2_rules import satellite_feed, source_table_on_multi_source_hub

    existing = DVModel(hubs=[Hub(name="hub_customer", business_key="customer_id",
                                 source_entity="customer", description="")])
    delta = DVModel(hubs=[Hub(name="hub_customer", business_key="customer_id",
                              source_entity="crm_contact", description="",
                              sources=[HubSource(source_table="crm_contact",
                                                 business_key_column="customer_id")])])
    merged = merge_models(existing, delta, _state(existing))
    hub = merged.hubs[0]

    # The legacy feed (source_entity 'customer') is matchable...
    assert source_table_on_multi_source_hub(_sat_with("customer"), hub) is False
    feed = satellite_feed(_sat_with("customer"), hub)
    assert feed is not None and feed.source_table == "customer"
    # ...and so is the new one.
    assert source_table_on_multi_source_hub(_sat_with("crm_contact"), hub) is False


def test_effectivity_satellites_stay_excluded() -> None:
    from vault_agent.rules.dv2_rules import satellite_feed

    hub = _multi_source_hub(("customer", "customer_id"), ("crm_contact", "customer_id"))

    assert satellite_feed(_sat_with("crm_contact", "effectivity"), hub) is None


async def test_a_multi_active_satellite_may_bind_to_a_feed() -> None:
    """The type restriction belongs to the SPLIT; a satellite bound to one feed is ordinary."""
    model = DVModel(
        hubs=[_multi_source_hub(("customer", "customer_id"), ("crm_contact", "customer_id"))],
        satellites=[_sat_with("crm_contact", "multi_active")],
    )
    state = VaultAgentState(dv_model=model)

    await CodeGeneratorAgent().run(state)

    assert "sat_customer_marketing" in state.artifacts.dbt_models
    assert not [f for f in state.flags if f.kind == FlagKind.GENERATION_GAP]


async def test_a_feed_bound_satellite_binds_to_the_legacy_staging_name() -> None:
    """Grandfathering and feed binding compose: an extension satellite naming the LEGACY feed
    must read the unsuffixed staging model, not a renamed one."""
    existing = DVModel(hubs=[Hub(name="hub_customer", business_key="customer_id",
                                 source_entity="customer", description="")])
    merged = DVModel(
        hubs=[_multi_source_hub(("customer", "customer_id"), ("crm_contact", "customer_id"))],
        satellites=[_sat_with("customer")],
    )
    state = _state(existing, merged)

    await CodeGeneratorAgent().run(state)

    assert "stg_customer" in state.artifacts.dbt_models["sat_customer_marketing"]
    assert "stg_customer_customer" not in state.artifacts.staging_models
