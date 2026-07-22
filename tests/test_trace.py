"""Keyless tests for the JSONL trace writer (WP15 §2.2).

The writer is the only place that decides *how* a trace event is persisted: one JSON object
per line, appended (so a resumed run continues one transcript), with the system prompt
written once per sha and referenced afterwards.
"""
import json
from pathlib import Path

from vault_agent.llm import TraceEvent, prompt_sha
from vault_agent.trace import JsonlTraceWriter


def _read(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _call_event(system_prompt: str = "SYSTEM", **extra: object) -> TraceEvent:
    return TraceEvent(
        kind="llm_call",
        tool_name="emit_dv_model",
        model="test-model",
        system_prompt=system_prompt,
        system_prompt_sha=prompt_sha(system_prompt),
        user_content="USER",
        max_tokens=8192,
        **extra,  # type: ignore[arg-type]
    )


def test_writes_one_json_object_per_event(tmp_path: Path) -> None:
    writer = JsonlTraceWriter(tmp_path / "traces" / "run.jsonl")
    writer(_call_event(payload={"hubs": [{"name": "hub_customer"}]}, stop_reason="tool_use"))

    records = _read(writer.path)
    assert len(records) == 1
    record = records[0]
    assert record["kind"] == "llm_call"
    assert record["tool_name"] == "emit_dv_model"
    assert record["payload"] == {"hubs": [{"name": "hub_customer"}]}
    assert record["system_prompt"] == "SYSTEM"
    assert record["ts"]  # debug artifact: timestamped, hence exempt from byte-identity rules


def test_system_prompt_is_written_once_per_sha(tmp_path: Path) -> None:
    # The modeler's system prompt is byte-identical across MAX_MODELING_ATTEMPTS retries (WP3);
    # repeating it per event would bloat the transcript for no information.
    writer = JsonlTraceWriter(tmp_path / "run.jsonl")
    writer(_call_event())
    writer(_call_event())
    writer(_call_event("A DIFFERENT SYSTEM PROMPT"))

    first, second, third = _read(writer.path)
    assert first["system_prompt"] == "SYSTEM"
    assert "system_prompt" not in second
    assert second["system_prompt_sha"] == first["system_prompt_sha"]  # still identifiable
    assert third["system_prompt"] == "A DIFFERENT SYSTEM PROMPT"


def test_appends_across_writer_sessions(tmp_path: Path) -> None:
    # The resume case: a second process/session on the same thread's file continues the
    # transcript rather than truncating it.
    path = tmp_path / "run.jsonl"
    JsonlTraceWriter(path)(_call_event())
    JsonlTraceWriter(path)(_call_event(payload={"resumed": True}))

    records = _read(path)
    assert len(records) == 2
    assert records[1]["payload"] == {"resumed": True}


def test_backstop_event_round_trips(tmp_path: Path) -> None:
    # WP16 reserves the third kind; the writer must carry it without special-casing.
    writer = JsonlTraceWriter(tmp_path / "run.jsonl")
    writer(
        TraceEvent(
            kind="backstop",
            backstop_id="attributes_without_cdk",
            detail={"satellite": "sat_x", "dropped": ["address_type"]},
        )
    )

    record = _read(writer.path)[0]
    assert record["kind"] == "backstop"
    assert record["backstop_id"] == "attributes_without_cdk"
    assert record["detail"] == {"satellite": "sat_x", "dropped": ["address_type"]}


def test_non_serialisable_payload_does_not_raise(tmp_path: Path) -> None:
    # A tool payload is whatever the model returned; the trace channel must never take a run
    # down over an exotic value (json.dumps falls back to str()).
    writer = JsonlTraceWriter(tmp_path / "run.jsonl")
    writer(_call_event(payload={"weird": {1, 2}}))

    assert "weird" in _read(writer.path)[0]["payload"]  # type: ignore[operator]
