// Pure derivations from the API's data — the only place the frontend "computes" anything, and
// every result is labelled as derived from the trace (WP67 §2.1). No prices here (§2.4).
import type { GraphNode, RunStatus, TraceEvent } from "./types";

export type NodeState = "pending" | "active" | "done";

export interface StripEntry {
  id: string;
  tool_name: string | null;
  state: NodeState;
  /** A deterministic node's state is inferred from its neighbours' calls. */
  inferred: boolean;
  calls: number;
  attempts: number;
  errors: number;
  backstops: number;
}

/** The status strip: `done` once a later node's call appears, `active` while its calls are the
 *  latest, `pending` otherwise. A terminal run status closes every node up to the last seen one
 *  (finished: all; paused: all before the human checkpoint). */
export function deriveStrip(nodes: GraphNode[], events: TraceEvent[], status: RunStatus): StripEntry[] {
  const byTool = new Map<string, number>();
  nodes.forEach((n, i) => { if (n.tool_name) byTool.set(n.tool_name, i); });
  const calls = nodes.map(() => 0), attempts = nodes.map(() => 0), errors = nodes.map(() => 0),
    backstops = nodes.map(() => 0);
  let latest = -1;
  for (const e of events) {
    const i = e.tool_name ? byTool.get(e.tool_name) : undefined;
    if (i === undefined) continue;
    if (e.kind === "llm_call") { calls[i] = (calls[i] ?? 0) + 1; attempts[i] = Math.max(attempts[i] ?? 0, e.attempt); }
    if (e.kind === "llm_error") errors[i] = (errors[i] ?? 0) + 1;
    if (e.kind === "backstop") backstops[i] = (backstops[i] ?? 0) + 1;
    latest = Math.max(latest, i);
  }
  const human = nodes.findIndex((n) => n.id === "human_checkpoint");
  const terminal = status === "finished" || status === "failed" || status === "crashed" || status === "discarded";
  return nodes.map((n, i) => {
    let state: NodeState = "pending";
    if (status === "finished") state = "done";
    else if (status === "paused") state = human >= 0 && i < human ? "done" : i === human ? "active" : "pending";
    else if (terminal) state = i <= latest ? "done" : "pending";
    else if (i < latest) state = "done";
    else if (i === latest) state = "active";
    else if (latest === -1 && i === 0 && events.length > 0) state = "active";
    return {
      id: n.id, tool_name: n.tool_name, state, inferred: n.tool_name === null,
      calls: calls[i] ?? 0, attempts: attempts[i] ?? 0, errors: errors[i] ?? 0, backstops: backstops[i] ?? 0,
    };
  });
}

export interface Usage {
  calls: number;
  input: number;
  output: number;
  cacheRead: number;
  cacheWrite: number;
  errors: number;
  backstops: number;
  models: string[];
}

export function deriveUsage(events: TraceEvent[]): Usage {
  const u: Usage = { calls: 0, input: 0, output: 0, cacheRead: 0, cacheWrite: 0, errors: 0, backstops: 0, models: [] };
  const models = new Set<string>();
  for (const e of events) {
    if (e.kind === "llm_call") {
      u.calls += 1; u.input += e.input_tokens; u.output += e.output_tokens;
      u.cacheRead += e.cache_read_tokens; u.cacheWrite += e.cache_write_tokens;
      if (e.model) models.add(e.model);
    } else if (e.kind === "llm_error") u.errors += 1;
    else if (e.kind === "backstop") u.backstops += 1;
  }
  u.models = [...models].sort();
  return u;
}

export interface EventFilter {
  kinds: Set<TraceEvent["kind"]>;
  tool: string | null;
  text: string;
}

export function filterEvents(events: TraceEvent[], f: EventFilter): TraceEvent[] {
  const needle = f.text.trim().toLowerCase();
  return events.filter((e) =>
    f.kinds.has(e.kind)
    && (f.tool === null || e.tool_name === f.tool)
    && (needle === "" || JSON.stringify(e).toLowerCase().includes(needle)));
}

/** One syslog-style line per event: time, severity, tool, the gist. */
export function eventLine(e: TraceEvent): { time: string; level: "info" | "warn" | "error" | "debug"; text: string } {
  const time = e.ts ? e.ts.slice(11, 19) : "--:--:--";
  switch (e.kind) {
    case "llm_route":
      return { time, level: "debug", text: `route ${summarise(e.payload)}` };
    case "llm_call":
      return {
        time, level: e.stop_reason && e.stop_reason !== "tool_use" && e.stop_reason !== "end_turn" ? "warn" : "info",
        text: `${e.tool_name} attempt ${e.attempt} ${e.model} in=${e.input_tokens} out=${e.output_tokens}`
          + (e.cache_read_tokens ? ` cached=${e.cache_read_tokens}` : "") + (e.stop_reason ? ` stop=${e.stop_reason}` : ""),
      };
    case "llm_error":
      return { time, level: "error", text: `${e.tool_name} attempt ${e.attempt}: ${e.error ?? "error"}` };
    case "backstop":
      return { time, level: "warn", text: `backstop ${summarise(e.payload)}` };
  }
}

function summarise(payload: Record<string, unknown> | null): string {
  if (!payload) return "";
  return Object.entries(payload)
    .filter(([, v]) => typeof v === "string" || typeof v === "number" || typeof v === "boolean")
    .map(([k, v]) => `${k}=${String(v)}`)
    .join(" ");
}

export function elapsedSeconds(started: string | null, finished: string | null, now: Date): number | null {
  if (!started) return null;
  const end = finished ? new Date(finished) : now;
  return Math.max(0, Math.round((end.getTime() - new Date(started).getTime()) / 1000));
}

export function formatDuration(seconds: number | null): string {
  if (seconds === null) return "–";
  const m = Math.floor(seconds / 60), s = seconds % 60;
  return m ? `${m} min ${s} s` : `${s} s`;
}

export function formatTokens(n: number): string {
  return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(2)} M` : n >= 1000 ? `${(n / 1000).toFixed(1)} k` : String(n);
}

export function formatBytes(n: number): string {
  return n >= 1_048_576 ? `${(n / 1_048_576).toFixed(1)} MB` : n >= 1024 ? `${(n / 1024).toFixed(1)} kB` : `${n} B`;
}
