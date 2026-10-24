import { useState } from "react";
import { api, ApiError } from "../api";
import { formatBytes } from "../derive";
import { PLATFORMS, type Platform, type Project, type ProjectFile, type RunSummary } from "../types";
import { Button, Dot, Empty, ErrorNote, KV, Pill, Section } from "../components/ui";

// A browser upload is text: .md/.txt requirements and .yml/.yaml/.json schemas. A PDF
// requirements document goes through the CLI (`vault-agent run file.pdf`), as the hint says.
const ACCEPT: Record<ProjectFile["kind"], string> = {
  requirements: ".md,.txt", schema: ".yml,.yaml,.json", profiling: ".yml,.yaml,.json",
};

export function ProjectPerspective({ project, onChanged, onOpenRun, busy }: {
  project: Project; onChanged: () => void; onOpenRun: (runId: string) => void; busy: boolean;
}) {
  const [error, setError] = useState<string | null>(null);
  const requirements = project.files.filter((f) => f.kind === "requirements");
  const schemas = project.files.filter((f) => f.kind === "schema");
  const profilings = project.files.filter((f) => f.kind === "profiling");
  const finished = project.runs.filter((r) => r.status === "finished");
  const [req, setReq] = useState(requirements[0]?.name ?? "");
  const [schema, setSchema] = useState(schemas[0]?.name ?? "");
  const [existing, setExisting] = useState("");
  // WP82: the CLI's --profiling and --target-platform, so a workbench run equals a CLI run.
  const [profiling, setProfiling] = useState("");
  const [platform, setPlatform] = useState<Platform>("postgres");
  // WP91: Business Vault — a PIT per hub with two or more descriptive satellites, over a bounded spine.
  const [pit, setPit] = useState(false);
  const [asOfStart, setAsOfStart] = useState("");
  const [asOfEnd, setAsOfEnd] = useState("");
  const [grain, setGrain] = useState<"day" | "month">("day");
  const pitIncomplete = pit && (!asOfStart || !asOfEnd || asOfStart >= asOfEnd);
  const active = project.runs.find((r) => r.status === "running");

  async function upload(kind: ProjectFile["kind"], file: File) {
    setError(null);
    try {
      await api.addFile(project.id, kind, file.name, await file.text());
      onChanged();
      if (kind === "requirements" && !req) setReq(file.name);
      if (kind === "schema" && !schema) setSchema(file.name);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : String(e));
    }
  }

  async function start() {
    setError(null);
    try {
      const run = await api.startRun(project.id, {
        requirements: req, schema: schema || null, existing_run: existing || null,
        profiling: profiling || null, target_platform: platform,
        ...(pit ? { pit: true, as_of_start: asOfStart, as_of_end: asOfEnd, as_of_grain: grain } : {}),
      });
      onChanged();
      onOpenRun(run.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : String(e));
    }
  }

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Section title="Project">
        <KV rows={[["Name", project.name], ["Id", <code key="id" className="font-mono text-xs">{project.id}</code>], ["Created", project.created], ["Runs", String(project.runs.length)]]} />
      </Section>
      <Section title="Inputs">
        <ErrorNote error={error} />
        <ul className="mt-2 divide-y divide-line text-sm">
          {project.files.length === 0 ? <li><Empty>no inputs yet — attach a requirements document and, for grounding, the declared source schema</Empty></li> : null}
          {project.files.map((f) => (
            <li key={f.name} className="flex items-center justify-between py-1.5">
              <span className="font-mono text-xs">{f.name}</span>
              <span className="flex items-center gap-2 text-xs text-ink-faint"><Pill>{f.kind}</Pill>{formatBytes(f.bytes)}</span>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-wrap gap-3">
          {(["requirements", "schema", "profiling"] as const).map((kind) => (
            <label key={kind} className="cursor-pointer rounded-md border border-line px-3 py-1.5 text-sm hover:bg-pane-2">
              attach {kind}
              <input type="file" accept={ACCEPT[kind]} className="hidden" aria-label={`attach ${kind}`}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(kind, f); e.target.value = ""; }} />
            </label>
          ))}
        </div>
        <p className="mt-2 text-xs text-ink-faint">A schema is validated by the house loader on upload and refused with its message. PDF requirements go through the CLI.</p>
      </Section>
      <Section title="Start a run" aside={active ? <Pill tone="info">a run is active</Pill> : null}>
        <div className="grid gap-3 text-sm sm:grid-cols-3">
          <label className="grid gap-1">
            <span className="text-xs text-ink-faint">requirements</span>
            <select value={req} onChange={(e) => setReq(e.target.value)} className="rounded-md border border-line bg-pane-2 px-2 py-1.5">
              <option value="">—</option>
              {requirements.map((f) => <option key={f.name} value={f.name}>{f.name}</option>)}
            </select>
          </label>
          <label className="grid gap-1">
            <span className="text-xs text-ink-faint">source schema (grounding)</span>
            <select value={schema} onChange={(e) => setSchema(e.target.value)} className="rounded-md border border-line bg-pane-2 px-2 py-1.5">
              <option value="">none</option>
              {schemas.map((f) => <option key={f.name} value={f.name}>{f.name}</option>)}
            </select>
          </label>
          <label className="grid gap-1">
            <span className="text-xs text-ink-faint">extend an earlier run (brownfield)</span>
            <select value={existing} onChange={(e) => setExisting(e.target.value)} className="rounded-md border border-line bg-pane-2 px-2 py-1.5" disabled={finished.length === 0}>
              <option value="">greenfield</option>
              {finished.map((r) => <option key={r.id} value={r.id}>{stamp(r)}</option>)}
            </select>
          </label>
          <label className="grid gap-1">
            <span className="text-xs text-ink-faint">profiling evidence (optional)</span>
            <select aria-label="profiling" value={profiling} onChange={(e) => setProfiling(e.target.value)} className="rounded-md border border-line bg-pane-2 px-2 py-1.5" disabled={profilings.length === 0}>
              <option value="">none</option>
              {profilings.map((f) => <option key={f.name} value={f.name}>{f.name}</option>)}
            </select>
          </label>
          <label className="grid gap-1">
            <span className="text-xs text-ink-faint">target platform</span>
            <select aria-label="target platform" value={platform} onChange={(e) => setPlatform(e.target.value as Platform)} className="rounded-md border border-line bg-pane-2 px-2 py-1.5">
              {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
        </div>
        <div className="mt-3 grid gap-2 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={pit} onChange={(e) => setPit(e.target.checked)} />
            <span>point-in-time tables (Business Vault) — one per hub with two or more satellites, over a bounded spine</span>
          </label>
          {pit ? (
            <div className="grid gap-3 sm:grid-cols-3">
              <label className="grid gap-1">
                <span className="text-xs text-ink-faint">as-of start (inclusive)</span>
                <input type="date" value={asOfStart} onChange={(e) => setAsOfStart(e.target.value)} className="rounded-md border border-line bg-pane-2 px-2 py-1.5" />
              </label>
              <label className="grid gap-1">
                <span className="text-xs text-ink-faint">as-of end (exclusive)</span>
                <input type="date" value={asOfEnd} onChange={(e) => setAsOfEnd(e.target.value)} className="rounded-md border border-line bg-pane-2 px-2 py-1.5" />
              </label>
              <label className="grid gap-1">
                <span className="text-xs text-ink-faint">grain</span>
                <select value={grain} onChange={(e) => setGrain(e.target.value as "day" | "month")} className="rounded-md border border-line bg-pane-2 px-2 py-1.5">
                  <option value="day">day</option>
                  <option value="month">month</option>
                </select>
              </label>
              {pitIncomplete ? <p className="text-xs text-ink-faint sm:col-span-3">A PIT needs both dates, start before end — the CLI's --as-of-start and --as-of-end.</p> : null}
            </div>
          ) : null}
        </div>
        <div className="mt-3 flex items-center gap-3">
          <Button onClick={() => void start()} disabled={!req || busy || Boolean(active) || pitIncomplete}>Run the generator</Button>
          <span className="text-xs text-ink-faint">calls the models — the run pauses at the human checkpoint</span>
        </div>
      </Section>
      <Section title="Run history">
        {project.runs.length === 0 ? <Empty>no runs yet</Empty> : (
          <ul className="divide-y divide-line text-sm">
            {project.runs.map((r) => (
              <li key={r.id}>
                <button type="button" onClick={() => onOpenRun(r.id)} className="flex w-full items-center justify-between gap-3 py-2 text-left hover:bg-pane-2">
                  <span className="flex items-center gap-2"><Dot status={r.status} /><span className="font-mono text-xs">{stamp(r)}</span></span>
                  <span className="flex items-center gap-2 text-xs text-ink-faint">
                    {r.existing_run ? <Pill tone="info">brownfield</Pill> : null}
                    {r.schema ? <Pill>grounded</Pill> : null}
                    <Pill tone={r.status === "finished" ? "ok" : r.status === "paused" ? "warn" : r.status === "running" ? "info" : r.status === "discarded" ? "line" : "bad"}>{r.status}</Pill>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}

export function stamp(r: RunSummary | { id: string }): string {
  return r.id.split(":")[1] ?? r.id;
}
