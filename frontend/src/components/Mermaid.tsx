import { useCallback, useEffect, useId, useRef, useState } from "react";

// WP88: the zoom per tile, remembered by title while the page is open (null = fit the tile's width).
const rememberedZoom = new Map<string, number | null>();
const STEP = 1.25;

// Mermaid renders the source the API escaped (the report's rule) under securityLevel strict, as
// the report does; the SVG is Mermaid's own output. Loaded on demand — it is the bundle's heaviest part.
const MERMAID = { startOnLoad: false, securityLevel: "strict", fontFamily: "inherit", layout: "dagre" } as const;

// WP143 (C49): the file name a saved picture gets — the tile's title, in the characters every
// file system takes.
export const fileStem = (title: string): string =>
  title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "diagram";

// `sheet` is the line under a printed picture — the run it shows (WP143).
export function Mermaid({ source, title, sheet }: { source: string; title: string; sheet?: string }) {
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
        // Mermaid 12 lays out with ELK by default (a 456 kB gzip chunk, fetched on first render); dagre is what
        // Mermaid 11 drew these diagrams with — pinned so the upgrade of 2026-10-24 changes no picture.
        mermaid.initialize({ ...MERMAID, theme: "dark" });
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

  // WP143 (C49): the tile's own source drawn again in Mermaid's light theme — for paper and for a
  // file. The picture on the screen stays the dark one; the next screen render sets its theme itself.
  const lightSvg = useCallback(async (): Promise<string> => {
    const mermaid = (await import("mermaid")).default;
    // Labels as SVG text (mermaid 12.2.0, config.type.d.ts: root-level `htmlLabels`): an HTML label
    // sits in a <foreignObject>, which a browser draws and most other SVG viewers do not.
    // SVG text is wrapped at `flowchart.wrappingWidth` (200 by default), which breaks a construct's
    // name in the middle (seen on paper: link_account_cus / tomer); wide enough, a name stays whole.
    mermaid.initialize({ ...MERMAID, theme: "default", htmlLabels: false, flowchart: { wrappingWidth: 1200 } });
    try {
      const { svg } = await mermaid.render(`p${id}${Date.now()}`, source);
      // Mermaid hands back HTML-serialised markup (an unclosed <br>); through the DOM and the XML
      // serialiser it becomes a document any XML reader takes, with its namespaces.
      const holder = document.createElement("div");
      holder.innerHTML = svg;
      const picture = holder.querySelector("svg");
      return picture ? new XMLSerializer().serializeToString(picture) : svg;
    } finally {
      mermaid.initialize({ ...MERMAID, theme: "dark" });
    }
  }, [id, source]);

  const print = useCallback(async () => {
    setError(null);
    try {
      const svg = await lightSvg();
      const page = document.createElement("div");
      page.className = "print-sheet";
      const heading = document.createElement("h1");
      heading.textContent = title;
      const picture = document.createElement("div");
      picture.innerHTML = svg; // Mermaid's own output under securityLevel strict, as on the screen
      page.append(heading, picture);
      if (sheet) {
        const line = document.createElement("p");
        line.textContent = sheet;
        page.append(line);
      }
      const done = () => {
        page.remove();
        document.documentElement.classList.remove("printing");
        window.removeEventListener("afterprint", done);
      };
      window.addEventListener("afterprint", done);
      document.body.append(page);
      document.documentElement.classList.add("printing");
      window.print();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [lightSvg, sheet, title]);

  const save = useCallback(async () => {
    setError(null);
    try {
      const svg = await lightSvg();
      const url = URL.createObjectURL(new Blob([`<?xml version="1.0" encoding="UTF-8"?>\n${svg}`], { type: "image/svg+xml" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `${fileStem(title)}.svg`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [lightSvg, title]);

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
              <button type="button" className={tool} aria-label="print" title="print this diagram — light, on a sheet of its own" onClick={() => void print()}>print</button>
              <button type="button" className={tool} aria-label="save SVG" title="save this diagram as an SVG file — light, scales without loss" onClick={() => void save()}>svg</button>
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
