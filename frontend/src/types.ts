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

// WP82: the CLI's --target-platform choices — `TargetPlatform` in src/vault_agent/rules/platforms.py;
// tests/test_wp82_parity.py holds this list against it.
export const PLATFORMS = ["postgres", "databricks"] as const;
export type Platform = (typeof PLATFORMS)[number];

export interface RunSummary {
  id: string;
  status: RunStatus;
  started: string | null;
  finished: string | null;
  requirements: string | null;
  schema: string | null;
  existing_run: string | null;
  error: string | null;
  profiling?: string | null; // WP82
  target_platform?: string; // WP82
}

// WP82: what `POST /api/projects/{id}/runs` takes — the CLI's `run` options.
export interface StartRunBody {
  requirements: string;
  schema: string | null;
  existing_run: string | null;
  profiling: string | null;
  target_platform?: Platform | null; // WP113: null = the project's setting
  primary_model?: string | null;
  heavy_model?: string | null;
  anthropic_base_url?: string | null;
  pit?: boolean;
  as_of_start?: string;
  as_of_end?: string;
  as_of_grain?: "day" | "month";
  bridges?: string[]; // WP115: the CLI's repeatable --bridge, a path each
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
  checkpoints?: CheckpointRecord[];
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

export type CheckpointPhase = "resolution" | "signoff";

export interface LinkDecision {
  key: string;
  kind: "link" | "relationship" | "license";
  target: string;
  note: string;
  evidence: string[];
}

export interface ResolutionDecision {
  concept: string;
  label: string;
  entity: string | null;
  claim: string;
  category: string;
  confidence: number;
  evidence: string[];
}

// WP82: a stage no rule could bind — what the human needs to bind it.
export interface PendingBinding {
  stage: string;
  reads: string;
  reason: "rejected" | "none" | "ambiguous" | "shared" | string;
  tried: string | null;
  expected_columns: string[];
  role: "decision" | "disclosure";
}

// WP115: a bridge path proposed from two links citing one requirement around a shared hub — a
// decision, declined unless the human builds it (the CLI's --bridge / --no-bridge).
export interface BridgeProposal {
  path: string;
  requirement_ids: string[];
  evidence: string[];
}

export interface Checkpoint {
  run: string;
  phase: CheckpointPhase;
  blocked: boolean;
  decisions: number;
  disclosures: number;
  items: ReviewItem[];
  unresolved: Unresolved[];
  links: LinkDecision[];
  resolutions: ResolutionDecision[];
  answers: string[];
  bindings?: PendingBinding[]; // WP82
  bridges?: BridgeProposal[]; // WP115
}

// WP82: a stage's binding as the API takes it — the CLI's --bind "STAGE=RELATION(STAGE_COLUMN=column)".
export interface StageBinding {
  relation: string;
  columns: Record<string, string>;
}

export interface Decision {
  accept?: boolean;
  discard?: boolean;
  resolutions?: Record<string, string>;
  owners?: Record<string, string>;
  links?: Record<string, boolean>;
  bindings?: Record<string, StageBinding>; // WP82: --bind
  mappings?: Record<string, string>; // WP82: --map "concept=TABLE.COLUMN"
  bridges?: Record<string, boolean>; // WP115: --bridge / --no-bridge "<path>"
}

export interface CheckpointRecord {
  phase: CheckpointPhase;
  command: string;
}

export interface ParseResult {
  status: "ok" | "failed" | "unavailable";
  adapter: string | null;
  version?: string;
  seconds: number;
  errors: string[];
  log: string | null;
  command: string | null;
  detail?: string;
}

export interface ProjectCheck {
  run: string;
  staging_models: number;
  unresolved: string[];
  inferred: string[];
  dbt: { version: string; adapter: string } | null;
  parse: ParseResult | null;
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

export interface SubjectArea {
  name: string;
  increment: boolean;
  hubs: string[];
  links: string[];
  satellites: string[];
  neighbours: string[];
  mermaid: string;
}

export interface ModelView {
  run: string;
  model: DVModel;
  output_mermaid: string;
  input_mermaid: string;
  existing: DVModel | null;
  areas: SubjectArea[];
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

// WP113 (C3): what a project pins for its runs, what a run effectively takes, and the environment
// it inherits — the key only as set / not set, never its value.
// WP114 (C3): the physical naming profile the project's runs generate under.
export interface NamingProfile {
  staging_prefix: string; hashkey_suffix: string; hashdiff_suffix: string;
  load_datetime: string; record_source: string; applied_dts: string;
  technical_case: "upper" | "lower";
}

export const DEFAULT_NAMING: NamingProfile = {
  staging_prefix: "stg_", hashkey_suffix: "_HK", hashdiff_suffix: "_HASHDIFF",
  load_datetime: "LOAD_DATETIME", record_source: "RECORD_SOURCE", applied_dts: "APPLIED_DTS",
  technical_case: "upper",
};

export interface ProjectSettings {
  target_platform?: Platform | null;
  primary_model?: string | null;
  heavy_model?: string | null;
  anthropic_base_url?: string | null;
  naming?: NamingProfile | null;
}

export interface ProjectSettingsView {
  settings: ProjectSettings;
  effective: { target_platform: Platform; primary_model: string; heavy_model: string; anthropic_base_url: string | null; naming?: NamingProfile };
  environment: {
    llm_provider: string; anthropic_api_key_set: boolean; primary_model: string; heavy_model: string;
    anthropic_base_url: string | null; route?: string; credentials?: string;
  };
}
