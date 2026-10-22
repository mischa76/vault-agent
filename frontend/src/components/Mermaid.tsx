import { useCallback, useEffect, useId, useRef, useState } from "react";

// WP88: the zoom per tile, remembered by title while the page is open (null = fit the tile's width).
const rememberedZoom = new Map<string, number | null>();
const STEP = 1.25;

// Mermaid renders the source the API escaped (the report's rule) under securityLevel strict, as
// the report does; the SVG is Mermaid's own output. Loaded on demand — it is the bundle's heaviest part.
export function Mermaid({ source, title }: { source: string; title: string }) {
  const host = useRef<HTMLDivElement>(null);
  const natural = useRef<number | null>(null);
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(true);
  const [rendered, setRendered] = useState(0);
  const [zoom, setZoomState] = useState<number | null>(() => rememberedZoom.get(title) ?? null);
  const [full, setFull] = useState(false);

  const setZoom = useCallback((next: number | null) => {
    rememberedZoom.set(title, next);
    setZoomState(next);
  }, [title]);

  useEffect(() => {
    let cancelled = false;
    setPending(true); setError(null);
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "dark", fontFamily: "inherit" });
        const { svg } = await mermaid.render(`m${id}`, source);
        if (!cancelled && host.current) {
          host.current.innerHTML = svg;
          const el = host.current.querySelector("svg");
          const box = el?.getAttribute("viewBox")?.split(/[\s,]+/).map(Number);
          natural.current = box && box.length === 4 && box[2]! > 0 ? box[2]! : null;
          setRendered((n) => n + 1);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setPending(false);
      }
    })();
    return () => { cancelled = true; };
  }, [source, id]);

  // Apply the zoom to the SVG Mermaid produced: fit = the tile's width; else pixels, and the tile scrolls.
  useEffect(() => {
    const el = host.current?.querySelector("svg");
    if (!el) return;
    if (zoom === null || natural.current === null) {
      el.style.width = "100%";
      el.style.maxWidth = "100%";
    } else {
      el.style.width = `${Math.round(natural.current * zoom)}px`;
      el.style.maxWidth = "none";
    }
    el.style.height = "auto";
  }, [zoom, rendered]);

  // From fit, zooming starts at the scale the tile currently shows (1:1 when that is unknown).
  const current = useCallback((): number => {
    if (zoom !== null) return zoom;
    const width = host.current?.clientWidth ?? 0;
    return natural.current && width > 0 ? width / natural.current : 1;
  }, [zoom]);
  const zoomIn = useCallback(() => setZoom(current() * STEP), [current, setZoom]);
  const zoomOut = useCallback(() => setZoom(current() / STEP), [current, setZoom]);

  useEffect(() => {
    if (!full) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setFull(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [full]);

  const onWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    if (!(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    if (e.deltaY < 0) zoomIn(); else zoomOut();
  };

  const empty = source.trim().split("\n").length <= 1;
  const tool = "rounded border border-line px-1.5 py-0.5 text-ink-dim hover:text-ink disabled:opacity-40";
  return (
    <figure
      className={full ? "fixed inset-4 z-50 flex flex-col rounded-lg border border-line bg-pane-2 p-3 shadow-2xl" : "rounded-lg border border-line bg-pane-2 p-3"}
      role={full ? "dialog" : undefined} aria-modal={full ? true : undefined} aria-label={full ? title : undefined}
    >
      <figcaption className="mb-2 flex items-center justify-between gap-2 text-xs text-ink-dim">
        <span>{title}</span>
        <span className="flex items-center gap-1">
          {pending && !empty && <span className="mr-2">rendering…</span>}
          {!empty ? (
            <>
              <button type="button" className={tool} aria-label="zoom out" title="zoom out (Ctrl + wheel)" onClick={zoomOut}>−</button>
              <button type="button" className={tool} aria-label="zoom in" title="zoom in (Ctrl + wheel)" onClick={zoomIn}>+</button>
              <button type="button" className={tool} aria-label="fit" title="fit the tile's width" onClick={() => setZoom(null)}>fit</button>
              <button type="button" className={tool} aria-label="actual size" title="1:1" onClick={() => setZoom(1)}>1:1</button>
              <button type="button" className={tool} aria-label="full screen" title={full ? "close (Esc)" : "full screen"} onClick={() => setFull(!full)}>{full ? "×" : "⛶"}</button>
              <span className="ml-1 w-10 text-right tabular-nums">{zoom === null ? "fit" : `${Math.round(zoom * 100)}%`}</span>
            </>
          ) : null}
        </span>
      </figcaption>
      {empty ? <p className="text-sm text-ink-faint">nothing declared — the diagram is empty</p> : null}
      {error ? <pre className="text-xs text-bad whitespace-pre-wrap">{error}</pre> : null}
      <div ref={host} onWheel={onWheel} className={full ? "mermaid-host min-h-0 flex-1 overflow-auto" : "mermaid-host max-h-[70vh] overflow-auto"} />
      {!full ? (
        <details className="mt-2 text-xs text-ink-faint">
          <summary>Mermaid source</summary>
          <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap font-mono">{source}</pre>
        </details>
      ) : null}
    </figure>
  );
}
