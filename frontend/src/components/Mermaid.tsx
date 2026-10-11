import { useEffect, useId, useRef, useState } from "react";

// Mermaid renders the source the API escaped (the report's rule) under securityLevel strict, as
// the report does; the SVG is Mermaid's own output. Loaded on demand — it is the bundle's heaviest part.
export function Mermaid({ source, title }: { source: string; title: string }) {
  const host = useRef<HTMLDivElement>(null);
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setPending(true); setError(null);
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "dark", fontFamily: "inherit" });
        const { svg } = await mermaid.render(`m${id}`, source);
        if (!cancelled && host.current) host.current.innerHTML = svg;
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setPending(false);
      }
    })();
    return () => { cancelled = true; };
  }, [source, id]);

  const empty = source.trim().split("\n").length <= 1;
  return (
    <figure className="rounded-lg border border-line bg-pane-2 p-3">
      <figcaption className="mb-2 flex items-center justify-between text-xs text-ink-dim">
        <span>{title}</span>
        {pending && !empty && <span>rendering…</span>}
      </figcaption>
      {empty ? <p className="text-sm text-ink-faint">nothing declared — the diagram is empty</p> : null}
      {error ? <pre className="text-xs text-bad whitespace-pre-wrap">{error}</pre> : null}
      <div ref={host} className="mermaid-host overflow-auto" />
      <details className="mt-2 text-xs text-ink-faint">
        <summary>Mermaid source</summary>
        <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap font-mono">{source}</pre>
      </details>
    </figure>
  );
}
