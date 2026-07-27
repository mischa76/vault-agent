"""Requirements Parser agent.

Reads the raw requirements documents listed in ``VaultAgentState.input_documents``
(``.md``/``.txt`` plain text, ``.pdf`` via pypdf, ``.docx`` via python-docx; unknown
extensions are flagged and skipped) and extracts an atomic, IREB-aligned list of
``ParsedRequirement`` records into ``VaultAgentState.requirements``.

Structured output is obtained via Anthropic tool-use: the model is forced to call the
``emit_requirements`` tool whose input schema is derived from ``ParsedRequirement`` itself,
so the returned payload validates back into the pydantic model with no ad-hoc parsing.

The Anthropic client is only constructed lazily (and ``config.settings`` only imported
then), so unit tests can inject a stub extractor and run without an API key.
"""
import logging
import re
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from vault_agent.agents.base import BaseAgent
from vault_agent.llm import LLMCallError
from vault_agent.state import FlagKind, ParsedRequirement, VaultAgentState

logger = logging.getLogger(__name__)

_TOOL_NAME = "emit_requirements"
_MAX_TOKENS = 8192

# Guard against blowing the model's context window: ~4 chars/token heuristic,
# capped well below the 200k window to leave room for system prompt + output.
MAX_DOCUMENT_CHARS = 400_000

# How often a document may be halved when the model's answer does not fit the output
# budget: 4 levels = up to 16 segments, far past any observed need (the 30-table scale
# landscape needs one split). A deeper recursion means the per-segment answer is not
# shrinking, so the cause is not size — better to surface the error than to keep paying.
_MAX_SPLIT_DEPTH = 4

# Boundary classes for splitting a document, best first: a markdown heading starts a new
# section, a blank line separates paragraphs/list blocks, a newline is the last resort
# that still never cuts mid-sentence.
_BOUNDARY_PATTERNS = (
    re.compile(r"^#{1,6} ", re.MULTILINE),
    re.compile(r"\n\s*\n"),
    re.compile(r"\n"),
)


def split_document(text: str) -> tuple[str, str] | None:
    """Halve ``text`` at the structural boundary closest to its midpoint.

    Tries the boundary classes in ``_BOUNDARY_PATTERNS`` order, so a document is cut
    between sections before it is cut between paragraphs, and between paragraphs before
    between lines — a segment is therefore always a whole number of structural units and
    a requirement is never severed mid-sentence. Returns ``None`` when the text has no
    interior boundary at all (a single line), which ends the recursion in :func:`_extract`.
    """
    midpoint = len(text) / 2
    for pattern in _BOUNDARY_PATTERNS:
        offsets = [m.start() for m in pattern.finditer(text) if 0 < m.start() < len(text)]
        if not offsets:
            continue
        cut = min(offsets, key=lambda offset: abs(offset - midpoint))
        head, tail = text[:cut], text[cut:]
        if head.strip() and tail.strip():
            return head, tail
    return None


def merge_records(
    segments: list[list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], int]:
    """Concatenate per-segment records, dropping exact repeats and de-colliding ids.

    Each segment is extracted by its own call, so the model numbers every segment from
    scratch: without this, two segments both emit ``REQ-001``. Records identical in
    (text, category) are the same requirement seen twice across a cut and are dropped;
    a surviving record whose id is already taken gets a deterministic ``-2``/``-3``
    suffix. Both branches are no-ops for a single segment, so an unsplit document
    round-trips byte-identically. Returns the merged records and the number dropped."""
    merged: list[dict[str, Any]] = []
    seen_content: set[tuple[str, str]] = set()
    seen_ids: dict[str, int] = {}
    dropped = 0
    for records in segments:
        for record in records:
            content = (
                str(record.get("text", "")).strip().casefold(),
                str(record.get("category", "")).strip().casefold(),
            )
            if content in seen_content:
                dropped += 1
                continue
            seen_content.add(content)
            record_id = str(record.get("id", ""))
            if record_id and record_id in seen_ids:
                seen_ids[record_id] += 1
                record = {**record, "id": f"{record_id}-{seen_ids[record_id]}"}
            elif record_id:
                seen_ids[record_id] = 1
            merged.append(record)
    return merged, dropped


def _extract_pdf_text(path: Path) -> str:
    """Extract text from a PDF, one page per line-group, via pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx_text(path: Path) -> str:
    """Extract text from a .docx, one paragraph per line, via python-docx."""
    from docx import Document

    document = Document(str(path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _tool_schema() -> dict[str, Any]:
    """Wrap the ParsedRequirement JSON schema as an array-valued tool input."""
    item_schema = ParsedRequirement.model_json_schema()
    return {
        "type": "object",
        "properties": {
            "requirements": {
                "type": "array",
                "items": item_schema,
                "description": "One entry per atomic requirement found in the document.",
            }
        },
        "required": ["requirements"],
    }


class RequirementExtractor(Protocol):
    """Turns a single document into a list of raw requirement records.

    Implemented for real by :class:`AnthropicRequirementExtractor`; stubbed in tests.
    """

    async def extract(
        self, *, system_prompt: str, document: str
    ) -> list[dict[str, Any]]: ...


class AnthropicRequirementExtractor:
    """Default extractor backed by the shared forced-tool-use call path."""

    def __init__(self, model: str | None = None) -> None:
        # Imported lazily so importing this module never requires an API key.
        from vault_agent.config import get_settings
        from vault_agent.llm import ForcedToolCaller

        self._caller = ForcedToolCaller(model or get_settings().primary_model)

    async def extract(
        self, *, system_prompt: str, document: str
    ) -> list[dict[str, Any]]:
        payload = await self._caller.call(
            tool_name=_TOOL_NAME,
            tool_description="Emit the structured requirements extracted from the document.",
            input_schema=_tool_schema(),
            system_prompt=system_prompt,
            user_content=document,
            max_tokens=_MAX_TOKENS,
        )
        return list(payload.get("requirements", []))


class RequirementsParserAgent(BaseAgent):
    """Extracts structured requirements from the input documents."""

    prompt_path = "requirements_parser.md"

    def __init__(self, extractor: RequirementExtractor | None = None) -> None:
        self._extractor = extractor

    def _get_extractor(self) -> RequirementExtractor:
        if self._extractor is None:
            self._extractor = AnthropicRequirementExtractor()
        return self._extractor

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        logger.info("parsing %d input document(s)", len(state.input_documents))
        system_prompt = self.load_prompt()
        extractor = self._get_extractor()

        requirements: list[ParsedRequirement] = []
        for doc_path in state.input_documents:
            document = self._read_document(doc_path, state)
            if document is None:
                continue
            logger.debug("document %s: %d chars", doc_path, len(document))
            segments = await self._extract(extractor, system_prompt, document)
            raw_records, dropped = merge_records(segments)
            if len(segments) > 1:
                logger.info(
                    "document %s: extracted over %d segment(s), %d duplicate(s) dropped",
                    doc_path,
                    len(segments),
                    dropped,
                )
                state.flag(
                    "requirements_parser",
                    f"document {doc_path!r} did not fit one model response and was "
                    f"extracted over {len(segments)} segment(s) split on section "
                    f"boundaries; requirement ids are per-segment and were de-collided "
                    f"— review the extracted set for completeness",
                    kind=FlagKind.INPUT_SEGMENTED,
                    asset=doc_path,
                )
            for record in raw_records:
                try:
                    requirements.append(ParsedRequirement.model_validate(record))
                except ValidationError as exc:
                    state.flag(
                        "requirements_parser",
                        f"dropped invalid record from {doc_path!r}: "
                        f"{exc.error_count()} error(s)",
                        kind=FlagKind.DROPPED_RECORD,
                        asset=doc_path,
                    )

        logger.info("extracted %d requirement(s)", len(requirements))
        state.requirements = requirements
        state.decisions.append(
            {
                "agent": "requirements_parser",
                "documents": list(state.input_documents),
                "requirements_extracted": len(requirements),
            }
        )
        return state

    @staticmethod
    async def _extract(
        extractor: RequirementExtractor,
        system_prompt: str,
        document: str,
        depth: int = 0,
    ) -> list[list[dict[str, Any]]]:
        """Extract one document, halving it only when the model's answer did not fit.

        The whole document is tried first, so every input that already fits produces
        exactly one call with exactly today's content — the segmentation is invisible
        until it is needed. A truncated response (``LLMCallError.truncated``, i.e.
        ``stop_reason == "max_tokens"``) means the *answer* outgrew the output budget, not
        that the input was too long: a dense inventory-style document yields several
        atomic requirements per line, so output scales with content density, not with
        character count. Splitting the input is the only lever that shrinks the answer.

        Recursion is bounded by ``_MAX_SPLIT_DEPTH`` and by the text itself — an
        unsplittable segment re-raises. The truncated call that triggered a split is paid
        for; WP3 prompt caching keeps its input cost near zero, and it only happens on
        documents that would otherwise fail outright."""
        try:
            return [await extractor.extract(system_prompt=system_prompt, document=document)]
        except LLMCallError as exc:
            halves = split_document(document) if exc.truncated else None
            if halves is None or depth >= _MAX_SPLIT_DEPTH:
                raise
            logger.info(
                "response truncated; splitting document (%d chars) at depth %d",
                len(document),
                depth,
            )
            segments: list[list[dict[str, Any]]] = []
            for half in halves:
                segments.extend(
                    await RequirementsParserAgent._extract(
                        extractor, system_prompt, half, depth + 1
                    )
                )
            return segments

    @staticmethod
    def _read_document(doc_path: str, state: VaultAgentState) -> str | None:
        """Dispatch by file extension to the matching text extractor.

        Supports the charter's source formats (``.md``/``.txt`` plain text, ``.pdf`` via
        pypdf, ``.docx`` via python-docx). An unknown extension is flagged on
        ``state.flags`` and skipped — it never crashes the pipeline. Extracted text
        longer than ``MAX_DOCUMENT_CHARS`` is cut to the head and flagged
        (``FlagKind.INPUT_TRUNCATED``) — never silently truncated."""
        path = Path(doc_path)
        if not path.is_file():
            state.flag(
                "requirements_parser",
                f"input document not found: {doc_path!r}",
                severity="error",
                kind=FlagKind.MISSING_INPUT,
                asset=doc_path,
            )
            return None
        suffix = path.suffix.lower()
        if suffix in ("", ".md", ".txt"):
            text = path.read_text(encoding="utf-8")
        elif suffix == ".pdf":
            text = _extract_pdf_text(path)
        elif suffix == ".docx":
            text = _extract_docx_text(path)
        else:
            state.flag(
                "requirements_parser",
                f"unsupported document type {suffix or '(none)'!r} for {doc_path!r}; "
                f"supported: .md, .txt, .pdf, .docx — skipped",
                severity="error",
                kind=FlagKind.MISSING_INPUT,
                asset=doc_path,
            )
            return None
        # Input-size guard (WP3): an oversized document would blow the context window
        # with an opaque API error. Truncate to the head — but never silently: the flag
        # names the document and both sizes so a human can decide whether the head is
        # an acceptable basis (advisory; the pipeline continues).
        if len(text) > MAX_DOCUMENT_CHARS:
            state.flag(
                "requirements_parser",
                f"document {doc_path!r} truncated from {len(text)} to "
                f"{MAX_DOCUMENT_CHARS} characters to fit the model's context window; "
                f"requirements beyond the cut are not extracted — review",
                kind=FlagKind.INPUT_TRUNCATED,
                asset=doc_path,
            )
            text = text[:MAX_DOCUMENT_CHARS]
        return text
