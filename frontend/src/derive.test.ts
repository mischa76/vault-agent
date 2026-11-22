import { describe, expect, it } from "vitest";
import { deriveStrip, deriveUsage, eventLine, filterEvents } from "./derive";
import type { GraphNode, TraceEvent } from "./types";

const NODES: GraphNode[] = [
  { id: "orchestrator", tool_name: null }, { id: "requirements_parser", tool_name: "emit_requirements" },
  { id: "business_key_identifier", tool_name: "emit_business_keys" }, { id: "dv2_modeler", tool_name: "emit_dv_model" },
  { id: "validator", tool_name: null }, { id: "human_checkpoint", tool_name: null }, { id: "adr_author", tool_name: null },
];
const call = (tool: string, attempt = 1, extra: Partial<TraceEvent> = {}): TraceEvent => ({
  ts: "2026-10-11T10:00:00+00:00", kind: "llm_call", tool_name: tool, model: "claude-sonnet-5-5", client: "AsyncAnthropic",
  attempt, stop_reason: "tool_use", input_tokens: 100, output_tokens: 10, cache_read_tokens: 40, cache_write_tokens: 0,
  error: null, payload: null, ...extra,
});
const route: TraceEvent = { ...call(""), kind: "llm_route", payload: { provider: "anthropic" } };

describe("deriveStrip", () => {
  it("marks earlier nodes done, the latest active and the rest pending while running", () => {
    const strip = deriveStrip(NODES, [route, call("emit_requirements"), call("emit_business_keys")], "running");
    expect(strip.map((s) => s.state)).toEqual(["done", "done", "active", "pending", "pending", "pending", "pending"]);
    expect(strip[0]!.inferred).toBe(true);
    expect(strip[1]!.inferred).toBe(false);
  });
  it("counts attempts from the modeler's retries", () => {
    const strip = deriveStrip(NODES, [call("emit_dv_model", 1), call("emit_dv_model", 2), call("emit_dv_model", 3)], "running");
    expect(strip[3]).toMatchObject({ state: "active", calls: 3, attempts: 3 });
  });
  it("closes everything before the human checkpoint when paused, and everything when finished", () => {
    const paused = deriveStrip(NODES, [call("emit_dv_model")], "paused");
    expect(paused.map((s) => s.state)).toEqual(["done", "done", "done", "done", "done", "active", "pending"]);
    expect(deriveStrip(NODES, [], "finished").every((s) => s.state === "done")).toBe(true);
  });
  it("closes an interrupted run up to its latest node and leaves the rest pending", () => {
    const strip = deriveStrip(NODES, [route, call("emit_requirements")], "interrupted");
    expect(strip.map((s) => s.state)).toEqual(["done", "done", "pending", "pending", "pending", "pending", "pending"]);
  });
  it("shows the orchestrator active on the route event alone", () => {
    expect(deriveStrip(NODES, [route], "running")[0]!.state).toBe("active");
  });
});

describe("deriveUsage", () => {
  it("sums tokens over calls only and lists the models", () => {
    const u = deriveUsage([route, call("emit_requirements"), call("emit_dv_model", 1, { model: "claude-opus-5-5" }),
      { ...call("emit_dv_model"), kind: "llm_error", error: "truncated" }, { ...call("emit_dv_model"), kind: "backstop" }]);
    expect(u).toMatchObject({ calls: 2, input: 200, output: 20, cacheRead: 80, errors: 1, backstops: 1 });
    expect(u.models).toEqual(["claude-opus-5-5", "claude-sonnet-5-5"]);
  });
});

describe("eventLine and filterEvents", () => {
  it("renders a syslog-style line per kind", () => {
    expect(eventLine(call("emit_requirements")).text).toContain("emit_requirements attempt 1 claude-sonnet-5-5 in=100 out=10 cached=40");
    expect(eventLine({ ...call("x"), kind: "llm_error", error: "boom" })).toMatchObject({ level: "error", text: "x attempt 1: boom" });
    expect(eventLine(route).text).toBe("route provider=anthropic");
  });
  it("filters by kind, tool and text", () => {
    const events = [route, call("emit_requirements"), call("emit_dv_model")];
    expect(filterEvents(events, { kinds: new Set(["llm_call"]), tool: null, text: "" })).toHaveLength(2);
    expect(filterEvents(events, { kinds: new Set(["llm_call"]), tool: "emit_dv_model", text: "" })).toHaveLength(1);
    expect(filterEvents(events, { kinds: new Set(["llm_call", "llm_route"]), tool: null, text: "llm_route" })).toHaveLength(1);
  });
});
