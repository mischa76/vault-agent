// A thin typed client over the WP66 API. Every call here is one the CLI could make; the run
// records the equivalent (`cli_equivalents`).
import type { ProjectSettings, ProjectSettingsView, Artefact, Checkpoint, ConsoleAnswer, Decision, Events, GraphNode, ModelView, ParseResult, Project, ProjectCheck, ProjectFile, ProjectSummary, Run, StartRunBody } from "./types";

// WP91: the CLI's --pit / --as-of-* on the run start; the server validates the bounds.
export type BusinessVault = { pit: boolean; as_of_start: string; as_of_end: string; as_of_grain: "day" | "month" };

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
  // WP82: one body, the CLI's `run` options (profiling and the platform included).
  startRun: (id: string, body: StartRunBody) =>
    call<Run>(`/api/projects/${encodeURIComponent(id)}/runs`, json(body)),
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
  // WP112 (C2): deleting — the API keeps what another run depends on and says so (409).
  deleteProject: (id: string) =>
    call<{ deleted: string; runs: number; files: number }>(`/api/projects/${encodeURIComponent(id)}`, { method: "DELETE" }),
  deleteFile: (id: string, name: string) =>
    call<{ deleted: string; kind: string }>(
      `/api/projects/${encodeURIComponent(id)}/files/${encodeURIComponent(name)}`, { method: "DELETE" }),
  deleteRun: (id: string) =>
    call<{ deleted: string; project: string }>(`/api/runs/${encodeURIComponent(id)}`, { method: "DELETE" }),
  // WP113 (C3): the project's settings — stored, effective, and the environment (never a secret).
  settings: (id: string) => call<ProjectSettingsView>(`/api/projects/${encodeURIComponent(id)}/settings`),
  saveSettings: (id: string, body: ProjectSettings) =>
    call<ProjectSettingsView>(`/api/projects/${encodeURIComponent(id)}/settings`, { method: "PUT", body: JSON.stringify(body) }),
};
