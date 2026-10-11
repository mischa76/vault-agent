import { useMemo, useState } from "react";
import { filterEvents, type EventFilter } from "../derive";
import type { TraceEvent } from "../types";
import { EventStream } from "../components/EventStream";
import { Pill, Section } from "../components/ui";

const KINDS: TraceEvent["kind"][] = ["llm_route", "llm_call", "llm_error", "backstop"];

export function LogPerspective({ events }: { events: TraceEvent[] }) {
  const [filter, setFilter] = useState<EventFilter>({ kinds: new Set(KINDS), tool: null, text: "" });
  const tools = useMemo(() => [...new Set(events.map((e) => e.tool_name).filter(Boolean))].sort(), [events]);
  const shown = useMemo(() => filterEvents(events, filter), [events, filter]);
  const toggle = (k: TraceEvent["kind"]) => {
    const kinds = new Set(filter.kinds);
    if (kinds.has(k)) kinds.delete(k); else kinds.add(k);
    setFilter({ ...filter, kinds });
  };
  return (
    <Section title="Event log" aside={<Pill>{shown.length} / {events.length}</Pill>}>
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        {KINDS.map((k) => (
          <button key={k} type="button" onClick={() => toggle(k)} aria-pressed={filter.kinds.has(k)}
            className={`rounded-full border px-2 py-0.5 ${filter.kinds.has(k) ? "border-accent text-accent" : "border-line text-ink-faint"}`}>{k}</button>
        ))}
        <select value={filter.tool ?? ""} onChange={(e) => setFilter({ ...filter, tool: e.target.value || null })} className="rounded-md border border-line bg-pane-2 px-2 py-0.5" aria-label="tool filter">
          <option value="">every tool</option>
          {tools.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <input value={filter.text} onChange={(e) => setFilter({ ...filter, text: e.target.value })} placeholder="search" className="w-48 rounded-md border border-line bg-pane-2 px-2 py-0.5 font-mono" aria-label="search events" />
      </div>
      <div className="max-h-[70vh] overflow-auto rounded-md border border-line bg-pane-2 py-1">
        <EventStream events={shown} follow={false} />
      </div>
    </Section>
  );
}
