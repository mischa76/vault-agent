import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { deriveUsage, elapsedSeconds, formatDuration, formatTokens } from "./derive";
import { PERSPECTIVES, useRoute, type Perspective } from "./router";
import type { Artefact, Checkpoint, ConsoleEntry, Decision, GraphNode, ModelView, Project, ProjectSummary, Run, TraceEvent } from "./types";
import { Console } from "./components/Console";
import { EventStream } from "./components/EventStream";
import { Button, Dot, Empty, ErrorNote } from "./components/ui";
import { ArtefactsPerspective } from "./perspectives/Artefacts";
import { LogPerspective } from "./perspectives/Log";
import { ModelPerspective } from "./perspectives/Model";
import { ProjectPerspective, stamp } from "./perspectives/Project";
import { ReviewPerspective } from "./perspectives/Review";
import { RunPerspective } from "./perspectives/Run";

const POLL_MS = 2000;
const LABEL: Record<Perspective, string> = { project: "Project", run: "Run", review: "Review", model: "Model", artefacts: "Artefacts", log: "Log" };

function detail(e: unknown): string { return e instanceof ApiError ? e.detail : e instanceof Error ? e.message : String(e); }

export function App() {
  const [route, navigate] = useRoute();
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const next = useRef(0);
  const [checkpoint, setCheckpoint] = useState<Checkpoint | null>(null);
  const [model, setModel] = useState<ModelView | null>(null);
  const [modelError, setModelError] = useState<string | null>(null);
  const [artefacts, setArtefacts] = useState<Artefact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [newName, setNewName] = useState("");
  const [now, setNow] = useState(() => new Date());
  const [transcripts, setTranscripts] = useState<Record<string, ConsoleEntry[]>>({});
  const [asking, setAsking] = useState(false);

  const refreshProjects = useCallback(async () => {
    try { setProjects(await api.projects()); } catch (e) { setError(detail(e)); }
  }, []);
  const refreshProject = useCallback(async (id: string) => {
    try { setProject(await api.project(id)); } catch (e) { setError(detail(e)); setProject(null); }
  }, []);

  useEffect(() => { api.graph().then((g) => setNodes(g.nodes)).catch((e: unknown) => setError(detail(e))); void refreshProjects(); }, [refreshProjects]);
  useEffect(() => { if (route.project) void refreshProject(route.project); else setProject(null); }, [route.project, refreshProject]);

  // The selected run: reset, then poll run.json and the trace while it runs.
  useEffect(() => {
    setRun(null); setEvents([]); next.current = 0; setCheckpoint(null); setModel(null); setModelError(null); setArtefacts([]);
    if (!route.run) return;
    const id = route.run;
    let cancelled = false, timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      try {
        const [r, ev] = await Promise.all([api.run(id), api.events(id, next.current)]);
        if (cancelled) return;
        setRun(r);
        if (ev.events.length) { setEvents((old) => [...old, ...ev.events]); next.current = ev.next; }
        setNow(new Date());
        if (r.status === "running") timer = setTimeout(tick, POLL_MS);
      } catch (e) { if (!cancelled) setError(detail(e)); }
    };
    void tick();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [route.run]);

  // Perspective data: the checkpoint while paused, the model and the artefacts once the run is not running.
  const status = run?.status;
  useEffect(() => {
    if (!run || status === "running") return;
    const id = run.id;
    let cancelled = false;
    if (status === "paused") api.checkpoint(id).then((c) => { if (!cancelled) setCheckpoint(c); }).catch((e: unknown) => { if (!cancelled) setError(detail(e)); });
    api.artefacts(id).then((a) => { if (!cancelled) setArtefacts(a); }).catch(() => undefined);
    api.model(id).then((m) => { if (!cancelled) { setModel(m); setModelError(null); } }).catch((e: unknown) => { if (!cancelled) setModelError(detail(e)); });
    if (route.project) void refreshProject(route.project);
    return () => { cancelled = true; };
  }, [run?.id, status, route.project, refreshProject]); // eslint-disable-line react-hooks/exhaustive-deps

  async function createProject() {
    if (!newName.trim()) return;
    setBusy(true); setError(null);
    try { const p = await api.createProject(newName.trim()); setNewName(""); await refreshProjects(); navigate({ project: p.id, run: null, perspective: "project" }); }
    catch (e) { setError(detail(e)); } finally { setBusy(false); }
  }

  async function decide(d: Decision) {
    if (!run) return;
    setBusy(true); setError(null);
    try {
      const r = await api.decide(run.id, d);
      setRun(r); setCheckpoint(null);
      navigate({ perspective: "run" });
      // the resume is a background task: poll again
      if (r.status === "running") {
        const id = r.id;
        const poll = async () => {
          const [rr, ev] = await Promise.all([api.run(id), api.events(id, next.current)]);
          setRun(rr); if (ev.events.length) { setEvents((old) => [...old, ...ev.events]); next.current = ev.next; }
          setNow(new Date());
          if (rr.status === "running") setTimeout(() => void poll(), POLL_MS);
        };
        setTimeout(() => void poll(), POLL_MS);
      }
    } catch (e) { setError(detail(e)); } finally { setBusy(false); }
  }

  async function act(action: "cancel" | "continue" | "discard") {
    if (!run) return;
    setBusy(true); setError(null);
    try {
      const r = action === "cancel" ? await api.cancel(run.id)
        : action === "continue" ? await api.continueRun(run.id)
        : await api.decide(run.id, { discard: true });
      setRun(r);
      if (route.project) void refreshProject(route.project);
      if (r.status === "running") {
        const id = r.id;
        const poll = async () => {
          const [rr, ev] = await Promise.all([api.run(id), api.events(id, next.current)]);
          setRun(rr); if (ev.events.length) { setEvents((old) => [...old, ...ev.events]); next.current = ev.next; }
          setNow(new Date());
          if (rr.status === "running") setTimeout(() => void poll(), POLL_MS);
        };
        setTimeout(() => void poll(), POLL_MS);
      }
    } catch (e) { setError(detail(e)); } finally { setBusy(false); }
  }

  async function ask(text: string) {
    if (!run) return;
    const id = run.id;
    setAsking(true);
    try {
      const a = await api.console(id, text);
      setTranscripts((t) => ({ ...t, [id]: [...(t[id] ?? []), { question: text, answer: a }] }));
    } catch (e) {
      const a = { text: detail(e), kind: "unavailable" as const, refs: [], command: null };
      setTranscripts((t) => ({ ...t, [id]: [...(t[id] ?? []), { question: text, answer: a }] }));
    } finally { setAsking(false); }
  }

  const usage = deriveUsage(events);
  const elapsed = run ? elapsedSeconds(run.started, run.finished, now) : null;
  const perspectives = route.run ? PERSPECTIVES : (["project"] as Perspective[]);

  return (
    <div className="grid h-full grid-rows-[auto_1fr_auto] bg-bg text-ink">
      <header className="flex items-center gap-4 border-b border-line bg-pane px-4 py-2">
        <span className="font-semibold tracking-tight"><span className="text-accent">vault</span>-agent workbench</span>
        <nav className="flex items-center gap-1 text-sm text-ink-dim" aria-label="breadcrumb">
          <button type="button" className="hover:text-ink" onClick={() => navigate({ project: null, run: null, perspective: "project" })}>projects</button>
          {project ? <><span>/</span><button type="button" className="hover:text-ink" onClick={() => navigate({ project: project.id, run: null, perspective: "project" })}>{project.name}</button></> : null}
          {run ? <><span>/</span><span className="font-mono text-xs">{stamp(run)}</span></> : null}
        </nav>
        <span className="ml-auto text-xs text-ink-faint">local · 127.0.0.1 · ADR-0014</span>
      </header>

      <div className="grid min-h-0 grid-cols-[16rem_minmax(0,1fr)_24rem]">
        <aside className="flex min-h-0 flex-col border-r border-line bg-pane">
          <div className="border-b border-line p-3">
            <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void createProject(); }}>
              <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="new project" aria-label="new project name"
                className="min-w-0 flex-1 rounded-md border border-line bg-pane-2 px-2 py-1 text-sm" />
              <Button type="submit" disabled={busy || !newName.trim()}>+</Button>
            </form>
          </div>
          <nav className="min-h-0 flex-1 overflow-auto p-2" aria-label="projects">
            {projects.length === 0 ? <Empty>no projects — create one above</Empty> : null}
            <ul className="grid gap-0.5">
              {projects.map((p) => (
                <li key={p.id}>
                  <button type="button" onClick={() => navigate({ project: p.id, run: null, perspective: "project" })}
                    className={`w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-pane-2 ${route.project === p.id ? "bg-pane-2 text-accent" : ""}`}>
                    {p.name}
                  </button>
                  {route.project === p.id && project ? (
                    <ul className="ml-3 border-l border-line pl-2">
                      {project.runs.map((r) => (
                        <li key={r.id}>
                          <button type="button" onClick={() => navigate({ project: p.id, run: r.id, perspective: "run" })}
                            className={`flex w-full items-center gap-2 rounded-md px-2 py-1 text-left font-mono text-xs hover:bg-pane-2 ${route.run === r.id ? "text-accent" : "text-ink-dim"}`}>
                            <Dot status={r.status} /> {stamp(r)}
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>
          </nav>
        </aside>

        <main className="flex min-h-0 flex-col">
          <div className="flex items-center gap-1 border-b border-line bg-pane px-3" role="tablist">
            {perspectives.map((p) => (
              <button key={p} type="button" role="tab" aria-selected={route.perspective === p} onClick={() => navigate({ perspective: p })}
                className={`border-b-2 px-3 py-2 text-sm ${route.perspective === p ? "border-accent text-ink" : "border-transparent text-ink-dim hover:text-ink"}`}>
                {LABEL[p]}{p === "review" && run?.status === "paused" ? <span className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-warn align-middle" /> : null}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-4">
            <div className="mb-3"><ErrorNote error={error} /></div>
            {!route.project ? <Welcome count={projects.length} /> : null}
            {route.project && !project ? <Empty>loading…</Empty> : null}
            {project && route.perspective === "project" ? (
              <ProjectPerspective project={project} busy={busy} onChanged={() => void refreshProject(project.id)}
                onOpenRun={(id) => navigate({ project: project.id, run: id, perspective: "run" })} />
            ) : null}
            {route.run && !run ? <Empty>loading the run…</Empty> : null}
            {run && route.perspective === "run" ? (
              <RunPerspective run={run} events={events} nodes={nodes} onReview={() => navigate({ perspective: "review" })}
                onCancel={() => void act("cancel")} onContinue={() => void act("continue")} onDiscard={() => void act("discard")} busy={busy} />
            ) : null}
            {run && route.perspective === "review" ? <ReviewPerspective run={run} checkpoint={checkpoint} onDecide={(d) => void decide(d)} busy={busy} error={null} /> : null}
            {run && route.perspective === "model" ? <ModelPerspective view={model} error={run.status === "running" ? "the model arrives when the run reaches the checkpoint" : modelError} /> : null}
            {run && route.perspective === "artefacts" ? <ArtefactsPerspective run={run} artefacts={artefacts} /> : null}
            {run && route.perspective === "log" ? <LogPerspective events={events} /> : null}
          </div>
        </main>

        <aside className="grid min-h-0 grid-rows-[auto_minmax(0,3fr)_minmax(0,2fr)] border-l border-line bg-pane">
          <header className="flex items-center justify-between border-b border-line px-3 py-2 text-xs uppercase tracking-wide text-ink-dim">
            <span>event stream</span><span className="font-mono normal-case">{events.length} lines</span>
          </header>
          <div className="min-h-0 overflow-auto py-1"><EventStream events={events} dense /></div>
          <Console entries={run ? (transcripts[run.id] ?? []) : []} onAsk={(t) => void ask(t)} busy={asking} enabled={Boolean(run)}
            onNavigate={(p) => navigate({ perspective: p })} />
        </aside>
      </div>

      <footer className="flex items-center gap-4 border-t border-line bg-pane px-4 py-1 font-mono text-xs text-ink-dim">
        {run ? (
          <>
            <span className="flex items-center gap-2"><Dot status={run.status} pulse />{run.status}</span>
            <span>elapsed {formatDuration(elapsed)}</span>
            <span>{usage.calls} calls</span>
            <span>in {formatTokens(usage.input)} · out {formatTokens(usage.output)}</span>
            {usage.errors ? <span className="text-bad">{usage.errors} errors</span> : null}
            {usage.backstops ? <span className="text-warn">{usage.backstops} backstops</span> : null}
          </>
        ) : <span>no run selected</span>}
        <span className="ml-auto">{nodes.length} nodes</span>
      </footer>
    </div>
  );
}

function Welcome({ count }: { count: number }) {
  return (
    <div className="mx-auto mt-16 max-w-xl text-center">
      <h1 className="text-2xl font-semibold"><span className="text-accent">vault</span>-agent workbench</h1>
      <p className="mt-3 text-sm text-ink-dim">Create a project, attach the requirements document and the declared source schema, run the generator, decide the checkpoint, inspect the model, the graphs and the artefacts. Every action is recorded as the CLI command it is equivalent to.</p>
      <p className="mt-6 text-xs text-ink-faint">{count === 0 ? "No projects yet — name one in the left pane." : "Select a project in the left pane."}</p>
    </div>
  );
}
