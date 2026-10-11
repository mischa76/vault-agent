import { useEffect, useRef, useState, type FormEvent } from "react";
import type { ConsoleEntry } from "../types";
import type { Perspective } from "../router";

// WP68: the state-driven console. Every answer comes from the run's state through the API;
// nothing here runs or decides — a "what if" shows the CLI command it would be.
const TONE = { answer: "text-ink", help: "text-ink-dim", unknown: "text-warn", unavailable: "text-ink-faint" };

export function Console({ entries, onAsk, onNavigate, busy, enabled }: {
  entries: ConsoleEntry[]; onAsk: (text: string) => void; onNavigate: (p: Perspective) => void;
  busy: boolean; enabled: boolean;
}) {
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [entries.length]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const t = text.trim();
    if (!t || busy || !enabled) return;
    onAsk(t);
    setText("");
  }

  return (
    <section className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)_auto]" aria-label="console">
      <header className="flex items-center justify-between border-t border-b border-line px-3 py-2 text-xs uppercase tracking-wide text-ink-dim">
        <span>console</span><span className="normal-case text-ink-faint">from the state — type help</span>
      </header>
      <ol className="min-h-0 overflow-auto px-3 py-2 text-xs" aria-label="console transcript">
        {entries.length === 0 ? (
          <li className="text-ink-faint">Ask about this run: <code>items</code>, <code>explain 1</code>, <code>why hub_x</code>, <code>gate E_DUP_HUB</code>, <code>what if accept</code>.</li>
        ) : null}
        {entries.map((e, i) => (
          <li key={i} className="mb-3">
            <div className="font-mono text-accent">› {e.question}</div>
            <pre className={`mt-1 whitespace-pre-wrap font-mono leading-5 ${TONE[e.answer.kind]}`}>{e.answer.text}</pre>
            {e.answer.refs.length > 0 ? (
              <div className="mt-1 flex flex-wrap gap-1">
                {e.answer.refs.map((r) => (
                  <button key={r.perspective + r.label} type="button" onClick={() => onNavigate(r.perspective as Perspective)}
                    className="rounded-full border border-line px-2 py-0.5 text-[11px] text-ink-dim hover:border-accent hover:text-accent">
                    {r.label}
                  </button>
                ))}
              </div>
            ) : null}
          </li>
        ))}
        <div ref={end} />
      </ol>
      <form onSubmit={submit} className="border-t border-line p-3">
        <input value={text} onChange={(e) => setText(e.target.value)} disabled={!enabled || busy}
          placeholder={enabled ? "help, status, items, explain <n>, why <construct>, what if accept" : "select a run first"}
          aria-label="console input"
          className="w-full rounded-md border border-line bg-pane-2 px-2 py-1.5 font-mono text-xs text-ink placeholder:text-ink-faint disabled:opacity-60" />
      </form>
    </section>
  );
}
