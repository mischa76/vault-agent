"""JSONL trace writer for LLM transcripts (WP15 §2.2).

One JSON object per :class:`~vault_agent.llm.TraceEvent`, newline-delimited, appended to a
file the *caller* chooses — library code never decides where traces go (WP5 §5.4): the CLI
puts them under ``<out>/.vault-agent/traces/``, the eval harness next to its result JSONs.

The point is grep/jq-ability: ``grep emit_dv_model run.jsonl | jq .payload`` shows exactly
what the modeler returned, so a mis-modelled run is diagnosed by *reading the trace* instead
of re-running the pipeline with ad-hoc prints (Karpathy, LOOPS.md rule VII).

Traces are debug artifacts, not deliverables: they carry timestamps (so they are exempt from
the byte-identity determinism rules the generated artifacts follow) and they carry raw
document/source text — never publish them.
"""
import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from vault_agent.llm import TraceEvent

logger = logging.getLogger(__name__)


class JsonlTraceWriter:
    """Appends trace events to ``path`` as newline-delimited JSON.

    Opens the file per event (append mode), so a resumed run — a second writer session on the
    same thread's file — continues one transcript, and a crashed run keeps everything written
    so far. The system prompt is written in full on the *first* event carrying a given sha and
    referenced by sha afterwards: the modeler's prompt is byte-identical across
    MAX_MODELING_ATTEMPTS retries (WP3), so deduping keeps the file readable and small."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._seen_prompts: set[str] = set()

    @property
    def path(self) -> Path:
        return self._path

    def __call__(self, event: TraceEvent) -> None:
        """Record one event (the :data:`~vault_agent.llm.TraceRecorder` interface)."""
        record = asdict(event)
        sha = record.get("system_prompt_sha") or ""
        if sha and sha in self._seen_prompts:
            record.pop("system_prompt", None)
        elif sha:
            self._seen_prompts.add(sha)
        record = {"ts": datetime.now(UTC).isoformat(), **record}
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")
