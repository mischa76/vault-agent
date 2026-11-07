import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { ProjectFile, SourceView } from "../types";
import { Button, ErrorNote, Pill, Section } from "./ui";

// WP119 (C46): the source database — `vault-agent source-schema` and `vault-agent profile` from the
// workbench. The connection is the workbench's VAULT_AGENT_SOURCE_URL (ADR-0015: secrets stay in
// `.env`); this section never sees a password, it shows the URL as the server hides it.
const CHECKS = ["range", "lengths", "patterns", "examples"] as const;
type Check = (typeof CHECKS)[number];

// `onProduced` hands the stored input to the run form, which selects it as an upload is selected.
export function SourceSection({ projectId, onChanged, onProduced, busy }: {
  projectId: string; onChanged: () => void; onProduced?: (file: ProjectFile) => void; busy: boolean;
}) {
  const [view, setView] = useState<SourceView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [schemas, setSchemas] = useState<string[]>([]);
  const [views, setViews] = useState(false);
  const [tables, setTables] = useState<{ schema: string; table: string }[]>([]);
  const [chosenTables, setChosenTables] = useState<string[]>([]);
  const [checks, setChecks] = useState<Check[]>(["range", "lengths", "patterns"]);
  const [sample, setSample] = useState(10000);
  const [working, setWorking] = useState(false);
  const [result, setResult] = useState<{ command: string; note: string } | null>(null);

  useEffect(() => {
    let live = true;
    api.source().then((v) => { if (live) setView(v); })
      .catch((e) => { if (live) setError(e instanceof ApiError ? e.detail : String(e)); });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    let live = true;
    setChosenTables([]);
    if (schemas.length === 0) { setTables([]); return; }
    api.sourceTables(schemas).then((t) => { if (live) setTables(t); })
      .catch((e) => { if (live) setError(e instanceof ApiError ? e.detail : String(e)); });
    return () => { live = false; };
  }, [schemas]);

  const toggle = <T,>(list: T[], item: T) => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);

  async function act(action: () => Promise<{ command: string; note: string; file: ProjectFile }>) {
    setError(null); setResult(null); setWorking(true);
    try {
      const done = await action();
      setResult(done);
      onProduced?.(done.file);
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setWorking(false);
    }
  }

  function readCatalogue() {
    void act(async () => {
      const r = await api.readCatalogue(projectId, { schemas, views });
      const s = r.summary;
      return { command: r.command, file: r.file, note: `${r.file.name}: ${s.tables} tables, ${s.columns} columns, ${s.foreign_keys} foreign keys — metadata only` };
    });
  }

  function makeProfile() {
    const scope = chosenTables.length ? `${chosenTables.length} table(s)` : `every table of ${schemas.join(", ")}`;
    const values = checks.includes("examples") ? " The examples check writes column values into the file." : "";
    if (!window.confirm(`Profiling reads rows of the source database: ${scope}, counts over all rows, shapes from a sample of ${sample}.${values} Continue?`)) return;
    void act(async () => {
      const r = await api.makeProfile(projectId, {
        schemas, tables: chosenTables, checks: checks.length ? checks : ["none"], sample,
        examples: checks.includes("examples") ? 3 : 0, reads_rows: true,
      });
      const s = r.summary;
      const refused = r.refused.length ? `; refused by the database: ${r.refused.join("; ")}` : "";
      return { command: r.command, file: r.file, note: `${r.file.name}: ${s.tables} tables, ${s.columns} columns, ${s.rows} rows counted${refused}` };
    });
  }

  const tone = view?.state === "ok" ? "ok" : view?.state === "unset" ? "line" : "warn";
  return (
    <Section title="Source" aside={view ? <Pill tone={tone}>source: {view.state === "unset" ? "not set" : view.state}</Pill> : null}>
      <ErrorNote error={error} />
      {view === null ? null : view.state === "unset" ? (
        <p className="text-sm text-ink-dim">No source database: set <code className="font-mono text-xs">VAULT_AGENT_SOURCE_URL</code> in
          the workbench's <code className="font-mono text-xs">.env</code> and restart it — the password stays there, never in the browser or a project (ADR-0015).</p>
      ) : view.state !== "ok" ? (
        <p className="text-sm text-ink-dim"><code className="font-mono text-xs">{view.url ?? "VAULT_AGENT_SOURCE_URL"}</code>: {view.detail}</p>
      ) : (
        <div className="grid gap-3 text-sm">
          <p className="text-xs text-ink-faint">connection <code className="font-mono">{view.url}</code> — from the workbench's environment</p>
          <fieldset className="grid gap-1">
            <legend className="text-xs text-ink-faint">schemas</legend>
            <div className="flex flex-wrap gap-3">
              {view.schemas.map((s) => (
                <label key={s} className="flex items-center gap-1.5">
                  <input type="checkbox" aria-label={`schema ${s}`} checked={schemas.includes(s)} onChange={() => setSchemas(toggle(schemas, s))} />
                  <span className="font-mono text-xs">{s}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-1.5 text-xs text-ink-dim">
              <input type="checkbox" aria-label="views" checked={views} onChange={() => setViews(!views)} /> views as well
            </label>
            <Button kind="ghost" onClick={readCatalogue} disabled={busy || working || schemas.length === 0}>read catalogue</Button>
            <span className="text-xs text-ink-faint">metadata only — becomes a schema input</span>
          </div>
          <details>
            <summary className="cursor-pointer text-xs text-ink-faint">profile — reads rows; tables {chosenTables.length ? chosenTables.length : "all"}, checks {checks.join(", ") || "none"}</summary>
            <div className="mt-2 grid gap-3">
              {tables.length ? (
                <div className="flex max-h-40 flex-wrap gap-3 overflow-auto">
                  {tables.map(({ schema, table }) => {
                    const name = `${schema}.${table}`;
                    return (
                      <label key={name} className="flex items-center gap-1.5">
                        <input type="checkbox" aria-label={`table ${name}`} checked={chosenTables.includes(name)} onChange={() => setChosenTables(toggle(chosenTables, name))} />
                        <span className="font-mono text-xs">{name}</span>
                      </label>
                    );
                  })}
                </div>
              ) : <p className="text-xs text-ink-faint">choose a schema to list its tables; none chosen profiles every table</p>}
              <div className="flex flex-wrap items-center gap-3">
                {CHECKS.map((c) => (
                  <label key={c} className="flex items-center gap-1.5 text-xs">
                    <input type="checkbox" aria-label={`check ${c}`} checked={checks.includes(c)} onChange={() => setChecks(toggle(checks, c))} />
                    {c}{c === "examples" ? <span className="text-warn"> (writes values)</span> : null}
                  </label>
                ))}
                <label className="flex items-center gap-1.5 text-xs">
                  sample
                  <input type="number" min={1} aria-label="sample" value={sample} onChange={(e) => setSample(Math.max(1, Number(e.target.value) || 1))}
                    className="w-24 rounded-md border border-line bg-pane-2 px-2 py-1 font-mono text-xs" />
                </label>
              </div>
              <div className="flex items-center gap-3">
                <Button kind="ghost" onClick={makeProfile} disabled={busy || working || schemas.length === 0}>make profile</Button>
                <span className="text-xs text-ink-faint">counts over all rows; becomes a profiling input</span>
              </div>
            </div>
          </details>
          {working ? <p className="text-xs text-ink-faint">reading the source database…</p> : null}
          {result ? (
            <div className="text-xs">
              <p className="text-ink-dim">{result.note}</p>
              <p className="mt-1 font-mono text-ink-faint">$ {result.command}</p>
            </div>
          ) : null}
        </div>
      )}
    </Section>
  );
}
