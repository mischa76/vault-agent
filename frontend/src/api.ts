// A thin typed client over the WP66 API. Every call here is one the CLI could make; the run
// records the equivalent (`cli_equivalents`).
import type { Artefact, Checkpoint, ConsoleAnswer, Decision, Events, GraphNode, ModelView, ParseResult, Project, ProjectCheck, ProjectFile, ProjectSummary, Run } from "./types";

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`${status}: ${detail}`);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* no JSON body */
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const api = {
  graph: () => call<{ nodes: GraphNode[] }>("/api/graph"),
  projects: () => call<ProjectSummary[]>("/api/projects"),
  project: (id: string) => call<Project>(`/api/projects/${encodeURIComponent(id)}`),
  createProject: (name: string) => call<ProjectSummary>("/api/projects", json({ name })),
  addFile: (id: string, kind: ProjectFile["kind"], name: string, content: string) =>
    call<ProjectFile>(`/api/projects/${encodeURIComponent(id)}/files`, json({ kind, name, content })),
  startRun: (id: string, requirements: string, schema: string | null, existing_run: string | null) =>
    call<Run>(`/api/projects/${encodeURIComponent(id)}/runs`, json({ requirements, schema, existing_run })),
  run: (id: string) => call<Run>(`/api/runs/${encodeURIComponent(id)}`),
  cancel: (id: string) => call<Run>(`/api/runs/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
  continueRun: (id: string) => call<Run>(`/api/runs/${encodeURIComponent(id)}/continue`, { method: "POST" }),
  events: (id: string, after: number) =>
    call<Events>(`/api/runs/${encodeURIComponent(id)}/events?after=${after}`),
  checkpoint: (id: string) => call<Checkpoint>(`/api/runs/${encodeURIComponent(id)}/checkpoint`),
  decide: (id: string, decision: Decision) =>
    call<Run>(`/api/runs/${encodeURIComponent(id)}/checkpoint`, json(decision)),
  artefacts: (id: string) => call<Artefact[]>(`/api/runs/${encodeURIComponent(id)}/artefacts`),
  artefactUrl: (id: string, path: string) =>
    `/api/runs/${encodeURIComponent(id)}/artefacts/${path.split("/").map(encodeURIComponent).join("/")}`,
  artefactText: async (id: string, path: string) => {
    const response = await fetch(api.artefactUrl(id, path));
    if (!response.ok) throw new ApiError(response.status, response.statusText);
    return response.text();
  },
  model: (id: string) => call<ModelView>(`/api/runs/${encodeURIComponent(id)}/model`),
  projectCheck: (id: string) => call<ProjectCheck>(`/api/runs/${encodeURIComponent(id)}/project`),
  parse: (id: string) => call<ParseResult>(`/api/runs/${encodeURIComponent(id)}/parse`, { method: "POST" }),
  console: (id: string, text: string) =>
    call<ConsoleAnswer>(`/api/runs/${encodeURIComponent(id)}/console`, json({ text })),
  reportUrl: (id: string) => `/api/runs/${encodeURIComponent(id)}/report`,
};
