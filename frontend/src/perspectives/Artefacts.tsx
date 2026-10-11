import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { formatBytes } from "../derive";
import type { Artefact, Run } from "../types";
import { Empty, Section } from "../components/ui";

const TEXT = [".md", ".sql", ".yml", ".yaml", ".json", ".txt", ".csv", ".py", ".toml"];

export function ArtefactsPerspective({ run, artefacts }: { run: Run; artefacts: Artefact[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setText(null); setError(null);
    if (!open || !TEXT.some((ext) => open.endsWith(ext))) return;
    let cancelled = false;
    api.artefactText(run.id, open).then((t) => { if (!cancelled) setText(t); })
      .catch((e: unknown) => { if (!cancelled) setError(e instanceof ApiError ? e.detail : String(e)); });
    return () => { cancelled = true; };
  }, [open, run.id]);

  const folders = new Map<string, Artefact[]>();
  for (const a of artefacts) {
    const dir = a.path.includes("/") ? a.path.slice(0, a.path.lastIndexOf("/")) : ".";
    folders.set(dir, [...(folders.get(dir) ?? []), a]);
  }
  const isHtml = open?.endsWith(".html");
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(16rem,1fr)_2fr]">
      <Section title="Output directory">
        {artefacts.length === 0 ? <Empty>nothing written yet</Empty> : null}
        {[...folders.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([dir, files]) => (
          <div key={dir} className="mb-3">
            <h3 className="font-mono text-xs text-ink-faint">{dir === "." ? "/" : dir + "/"}</h3>
            <ul>
              {files.map((f) => {
                const name = f.path.slice(f.path.lastIndexOf("/") + 1);
                return (
                  <li key={f.path} className="flex items-center justify-between gap-2">
                    <button type="button" onClick={() => setOpen(f.path)} className={`truncate py-0.5 text-left font-mono text-xs hover:text-accent ${open === f.path ? "text-accent" : ""}`}>{name}</button>
                    <span className="shrink-0 text-[10px] text-ink-faint">{formatBytes(f.bytes)}</span>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </Section>
      <Section title={open ?? "Viewer"} aside={open ? <a className="text-xs text-ink-dim underline" href={api.artefactUrl(run.id, open)} target="_blank" rel="noreferrer">open raw</a> : null}>
        {!open ? <Empty>select a file</Empty> : null}
        {error ? <Empty>{error}</Empty> : null}
        {isHtml ? <iframe title={open ?? ""} sandbox="" src={api.artefactUrl(run.id, open!)} className="h-[70vh] w-full rounded-md border border-line bg-white" /> : null}
        {text !== null ? <pre className="max-h-[70vh] overflow-auto rounded-md bg-pane-2 p-3 font-mono text-xs leading-5 whitespace-pre-wrap">{text}</pre> : null}
        {open && !isHtml && text === null && !error && !TEXT.some((e) => open.endsWith(e)) ? <Empty>binary or unknown type — use „open raw"</Empty> : null}
      </Section>
    </div>
  );
}
