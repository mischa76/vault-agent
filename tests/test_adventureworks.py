"""WP30: the AdventureWorks instrument and the chained-case machinery (spec §3).

Keyless throughout. The live arm comparison is the maintainer's; these pin the properties
that must hold before a single token is spent — above all that the instrument is a
transcription of somebody else's schema rather than our opinion of it.
"""
import json
from pathlib import Path

import pytest
import yaml

from eval.adventureworks.derive import (
    ARM_B_ORDER,
    build_combined_golden,
    build_combined_source_schema,
    build_golden_mapping,
    build_source_schema,
    case_dir_name,
    derive_all,
    foreign_key_edges,
    subject_areas,
)
from eval.datasets import DATASETS_ROOT, ChainSpec, EvalCase, load_all_cases, load_eval_case
from eval.mapping import load_golden_mapping
from eval.run import score_chain, write_step_vault
from eval.scorers import ScorerResult
from vault_agent.existing_model import DV_MODEL_FILENAME, load_existing_model
from vault_agent.source_schema import load_source_schemas
from vault_agent.state import DVModel, Hub, Satellite, VaultAgentState

EXTRACT = DATASETS_ROOT / "adventureworks" / "schema_extract.json"


@pytest.fixture(scope="module")
def extract() -> dict:
    return json.loads(EXTRACT.read_text(encoding="utf-8"))


# --- The instrument -----------------------------------------------------------------------


def test_notice_ships_beside_the_derived_assets() -> None:
    """§2.1: MIT attribution is a deliverable, not an afterthought."""
    notice = DATASETS_ROOT / "adventureworks" / "NOTICE"
    text = notice.read_text(encoding="utf-8")
    assert "MIT License" in text
    assert "Microsoft" in text


def test_derivation_is_deterministic(extract: dict, tmp_path: Path) -> None:
    """§3.4: re-deriving from the checked-in extract reproduces the shipped assets exactly."""
    derive_all(extract, tmp_path)
    for schema in subject_areas(extract):
        for asset in ("source_schema.yml", "golden_mapping.yml"):
            fresh = (tmp_path / case_dir_name(schema) / asset).read_text(encoding="utf-8")
            shipped = (DATASETS_ROOT / case_dir_name(schema) / asset).read_text(
                encoding="utf-8"
            )
            assert fresh == shipped, f"{schema}/{asset} drifted from the extract"


def test_every_declared_column_traces_to_the_extract(extract: dict) -> None:
    """Acceptance #1: nothing in the instrument was invented by us."""
    truth = {
        (t["schema"], t["name"]): {c["name"] for c in t["columns"]} for t in extract["tables"]
    }
    for schema in subject_areas(extract):
        for table in load_source_schemas(DATASETS_ROOT / case_dir_name(schema) /
                                         "source_schema.yml"):
            key = (schema, table.table)
            assert key in truth, f"{table.table} is not an AdventureWorks table"
            assert set(table.column_names) <= truth[key]


def test_comments_are_verbatim_and_never_authored(extract: dict) -> None:
    """§2.3: descriptions are transcribed; a column Microsoft left blank stays blank."""
    described = {
        (t["schema"], t["name"], c["name"]): c["description"]
        for t in extract["tables"]
        for c in t["columns"]
    }
    checked = 0
    for schema in subject_areas(extract):
        for table in load_source_schemas(DATASETS_ROOT / case_dir_name(schema) /
                                         "source_schema.yml"):
            for column in table.columns:
                upstream = described[(schema, table.table, column.name)]
                assert column.comment == (upstream or None)
                checked += 1
    assert checked == 465  # every column of the five business schemas


def test_golden_holds_only_microsofts_own_natural_keys(extract: dict) -> None:
    """§2.5: a business key here is a single-column AK_* index, never one we picked."""
    for schema in subject_areas(extract):
        declared = {
            (t["name"], ak["columns"][0])
            for t in extract["tables"]
            if t["schema"] == schema
            for ak in t["alternate_keys"]
            if not ak["technical_guid"] and len(ak["columns"]) == 1
        }
        golden = load_golden_mapping(DATASETS_ROOT / case_dir_name(schema) /
                                     "golden_mapping.yml")
        assert {(m.source_table, m.source_column) for m in golden.mappings} == declared


def test_rowguid_is_a_false_friend_never_a_mapping(extract: dict) -> None:
    """The GUID-shadow trap this schema supplies organically: unique, but never a key."""
    for schema in subject_areas(extract):
        golden = load_golden_mapping(DATASETS_ROOT / case_dir_name(schema) /
                                     "golden_mapping.yml")
        assert golden.false_friends, f"{schema} declares no false friend"
        assert all(f.column == "rowguid" for f in golden.false_friends)
        assert all(m.source_column != "rowguid" for m in golden.mappings)


def test_arm_b_order_follows_the_foreign_keys(extract: dict) -> None:
    """§7.1: the step order is derived, not chosen — every area follows what it references."""
    edges = foreign_key_edges(extract)
    seen: set[str] = set()
    for schema in ARM_B_ORDER:
        assert edges[schema] <= seen, f"{schema} precedes an area it references"
        seen.add(schema)
    assert set(ARM_B_ORDER) == set(subject_areas(extract))


def test_arm_a_is_the_union_of_the_areas(extract: dict) -> None:
    """Both arms must receive the SAME inputs, or the comparison is confounded."""
    combined = build_combined_source_schema(extract)["source_schemas"]
    per_area = [
        table
        for schema in ARM_B_ORDER
        for table in build_source_schema(extract, schema)["source_schemas"]
    ]
    assert combined == per_area

    golden = build_combined_golden(extract)
    assert len(golden["mappings"]) == sum(
        len(build_golden_mapping(extract, s)["mappings"]) for s in ARM_B_ORDER
    )


def test_arm_a_requirements_contain_every_area_document() -> None:
    combined = (DATASETS_ROOT / "adventureworks_full" / "requirements.md").read_text(
        encoding="utf-8"
    )
    for schema in ARM_B_ORDER:
        own = (DATASETS_ROOT / case_dir_name(schema) / "requirements.md").read_text(
            encoding="utf-8"
        ).strip()
        assert own in combined, f"{schema}'s blinded document was altered or dropped"


# --- The cases ----------------------------------------------------------------------------


def test_all_adventureworks_cases_load_with_their_gates() -> None:
    cases = {c.name: c for c in load_all_cases() if c.name.startswith("adventureworks")}
    assert set(cases) == {
        "adventureworks_full",
        "adventureworks_humanresources",
        "adventureworks_incremental",
        "adventureworks_person",
        "adventureworks_production",
        "adventureworks_purchasing",
        "adventureworks_sales",
    }
    # §2.5: the name-keyed scorers stay ungated; validation_gate is reported, not gated.
    for case in cases.values():
        assert "construct_f1" not in case.expectations.min_scores
        assert "validation_gate" not in case.expectations.min_scores


def test_chain_case_gates_preservation_at_exactly_one() -> None:
    case = load_eval_case(DATASETS_ROOT / "adventureworks_incremental" / "dataset.yml")
    assert case.chain is not None
    assert list(case.chain.steps) == [case_dir_name(s) for s in ARM_B_ORDER]
    assert case.expectations.min_scores["existing_construct_preservation"] == 1.0


# --- Chained-case machinery (§2.7) ---------------------------------------------------------


def test_chain_is_a_third_input_mode_and_excludes_the_others() -> None:
    spec = ChainSpec(steps=["a", "b"])
    with pytest.raises(ValueError, match="exactly one"):
        EvalCase(name="x", input_document=Path("r.md"), chain=spec, golden={})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="exactly one"):
        EvalCase(name="x", golden={})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="each step supplies its own"):
        EvalCase(name="x", chain=spec, source_schema=Path("s.yml"), golden={})  # type: ignore[arg-type]


def test_chain_step_must_name_an_existing_case(tmp_path: Path) -> None:
    """A typo in `steps` is a load-time error, not a mid-chain surprise after paying for step 1."""
    case_dir = tmp_path / "cases" / "chained"
    case_dir.mkdir(parents=True)
    (case_dir / "dataset.yml").write_text(
        yaml.safe_dump({"name": "chained", "golden": {},
                        "chain": {"steps": ["nope_one", "nope_two"]}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="chain step 'nope_one' has no case"):
        load_eval_case(case_dir / "dataset.yml")


def test_a_dying_chain_leaves_its_completed_steps_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WP14.1 one level down: a five-step chain costs ~$15, so a step-5 failure must not
    discard the four steps already paid for. Before this, persistence was per REPEAT only."""
    import asyncio

    from eval import run as run_mod

    calls = {"n": 0}

    async def fake_run_case_once(case: EvalCase) -> VaultAgentState:
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("credit balance too low")
        return VaultAgentState()

    monkeypatch.setattr(run_mod, "run_case_once", fake_run_case_once)
    monkeypatch.setattr(run_mod, "_score_run", lambda case, state, golden: [])
    monkeypatch.setattr(run_mod, "run_metrics", lambda *a, **k: {"wall_clock_seconds": 1.0})

    case = load_eval_case(DATASETS_ROOT / "adventureworks_incremental" / "dataset.yml")
    runs, metrics, written, failure = asyncio.run(
        run_mod._run_score_write(
            case, None, 1, out_root=tmp_path,
            models={"primary_model": "m", "heavy_model": "h"}, git_sha="abc",
        )
    )

    assert failure is not None and "credit balance" in failure[1]
    assert runs == [] and metrics == []  # the repeat itself produced no aggregate result
    # …but the two completed steps are on disk, named so they are attributable.
    steps = sorted(p.name for p in (tmp_path / case.name).glob("*step*.json"))
    assert len(steps) == 2
    assert "step1-adventureworks_person" in steps[0]
    assert "step2-adventureworks_humanresources" in steps[1]


def test_step_vault_round_trips_through_the_real_wp23_path(tmp_path: Path) -> None:
    """§2.7: a step writes the CLI's artifact and the next step reads it with the CLI's loader."""
    model = DVModel(
        hubs=[Hub(name="hub_person", business_key="business_entity_id",
                  source_entity="Person", description="A party.")],
        satellites=[Satellite(name="sat_person_details", parent="hub_person",
                              attributes=["first_name"], description="Names.")],
    )
    state = VaultAgentState(dv_model=model)

    written = write_step_vault(state, tmp_path / "step1")
    assert written.name == DV_MODEL_FILENAME
    reloaded = load_existing_model(tmp_path / "step1")

    assert reloaded is not None
    assert [h.name for h in reloaded.hubs] == ["hub_person"]
    assert reloaded.hubs[0].business_key == "business_entity_id"
    assert [s.name for s in reloaded.satellites] == ["sat_person_details"]


def _preserving_state(existing: DVModel | None, hubs: list[str]) -> VaultAgentState:
    return VaultAgentState(
        existing_model=existing,
        dv_model=DVModel(
            hubs=[
                Hub(name=name, business_key=f"{name}_bk", source_entity=name,
                    description="x")
                for name in hubs
            ]
        ),
    )


def test_chain_preservation_is_the_minimum_over_steps_not_the_mean() -> None:
    """A promise that held four times out of five was broken — min, never mean."""
    step1 = _preserving_state(None, ["hub_a"])
    kept = DVModel(hubs=step1.dv_model.hubs)
    step2 = _preserving_state(kept, ["hub_a", "hub_b"])           # preserved
    broken = _preserving_state(kept, ["hub_b"])                    # hub_a disappeared

    case = load_eval_case(DATASETS_ROOT / "adventureworks_incremental" / "dataset.yml")
    steps = [(case, step1), (case, step2), (case, broken)]
    results = score_chain(case, steps, None)

    preservation = next(r for r in results if r.name == "existing_construct_preservation")
    assert preservation.score < 1.0  # the broken step decides, not the average
    assert "min over 2 extending step(s)" in preservation.details


def test_chain_preservation_reports_every_step_for_attribution() -> None:
    step1 = _preserving_state(None, ["hub_a"])
    kept = DVModel(hubs=step1.dv_model.hubs)
    step2 = _preserving_state(kept, ["hub_a", "hub_b"])
    case = load_eval_case(DATASETS_ROOT / "adventureworks_incremental" / "dataset.yml")

    results: list[ScorerResult] = score_chain(case, [(case, step1), (case, step2)], None)
    preservation = next(r for r in results if r.name == "existing_construct_preservation")

    assert preservation.score == 1.0
    assert case.name in preservation.details
