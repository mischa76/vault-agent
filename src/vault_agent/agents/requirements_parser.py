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
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from vault_agent.agents.base import BaseAgent
from vault_agent.state import FlagKind, ParsedRequirement, VaultAgentState

_TOOL_NAME = "emit_requirements"
_MAX_TOKENS = 4096


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

    prompt_path = "requirements_parser.md"  # type: ignore[assignment]

    def __init__(self, extractor: RequirementExtractor | None = None) -> None:
        self._extractor = extractor

    def _get_extractor(self) -> RequirementExtractor:
        if self._extractor is None:
            self._extractor = AnthropicRequirementExtractor()
        return self._extractor

    async def run(self, state: VaultAgentState) -> VaultAgentState:
        system_prompt = self.load_prompt()
        extractor = self._get_extractor()

        requirements: list[ParsedRequirement] = []
        for doc_path in state.input_documents:
            document = self._read_document(doc_path, state)
            if document is None:
                continue
            raw_records = await extractor.extract(
                system_prompt=system_prompt, document=document
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
    def _read_document(doc_path: str, state: VaultAgentState) -> str | None:
        """Dispatch by file extension to the matching text extractor.

        Supports the charter's source formats (``.md``/``.txt`` plain text, ``.pdf`` via
        pypdf, ``.docx`` via python-docx). An unknown extension is flagged on
        ``state.flags`` and skipped — it never crashes the pipeline."""
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
            return path.read_text(encoding="utf-8")
        if suffix == ".pdf":
            return _extract_pdf_text(path)
        if suffix == ".docx":
            return _extract_docx_text(path)
        state.flag(
            "requirements_parser",
            f"unsupported document type {suffix or '(none)'!r} for {doc_path!r}; "
            f"supported: .md, .txt, .pdf, .docx — skipped",
            severity="error",
            kind=FlagKind.MISSING_INPUT,
            asset=doc_path,
        )
        return None
