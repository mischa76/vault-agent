"""WP117 (ADR-0019) — `vault-agent draft-requirements`: the catalogue drafted into a document a
human corrects, typed as unreviewed, read by `run` with a flag. Committed red before the
change. Keyless."""
from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from tests.test_agents.test_adr_author import _state as _adr_state
from tests.test_agents.test_requirements_parser import StubExtractor, _valid_payload
from vault_agent.agents.adr_author import AdrAuthorAgent
from vault_agent.agents.orchestrator import REVIEW_FLAG_ROLES
from vault_agent.agents.requirements_parser import RequirementsParserAgent
from vault_agent.cli import app
from vault_agent.draft_requirements import (
    DRAFT_MARKER,
    DraftHeader,
    classify,
    draft_document,
    natural_key,
    read_draft_header,
)
from vault_agent.source_schema import load_source_schemas
from vault_agent.state import FlagKind, ForeignKeyRef, SourceTable, VaultAgentState

ROOT = Path(__file__).resolve().parents[1]
AREAS = ("Person", "HumanResources", "Production", "Purchasing", "Sales")
runner = CliRunner()


def _t(name: str, columns: list[dict[str, str]], **kw: object) -> SourceTable:
    return SourceTable.model_validate({"table": name, "schema": "S", "columns": columns, **kw})


# ── the header ─────────────────────────────────────────────────────────────────────────────
def test_the_header_is_typed_and_round_trips() -> None:
    header = DraftHeader(source="inputs/source_schema.yml", date="2026-10-31")
    text = header.render() + "\n# Requirements\n"
    assert text.startswith("<!-- " + DRAFT_MARKER)
    read = read_draft_header(text)
    assert read == header and read.status == "unreviewed"
    reviewed = text.replace("status: unreviewed", "status: reviewed")
    assert read_draft_header(reviewed) is not None
    assert read_draft_header(reviewed).status == "reviewed"  # type: ignore[union-attr]
    assert read_draft_header("# An analyst's document\n") is None
    assert read_draft_header("<!-- a comment that is not ours -->\n# Doc\n") is None


# ── the rules, on miniature tables ─────────────────────────────────────────────────────────
def test_relationship_subtype_and_entity_by_how_the_keys_cover_the_primary_key() -> None:
    a = _t("A", [{"name": "AID"}], primary_key=["AID"])
    b = _t("B", [{"name": "BID"}], primary_key=["BID"])
    fk_a = ForeignKeyRef(columns=["AID"], references_table="A", references_columns=["AID"])
    fk_b = ForeignKeyRef(columns=["BID"], references_table="B", references_columns=["BID"])
    rel = _t("AB", [{"name": "AID"}, {"name": "BID"}, {"name": "Since"}],
             primary_key=["AID", "BID"], foreign_keys=[fk_a, fk_b])
    sub = _t("Emp", [{"name": "AID"}, {"name": "Rank"}], primary_key=["AID"], foreign_keys=[fk_a])
    assert classify(a)[0] == "entity" and classify(b)[0] == "entity"
    assert classify(rel)[0] == "relationship" and len(classify(rel)[1]) == 2
    assert classify(sub)[0] == "subtype"


def test_the_identifier_is_the_single_column_unique_key_unless_it_is_a_guid() -> None:
    product = _t("Product", [{"name": "ProductID", "type": "int"},
                             {"name": "ProductNumber", "type": "nvarchar(25)"},
                             {"name": "rowguid", "type": "uniqueidentifier"}],
                 primary_key=["ProductID"], unique_keys=[["rowguid"], ["ProductNumber"]])
    assert natural_key(product) == ["ProductNumber"]
    guid_only = _t("Thing", [{"name": "ThingID", "type": "int"},
                             {"name": "rowguid", "type": "UUID"}],
                   primary_key=["ThingID"], unique_keys=[["rowguid"]])
    assert natural_key(guid_only) is None
    text = draft_document([guid_only], "things", source="s.yml", date="2026-10-31")
    assert "identified by its **thing id**" in text
    assert "rowguid" not in text.lower().split("status")[1]


# ── the six documents regenerate from the product ──────────────────────────────────────────
def test_every_drafted_area_document_is_the_products_output_from_its_schema() -> None:
    for area in AREAS:
        case = ROOT / "eval" / "datasets" / f"adventureworks_drafted_{area.lower()}"
        tables = load_source_schemas(case / "source_schema.yml")
        text = draft_document(tables, area, date="2026-10-30",
                              source="eval.adventureworks.derive (schema_extract.json)",
                              technical=("ModifiedDate", "rowguid"))
        assert text == (case / "requirements.md").read_text(encoding="utf-8"), area
        assert read_draft_header(text) is not None


def test_the_eval_module_delegates_to_the_product() -> None:
    from eval.adventureworks.draft_requirements import draft

    extract_path = ROOT / "eval/datasets/adventureworks/schema_extract.json"
    extract = json.loads(extract_path.read_text(encoding="utf-8"))
    case = ROOT / "eval" / "datasets" / "adventureworks_drafted_person"
    assert draft(extract, "Person") == (case / "requirements.md").read_text(encoding="utf-8")


# ── the parser's flag and the ADR's provenance ─────────────────────────────────────────────
async def _parsed(tmp_path: Path, text: str) -> VaultAgentState:
    doc = tmp_path / "req.md"
    doc.write_text(text, encoding="utf-8")
    state = VaultAgentState(input_documents=[str(doc)])
    return await RequirementsParserAgent(extractor=StubExtractor(_valid_payload())).run(state)


async def test_an_unreviewed_draft_is_flagged_a_reviewed_one_not(tmp_path: Path) -> None:
    header = DraftHeader(source="s.yml", date="2026-10-31").render()
    flagged = await _parsed(tmp_path, header + "\n# Draft\n\n- **REQ-001** x\n")
    [flag] = [f for f in flagged.flags if f.kind == FlagKind.REQUIREMENTS_UNREVIEWED]
    assert flag.asset == str(tmp_path / "req.md") and "status: reviewed" in flag.message
    assert REVIEW_FLAG_ROLES[FlagKind.REQUIREMENTS_UNREVIEWED] == "decision"
    reviewed = await _parsed(tmp_path, header.replace("unreviewed", "reviewed") + "\n# Draft\n")
    assert not [f for f in reviewed.flags if f.kind == FlagKind.REQUIREMENTS_UNREVIEWED]
    authored = await _parsed(tmp_path, "# An analyst's document\n\n- **REQ-001** x\n")
    assert not [f for f in authored.flags if f.kind == FlagKind.REQUIREMENTS_UNREVIEWED]


async def test_the_adr_names_a_drafted_documents_provenance() -> None:
    state = _adr_state()
    state.input_documents = ["inputs/req.md"]
    state.flag("requirements_parser", "unreviewed", kind=FlagKind.REQUIREMENTS_UNREVIEWED,
               asset="inputs/req.md")
    adr = (await AdrAuthorAgent(today="2026-10-31").run(state)).adrs[0]
    assert "inputs/req.md" in adr and "drafted from the catalogue" in adr
    assert "unreviewed" in adr
    plain = (await AdrAuthorAgent(today="2026-10-31").run(_adr_state())).adrs[0]
    assert "drafted from the catalogue" not in plain


# ── the command ────────────────────────────────────────────────────────────────────────────
def test_the_command_writes_the_document_and_refuses_a_bad_schema(tmp_path: Path) -> None:
    out = tmp_path / "req.md"
    result = runner.invoke(app, [
        "draft-requirements", "--out", str(out), "--area", "bank",
        "--source-schema", str(ROOT / "examples/inputs/bank_source_schema.yml"),
    ])
    assert result.exit_code == 0, result.output
    text = out.read_text(encoding="utf-8")
    header = read_draft_header(text)
    assert header is not None and header.status == "unreviewed"
    assert header.source.endswith("bank_source_schema.yml")
    assert "# Requirements drafted from the source catalogue: bank" in text
    assert "- **REQ-001**" in text
    bad = tmp_path / "bad.yml"
    bad.write_text("source_schemas: [{table: 1, columns: 3}]\n", encoding="utf-8")
    refused = runner.invoke(app, ["draft-requirements", "--source-schema", str(bad),
                                  "--out", str(out)])
    assert refused.exit_code == 1 and "bad.yml" in refused.output
