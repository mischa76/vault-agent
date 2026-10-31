import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import { formatBytes } from "../derive";
import { PLATFORMS, type Platform, type Project, type ProjectFile, type ProjectSettingsView, type RunSummary } from "../types";
import { Button, Dot, Empty, ErrorNote, KV, Pill, Section } from "../components/ui";

// A browser upload is text: .md/.txt requirements and .yml/.yaml/.json schemas. A PDF
// requirements document goes through the CLI (`vault-agent run file.pdf`), as the hint says.
const ACCEPT: Record<ProjectFile["kind"], string> = {
  requirements: ".md,.txt", schema: ".yml,.yaml,.json", profiling: ".yml,.yaml,.json",
};

export function ProjectPerspective({ project, onChanged, onOpenRun, onDeleted, busy }: {
  project: Project; onChanged: () => void; onOpenRun: (runId: string) => void; onDeleted: () => void; busy: boolean;
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
  // WP113 (C3): the project's settings — the start form's platform follows the stored default.
  const [view, setView] = useState<ProjectSettingsView | null>(null);
  const [draft, setDraft] = useState({ target_platform: "", primary_model: "", heavy_model: "", anthropic_base_url: "" });
  const [savedNote, setSavedNote] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    api.settings(project.id).then((v) => {
      if (!live) return;
      setView(v);
      setDraft({
        target_platform: v.settings.target_platform ?? "", primary_model: v.settings.primary_model ?? "",
        heavy_model: v.settings.heavy_model ?? "", anthropic_base_url: v.settings.anthropic_base_url ?? "",
      });
      setPlatform(v.effective.target_platform);
    }).catch((e) => { if (live) setError(e instanceof ApiError ? e.detail : String(e)); });
    return () => { live = false; };
  }, [project.id]);

  async function saveSettings() {
    setError(null); setSavedNote(null);
    try {
      const v = await api.saveSettings(project.id, {
        target_platform: (draft.target_platform || null) as Platform | null,
        primary_model: draft.primary_model || null, heavy_model: draft.heavy_model || null,
        anthropic_base_url: draft.anthropic_base_url || null,
      });
      setView(v); setPlatform(v.effective.target_platform); setSavedNote("saved — the next run takes these");
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : String(e));
    }
  }

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

  // WP112 (C2): deleting asks first; the API keeps what another run depends on and the 409 says why.
  async function remove(what: string, action: () => Promise<unknown>, after: () => void) {
    if (!window.confirm(`Delete ${what}? This cannot be undone.`)) return;
    setError(null);
    try {
      await action();
      after();
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
        <div className="mt-3">
          <Button kind="danger" disabled={busy}
            onClick={() => void remove(`project ${project.name} with its inputs and runs`, () => api.deleteProject(project.id), onDeleted)}
            title="Refused while a run is running or paused, or while another project's run extends one of this project's runs">
            delete project
          </Button>
        </div>
      </Section>
      <Section title="Settings" aside={view ? <Pill tone={view.environment.anthropic_api_key_set ? "ok" : "warn"}>API key: {view.environment.anthropic_api_key_set ? "set" : "not set"}</Pill> : null}>
        <div className="grid gap-3 text-sm sm:grid-cols-2">
          <label className="grid gap-1">
            <span className="text-xs text-ink-faint">default target platform</span>
            <select aria-label="default target platform" value={draft.target_platform} onChange={(e) => setDraft({ ...draft, target_platform: e.target.value })} className="rounded-md border border-line bg-pane-2 px-2 py-1.5">
              <option value="">environment ({view?.environment.llm_provider ?? "…"}: postgres)</option>
              {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
          <label className="grid gap-1">
            <span className="text-xs text-ink-faint">anthropic base URL</span>
            <input aria-label="anthropic base URL" value={draft.anthropic_base_url} placeholder={view?.environment.anthropic_base_url ?? "the SDK's default"}
              onChange={(e) => setDraft({ ...draft, anthropic_base_url: e.target.value })} className="rounded-md border border-line bg-pane-2 px-2 py-1.5 font-mono text-xs" />
          </label>
          <label className="grid gap-1">
            <span className="text-xs text-ink-faint">primary model</span>
            <input aria-label="primary model" value={draft.primary_model || view?.effective.primary_model || ""} placeholder={view?.environment.primary_model}
              onChange={(e) => setDraft({ ...draft, primary_model: e.target.value })} className="rounded-md border border-line bg-pane-2 px-2 py-1.5 font-mono text-xs" />
          </label>
          <label className="grid gap-1">
            <span className="text-xs text-ink-faint">heavy model (the modeler)</span>
            <input aria-label="heavy model" value={draft.heavy_model || view?.effective.heavy_model || ""} placeholder={view?.environment.heavy_model}
              onChange={(e) => setDraft({ ...draft, heavy_model: e.target.value })} className="rounded-md border border-line bg-pane-2 px-2 py-1.5 font-mono text-xs" />
          </label>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <Button kind="ghost" onClick={() => void saveSettings()} disabled={busy}>save settings</Button>
          <span className="text-xs text-ink-faint">{savedNote ?? `route: ${view?.environment.route ?? view?.environment.llm_provider ?? "…"} — secrets stay in .env; every run records these and its CLI equivalent carries them`}</span>
        </div>
      </Section>
      <Section title="Inputs">
        <ErrorNote error={error} />
        <ul className="mt-2 divide-y divide-line text-sm">
          {project.files.length === 0 ? <li><Empty>no inputs yet — attach a requirements document and, for grounding, the declared source schema</Empty></li> : null}
          {project.files.map((f) => (
            <li key={f.name} className="flex items-center justify-between py-1.5">
              <span className="font-mono text-xs">{f.name}</span>
              <span className="flex items-center gap-2 text-xs text-ink-faint"><Pill>{f.kind}</Pill>{formatBytes(f.bytes)}
                <button type="button" aria-label={`delete file ${f.name}`} title="Kept while a run has read it"
                  className="rounded border border-line px-1.5 py-0.5 hover:bg-pane-2"
                  onClick={() => void remove(`input ${f.name}`, () => api.deleteFile(project.id, f.name), onChanged)}>delete</button>
              </span>
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
              <li key={r.id} className="flex items-center gap-2">
                <button type="button" aria-label={`delete run ${stamp(r)}`}
                  disabled={r.status === "running" || r.status === "paused"}
                  title={r.status === "running" ? "cancel first" : r.status === "paused" ? "decide or discard first" : "Kept while another run extends it"}
                  className="rounded border border-line px-1.5 py-0.5 text-xs text-ink-faint hover:bg-pane-2 disabled:opacity-40"
                  onClick={() => void remove(`run ${stamp(r)}`, () => api.deleteRun(r.id), onChanged)}>delete</button>
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
