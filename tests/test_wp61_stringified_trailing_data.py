"""WP61 — a stringified payload field with trailing data is still the value (spec §3).
Committed before the change, failing."""
from __future__ import annotations

from vault_agent.llm import TraceEvent, decoded_field


def _events() -> tuple[list[TraceEvent], object]:
    events: list[TraceEvent] = []
    return events, events.append


def test_one_closing_brace_too_many_is_dropped_and_counted() -> None:
    events, rec = _events()
    out = decoded_field({"assets": '{"a": {"doc": "x"}}}'}, "assets", {}, tool_name="t",
                        recorder=rec)  # type: ignore[arg-type]
    assert out == {"a": {"doc": "x"}}
    [event] = events
    assert event.backstop_id == "stringified_payload_field"
    assert event.detail["trailing"] == "}"


def test_a_clean_stringified_value_reports_no_trailing_data() -> None:
    events, rec = _events()
    assert decoded_field({"m": '{"k": 1}'}, "m", {}, recorder=rec) == {"k": 1}  # type: ignore[arg-type]
    [event] = events
    assert "trailing" not in event.detail


def test_no_value_or_the_wrong_shape_still_yields_the_default() -> None:
    assert decoded_field({"m": "not json"}, "m", {}) == {}
    assert decoded_field({"m": "[1]"}, "m", {}) == {}
