"""Unit tests for the Requirements Parser agent.

The LLM call is stubbed via the ``RequirementExtractor`` protocol so these tests run in
CI without an Anthropic API key (``asyncio_mode = auto`` runs the async tests directly).
"""
from pathlib import Path
from typing import Any

import pytest

from vault_agent.agents.requirements_parser import (
    MAX_DOCUMENT_CHARS,
    RequirementsParserAgent,
    merge_records,
    split_document,
)
from vault_agent.llm import LLMCallError
from vault_agent.state import FlagKind, ParsedRequirement, VaultAgentState

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
    assert not result.flags

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
    assert len(result.flags) == 1
    assert "dropped invalid record" in result.flags[0].message


async def test_missing_input_file_is_reported() -> None:
    stub = StubExtractor(_valid_payload())
    agent = RequirementsParserAgent(extractor=stub)
    state = VaultAgentState(input_documents=["does/not/exist.md"])

    result = await agent.run(state)

    assert result.requirements == []
    assert len(result.flags) == 1
    assert "not found" in result.flags[0].message
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

    assert not result.flags
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

    assert not result.flags
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
    assert any(
        "unsupported document type" in e.message and "reqs.csv" in e.message
        for e in result.flags
    )
    assert len(stub.calls) == 1  # only the supported doc reached the extractor
    assert len(result.requirements) == 2


async def test_oversized_document_is_truncated_and_flagged(tmp_path: Path) -> None:
    """WP3 input-size guard: the extractor sees exactly MAX_DOCUMENT_CHARS characters
    and the truncation is flagged (kind, asset, both sizes) — never silent."""
    original_size = MAX_DOCUMENT_CHARS + 5_000
    big = tmp_path / "big_requirements.md"
    big.write_text("x" * original_size, encoding="utf-8")
    stub = StubExtractor(_valid_payload())
    agent = RequirementsParserAgent(extractor=stub)

    result = await agent.run(VaultAgentState(input_documents=[str(big)]))

    _, document = stub.calls[0]
    assert len(document) == MAX_DOCUMENT_CHARS
    [flag] = [f for f in result.flags if f.kind == FlagKind.INPUT_TRUNCATED]
    assert flag.severity == "advisory"  # pipeline continues on the head
    assert flag.asset == str(big)
    assert str(original_size) in flag.message
    assert str(MAX_DOCUMENT_CHARS) in flag.message


async def test_document_at_the_limit_is_untouched_and_unflagged(tmp_path: Path) -> None:
    doc = tmp_path / "at_limit.md"
    doc.write_text("y" * MAX_DOCUMENT_CHARS, encoding="utf-8")
    stub = StubExtractor(_valid_payload())
    agent = RequirementsParserAgent(extractor=stub)

    result = await agent.run(VaultAgentState(input_documents=[str(doc)]))

    assert not result.flags
    _, document = stub.calls[0]
    assert len(document) == MAX_DOCUMENT_CHARS  # untouched, no truncation


# --- adaptive segmentation ----------------------------------------------------------
# A dense inventory-style document yields several atomic requirements per line, so the
# ANSWER outgrows the output budget while the input stays small (the 30-table scale
# landscape is 3.7k chars and truncated at max_tokens=4096 on 2026-07-27). The parser
# therefore splits only in reaction to a truncated response, never pre-emptively.


class TruncatingExtractor:
    """Truncates while the document exceeds ``fits_under`` chars; then succeeds.

    Emits ``REQ-001``-style ids per call, like the real model, so the merge has genuine
    id collisions to resolve."""

    def __init__(self, fits_under: int) -> None:
        self.fits_under = fits_under
        self.documents: list[str] = []

    async def extract(
        self, *, system_prompt: str, document: str
    ) -> list[dict[str, Any]]:
        self.documents.append(document)
        if len(document) > self.fits_under:
            raise LLMCallError("truncated at max_tokens", truncated=True)
        return [
            {
                "id": "REQ-001",
                "text": f"requirement from {document.strip().splitlines()[0]}",
                "category": "functional",
            }
        ]


_SECTIONED = (
    "# Title\n\nIntro paragraph.\n\n"
    "## Alpha\n\n- alpha one\n- alpha two\n\n"
    "## Beta\n\n- beta one\n- beta two\n\n"
    "## Gamma\n\n- gamma one\n- gamma two\n"
)


def test_split_document_prefers_a_heading_boundary() -> None:
    halves = split_document(_SECTIONED)
    assert halves is not None
    head, tail = halves
    assert head + tail == _SECTIONED  # lossless
    assert tail.startswith("## ")  # cut on a section, not mid-paragraph


def test_split_document_falls_back_to_paragraph_then_line() -> None:
    paragraphs = "one line\n\nsecond para\n\nthird para"
    halves = split_document(paragraphs)
    assert halves is not None and "".join(halves) == paragraphs

    lines = "alpha\nbeta\ngamma"
    halves = split_document(lines)
    assert halves is not None and "".join(halves) == lines


def test_split_document_returns_none_when_indivisible() -> None:
    assert split_document("a single unsplittable line") is None


def test_merge_records_is_identity_for_one_segment() -> None:
    records = _valid_payload()
    merged, dropped = merge_records([records])
    assert merged == records and dropped == 0


def test_merge_records_decollides_ids_and_drops_exact_repeats() -> None:
    seg_a = [{"id": "REQ-001", "text": "alpha", "category": "functional"}]
    seg_b = [
        {"id": "REQ-001", "text": "beta", "category": "functional"},  # id reused
        {"id": "REQ-002", "text": "ALPHA ", "category": "Functional"},  # same as seg_a
    ]
    merged, dropped = merge_records([seg_a, seg_b])
    assert [r["id"] for r in merged] == ["REQ-001", "REQ-001-2"]
    assert dropped == 1


async def test_unsplit_document_makes_exactly_one_call_and_no_flag(tmp_path: Path) -> None:
    """Regression guard: an input that already fits is byte-identical to pre-fix behaviour."""
    doc = tmp_path / "small.md"
    doc.write_text(_SECTIONED, encoding="utf-8")
    stub = StubExtractor(_valid_payload())
    agent = RequirementsParserAgent(extractor=stub)

    result = await agent.run(VaultAgentState(input_documents=[str(doc)]))

    assert len(stub.calls) == 1
    assert stub.calls[0][1] == _SECTIONED  # the whole document, unsegmented
    assert not [f for f in result.flags if f.kind == FlagKind.INPUT_SEGMENTED]
    assert len(result.requirements) == 2


async def test_truncated_response_splits_the_document_and_merges(tmp_path: Path) -> None:
    doc = tmp_path / "dense.md"
    doc.write_text(_SECTIONED, encoding="utf-8")
    extractor = TruncatingExtractor(fits_under=len(_SECTIONED) - 1)
    agent = RequirementsParserAgent(extractor=extractor)

    result = await agent.run(VaultAgentState(input_documents=[str(doc)]))

    # one failed whole-document attempt, then the two halves succeed
    assert len(extractor.documents) == 3
    assert "".join(extractor.documents[1:]) == _SECTIONED  # lossless split
    assert len(result.requirements) == 2  # both segments contributed
    assert [r.id for r in result.requirements] == ["REQ-001", "REQ-001-2"]
    [flag] = [f for f in result.flags if f.kind == FlagKind.INPUT_SEGMENTED]
    assert flag.severity == "advisory"
    assert flag.asset == str(doc)
    assert "2 segment(s)" in flag.message


async def test_non_truncation_error_is_not_split(tmp_path: Path) -> None:
    """Only truncation is a size problem; anything else must surface unchanged."""

    class Failing:
        def __init__(self) -> None:
            self.calls = 0

        async def extract(self, *, system_prompt: str, document: str) -> list[dict[str, Any]]:
            self.calls += 1
            raise LLMCallError("no tool_use block in the response")

    doc = tmp_path / "doc.md"
    doc.write_text(_SECTIONED, encoding="utf-8")
    extractor = Failing()
    agent = RequirementsParserAgent(extractor=extractor)

    with pytest.raises(LLMCallError, match="no tool_use block"):
        await agent.run(VaultAgentState(input_documents=[str(doc)]))
    assert extractor.calls == 1  # no retry, no split


async def test_indivisible_document_surfaces_the_truncation(tmp_path: Path) -> None:
    doc = tmp_path / "one_line.md"
    doc.write_text("a single very dense unsplittable line", encoding="utf-8")
    extractor = TruncatingExtractor(fits_under=0)  # always truncates
    agent = RequirementsParserAgent(extractor=extractor)

    with pytest.raises(LLMCallError, match="truncated"):
        await agent.run(VaultAgentState(input_documents=[str(doc)]))
    assert len(extractor.documents) == 1  # nothing to split, so no further calls
