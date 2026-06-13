"""Unit tests for the Requirements Parser agent.

The LLM call is stubbed via the ``RequirementExtractor`` protocol so these tests run in
CI without an Anthropic API key (``asyncio_mode = auto`` runs the async tests directly).
"""
from pathlib import Path
from typing import Any

from vault_agent.agents.requirements_parser import RequirementsParserAgent
from vault_agent.state import ParsedRequirement, VaultAgentState

EXAMPLE_DOC = (
    Path(__file__).parents[2] / "examples" / "inputs" / "bank_account_requirements.md"
)


class StubExtractor:
    """Returns a canned payload and records how it was called."""

    def __init__(self, payload: list[dict[str, Any]]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    async def extract(
        self, *, system_prompt: str, document: str
    ) -> list[dict[str, Any]]:
        self.calls.append((system_prompt, document))
        return self.payload


def _valid_payload() -> list[dict[str, Any]]:
    return [
        {
            "id": "REQ-001",
            "text": "A customer can open one or more accounts.",
            "category": "functional",
            "actor": "customer",
            "action": "open",
            "obj": "account",
        },
        {
            "id": "REQ-002",
            "text": "All balance changes must be auditable.",
            "category": "constraint",
        },
    ]


async def test_parses_requirements_from_example_document() -> None:
    stub = StubExtractor(_valid_payload())
    agent = RequirementsParserAgent(extractor=stub)
    state = VaultAgentState(input_documents=[str(EXAMPLE_DOC)])

    result = await agent.run(state)

    assert len(result.requirements) == 2
    assert all(isinstance(r, ParsedRequirement) for r in result.requirements)
    assert result.requirements[0].id == "REQ-001"
    assert result.requirements[0].actor == "customer"
    assert result.requirements[1].actor is None
    assert not result.errors

    # The real document was read from disk and handed to the LLM, alongside the prompt.
    assert len(stub.calls) == 1
    system_prompt, document = stub.calls[0]
    assert "Requirements Parser" in system_prompt
    assert "national customer ID" in document

    # An audit trail entry is recorded.
    assert result.decisions[-1]["agent"] == "requirements_parser"
    assert result.decisions[-1]["requirements_extracted"] == 2


async def test_invalid_records_are_skipped_and_logged() -> None:
    payload = _valid_payload() + [{"id": "REQ-003", "text": "missing category"}]
    stub = StubExtractor(payload)
    agent = RequirementsParserAgent(extractor=stub)
    state = VaultAgentState(input_documents=[str(EXAMPLE_DOC)])

    result = await agent.run(state)

    assert len(result.requirements) == 2
    assert len(result.errors) == 1
    assert "dropped invalid record" in result.errors[0]


async def test_missing_input_file_is_reported() -> None:
    stub = StubExtractor(_valid_payload())
    agent = RequirementsParserAgent(extractor=stub)
    state = VaultAgentState(input_documents=["does/not/exist.md"])

    result = await agent.run(state)

    assert result.requirements == []
    assert len(result.errors) == 1
    assert "not found" in result.errors[0]
    # Extractor must not be called when there is no document to parse.
    assert stub.calls == []


def _make_pdf_bytes(text: str) -> bytes:
    """A minimal single-page PDF whose page renders one extractable text string."""
    content = (f"BT /F1 24 Tf 72 100 Td ({text}) Tj ET").encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 %d\n" % (len(objects) + 1)
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += b"%010d 00000 n \n" % off
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1)
    pdf += b"startxref\n%d\n%%%%EOF" % xref
    return bytes(pdf)


async def test_reads_pdf_document(tmp_path: Path) -> None:
    pdf_path = tmp_path / "reqs.pdf"
    pdf_path.write_bytes(_make_pdf_bytes("REQ-PDF-MARKER"))
    stub = StubExtractor(_valid_payload())
    agent = RequirementsParserAgent(extractor=stub)

    result = await agent.run(VaultAgentState(input_documents=[str(pdf_path)]))

    assert not result.errors
    assert len(stub.calls) == 1
    _, document = stub.calls[0]
    assert "REQ-PDF-MARKER" in document  # PDF text was extracted and routed to the LLM


async def test_reads_docx_document(tmp_path: Path) -> None:
    from docx import Document  # local import; python-docx is a runtime dependency

    docx_path = tmp_path / "reqs.docx"
    doc = Document()
    doc.add_paragraph("REQ-DOCX-MARKER: customers own accounts.")
    doc.save(str(docx_path))
    stub = StubExtractor(_valid_payload())
    agent = RequirementsParserAgent(extractor=stub)

    result = await agent.run(VaultAgentState(input_documents=[str(docx_path)]))

    assert not result.errors
    assert len(stub.calls) == 1
    _, document = stub.calls[0]
    assert "REQ-DOCX-MARKER" in document


async def test_unsupported_extension_is_skipped(tmp_path: Path) -> None:
    bad = tmp_path / "reqs.csv"
    bad.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    good = EXAMPLE_DOC
    stub = StubExtractor(_valid_payload())
    agent = RequirementsParserAgent(extractor=stub)

    result = await agent.run(VaultAgentState(input_documents=[str(bad), str(good)]))

    # The unsupported file is flagged and skipped; the .md document still parses.
    assert any("unsupported document type" in e and "reqs.csv" in e for e in result.errors)
    assert len(stub.calls) == 1  # only the supported doc reached the extractor
    assert len(result.requirements) == 2
