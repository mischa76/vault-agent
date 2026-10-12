// The API's shapes (WP66 chapter 14). The frontend knows nothing the API does not say.

export type RunStatus = "running" | "paused" | "finished" | "failed" | "crashed" | "discarded" | "interrupted";

export interface GraphNode {
  id: string;
  tool_name: string | null;
}

export interface ProjectFile {
  kind: "requirements" | "schema" | "profiling";
  name: string;
  bytes: number;
}

export interface RunSummary {
  id: string;
  status: RunStatus;
  started: string | null;
  finished: string | null;
  requirements: string | null;
  schema: string | null;
  existing_run: string | null;
  error: string | null;
}

export interface ProjectSummary {
  id: string;
  name: string;
  created: string;
  files: ProjectFile[];
}

export interface Project extends ProjectSummary {
  runs: RunSummary[];
}

export interface Run extends RunSummary {
  project: string;
  thread_id: string | null;
  out_dir: string;
  cli_equivalents: string[];
}

export interface TraceEvent {
  ts: string;
  kind: "llm_call" | "llm_error" | "backstop" | "llm_route";
  tool_name: string;
  model: string;
  client: string;
  attempt: number;
  stop_reason: string | null;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  error: string | null;
  payload: Record<string, unknown> | null;
  [extra: string]: unknown;
}

export interface Events {
  run: string;
  status: RunStatus;
  after: number;
  next: number;
  events: TraceEvent[];
}

export interface ReviewItem {
  kind: string;
  summary: string;
  detail: string;
  source: string;
  group: string;
  asset: string | null;
  role: "decision" | "disclosure";
}

export interface Unresolved {
  concept: string;
  evidence: unknown;
}

export interface Checkpoint {
  run: string;
  blocked: boolean;
  decisions: number;
  disclosures: number;
  items: ReviewItem[];
  unresolved: Unresolved[];
}

export interface Decision {
  accept?: boolean;
  discard?: boolean;
  resolutions?: Record<string, string>;
  owners?: Record<string, string>;
}

export interface Artefact {
  path: string;
  bytes: number;
}

export interface Construct {
  name: string;
  [field: string]: unknown;
}

export interface DVModel {
  hubs: Construct[];
  links: Construct[];
  satellites: Construct[];
  [field: string]: unknown;
}

export interface ModelView {
  run: string;
  model: DVModel;
  output_mermaid: string;
  input_mermaid: string;
  existing: DVModel | null;
}

export interface ConsoleRef {
  perspective: string;
  label: string;
}

export interface ConsoleAnswer {
  text: string;
  kind: "answer" | "help" | "unknown" | "unavailable";
  refs: ConsoleRef[];
  command: string | null;
}

export interface ConsoleEntry {
  question: string;
  answer: ConsoleAnswer;
}

export interface ApiErrorBody {
  detail: string | unknown;
}
