import { useEffect, useRef } from "react";
import { eventLine } from "../derive";
import type { TraceEvent } from "../types";

const LEVEL = { info: "text-ink", warn: "text-warn", error: "text-bad", debug: "text-ink-faint" };

export function EventStream({ events, follow = true, dense = false }: { events: TraceEvent[]; follow?: boolean; dense?: boolean }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { if (follow) end.current?.scrollIntoView?.({ block: "end" }); }, [events.length, follow]);
  if (events.length === 0) return <p className="p-3 text-xs text-ink-faint">no events yet</p>;
  return (
    <ol className={`font-mono ${dense ? "text-[11px] leading-4" : "text-xs leading-5"}`} aria-label="event stream">
      {events.map((e, i) => {
        const line = eventLine(e);
        return (
          <li key={i} className={`flex gap-2 px-3 hover:bg-pane-2 ${LEVEL[line.level]}`}>
            <span className="shrink-0 text-ink-faint">{line.time}</span>
            <span className="shrink-0 w-10 uppercase text-[10px] pt-0.5 text-ink-faint">{line.level}</span>
            <span className="min-w-0 break-words">{line.text}</span>
          </li>
        );
      })}
      <div ref={end} />
    </ol>
  );
}
