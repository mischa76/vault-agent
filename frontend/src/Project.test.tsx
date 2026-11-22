import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProjectPerspective } from "./perspectives/Project";
import type { Project } from "./types";

// WP82: the start options the CLI has — profiling and the target platform — reach the API.
vi.mock("./api", () => ({
  ApiError: class extends Error {},
  api: {
    startRun: vi.fn(async () => ({ id: "stores:1" })), addFile: vi.fn(),
    deleteFile: vi.fn(async () => ({ deleted: "prof.yml" })), deleteRun: vi.fn(async () => ({ deleted: "x" })),
    deleteProject: vi.fn(async () => ({ deleted: "stores" })),
    source: vi.fn(async () => ({ state: "unset", url: null, dialect: null, schemas: [] })),
    sourceTables: vi.fn(async () => []),
    readCatalogue: vi.fn(async () => ({
      file: { kind: "schema", name: "source_schema.yml", bytes: 10 }, command: "vault-agent source-schema --schema Person --out inputs/source_schema.yml",
      warnings: [], summary: { tables: 1, columns: 2, comments: 0, foreign_keys: 0 },
    })),
    settings: vi.fn(async () => ({
      settings: {},
      effective: { target_platform: "postgres", primary_model: "claude-sonnet-5-5", heavy_model: "claude-opus-5-5", anthropic_base_url: null },
      environment: { llm_provider: "anthropic", anthropic_api_key_set: false, primary_model: "claude-sonnet-5-5", heavy_model: "claude-opus-5-5", anthropic_base_url: null },
    })),
    // PUT /settings answers with the whole view, as GET does (app.py `put_settings`); a mock that
    // answered with the settings alone left the perspective reading `environment` of nothing.
    saveSettings: vi.fn(async (_id: string, body: unknown) => ({
      settings: body,
      effective: { target_platform: "postgres", primary_model: "claude-sonnet-5-5", heavy_model: "claude-opus-5-5", anthropic_base_url: null },
      environment: { llm_provider: "anthropic", anthropic_api_key_set: false, primary_model: "claude-sonnet-5-5", heavy_model: "claude-opus-5-5", anthropic_base_url: null },
    })),
  },
}));
import { api } from "./api";

const project: Project = {
  id: "stores", name: "Stores", created: "2026-10-24T10:00:00+00:00",
  files: [
    { kind: "requirements", name: "req.md", bytes: 10 },
    { kind: "schema", name: "schema.yml", bytes: 10 },
    { kind: "profiling", name: "prof.yml", bytes: 10 },
  ],
  runs: [],
};

describe("Project — starting a run (WP82)", () => {
  it("offers the profiling file and the platform, and sends both with the start", async () => {
    const onOpenRun = vi.fn();
    render(<ProjectPerspective project={project} onChanged={() => undefined} onOpenRun={onOpenRun} onDeleted={() => undefined} busy={false} />);
    expect(screen.getByLabelText("profiling")).toHaveValue("");
    expect(screen.getByLabelText("target platform")).toHaveValue("postgres");
    fireEvent.change(screen.getByLabelText("profiling"), { target: { value: "prof.yml" } });
    fireEvent.change(screen.getByLabelText("target platform"), { target: { value: "databricks" } });
    fireEvent.click(screen.getByRole("button", { name: "Run the generator" }));
    await screen.findByRole("button", { name: "Run the generator" });
    expect(api.startRun).toHaveBeenCalledWith("stores", expect.objectContaining({
      requirements: "req.md", schema: "schema.yml", existing_run: null,
      profiling: "prof.yml", target_platform: "databricks",
    }));
    expect(onOpenRun).toHaveBeenCalledWith("stores:1");
  });
});

// WP112 (C2): deleting — a file, a run, the project — asks first and goes through the API.
describe("Project — deleting (WP112)", () => {
  const withRuns: Project = {
    ...project,
    runs: [
      { id: "stores:20261031T100000000000Z", status: "finished", started: "", finished: "", requirements: "req.md", schema: "schema.yml", existing_run: null, error: null, profiling: null, target_platform: "postgres" },
      { id: "stores:20261031T110000000000Z", status: "paused", started: "", finished: null, requirements: "req.md", schema: "schema.yml", existing_run: null, error: null, profiling: null, target_platform: "postgres" },
    ],
  };

  it("deletes a file after confirmation and not without it", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    const onChanged = vi.fn();
    render(<ProjectPerspective project={withRuns} onChanged={onChanged} onOpenRun={() => undefined} onDeleted={() => undefined} busy={false} />);
    fireEvent.click(screen.getByRole("button", { name: "delete file prof.yml" }));
    expect(api.deleteFile).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "delete file prof.yml" }));
    await screen.findByRole("button", { name: "delete file prof.yml" });
    expect(api.deleteFile).toHaveBeenCalledWith("stores", "prof.yml");
    expect(onChanged).toHaveBeenCalled();
    confirm.mockRestore();
  });

  it("offers to delete a finished run, not a paused one, and the project after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onDeleted = vi.fn();
    render(<ProjectPerspective project={withRuns} onChanged={() => undefined} onOpenRun={() => undefined} onDeleted={onDeleted} busy={false} />);
    expect(screen.getByRole("button", { name: "delete run 20261031T110000000000Z" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "delete run 20261031T100000000000Z" }));
    await screen.findByRole("button", { name: "delete run 20261031T100000000000Z" });
    expect(api.deleteRun).toHaveBeenCalledWith("stores:20261031T100000000000Z");
    fireEvent.click(screen.getByRole("button", { name: "delete project" }));
    await screen.findByRole("button", { name: "delete project" });
    expect(api.deleteProject).toHaveBeenCalledWith("stores");
    expect(onDeleted).toHaveBeenCalled();
  });
});

// WP113 (C3): the project's settings — platform, model ids, base URL — shown, saved, and the
// secrets only as "set"/"not set".
describe("Project — settings (WP113)", () => {
  it("shows the effective settings and saves what was typed", async () => {
    render(<ProjectPerspective project={project} onChanged={() => undefined} onOpenRun={() => undefined} onDeleted={() => undefined} busy={false} />);
    expect(await screen.findByDisplayValue("claude-sonnet-5-5")).toBeInTheDocument();
    expect(screen.getByText(/API key/)).toHaveTextContent("not set");
    fireEvent.change(screen.getByLabelText("anthropic base URL"), { target: { value: "http://proxy.local:8080" } });
    fireEvent.change(screen.getByLabelText("primary model"), { target: { value: "my-model" } });
    fireEvent.click(screen.getByRole("button", { name: "save settings" }));
    await screen.findByRole("button", { name: "save settings" });
    expect(api.saveSettings).toHaveBeenCalledWith("stores", expect.objectContaining({
      anthropic_base_url: "http://proxy.local:8080", primary_model: "my-model",
    }));
  });
});

// WP114 (C3): the naming profile in the settings — saved with the rest.
describe("Project — naming profile (WP114)", () => {
  it("saves the naming profile's fields", async () => {
    render(<ProjectPerspective project={project} onChanged={() => undefined} onOpenRun={() => undefined} onDeleted={() => undefined} busy={false} />);
    await screen.findByDisplayValue("claude-sonnet-5-5");
    fireEvent.change(screen.getByLabelText("staging prefix"), { target: { value: "stage_" } });
    fireEvent.change(screen.getByLabelText("technical case"), { target: { value: "lower" } });
    fireEvent.click(screen.getByRole("button", { name: "save settings" }));
    await screen.findByRole("button", { name: "save settings" });
    expect(api.saveSettings).toHaveBeenCalledWith("stores", expect.objectContaining({
      naming: expect.objectContaining({ staging_prefix: "stage_", technical_case: "lower" }),
    }));
  });
});

// WP119 follow-up (2026-11-07): a catalogue read in the Source section is the run's schema
// at once, as an uploaded one is — otherwise the form stays on „none" and the run is ungrounded.
describe("Project — the Source section's file is selected for the run (WP119)", () => {
  it("selects the catalogue just read as the source schema", async () => {
    vi.mocked(api.source).mockResolvedValueOnce({ state: "ok", url: "postgresql://vault:***@localhost/vault", dialect: "postgresql", schemas: ["Person"] });
    const bare: Project = { ...project, files: [{ kind: "requirements", name: "req.md", bytes: 10 }] };
    const { rerender } = render(<ProjectPerspective project={bare} onChanged={() => undefined} onOpenRun={() => undefined} onDeleted={() => undefined} busy={false} />);
    fireEvent.click(await screen.findByLabelText("schema Person"));
    fireEvent.click(screen.getByRole("button", { name: "read catalogue" }));
    await waitFor(() => expect(api.readCatalogue).toHaveBeenCalled());
    const withSchema: Project = { ...bare, files: [...bare.files, { kind: "schema", name: "source_schema.yml", bytes: 10 }] };
    rerender(<ProjectPerspective project={withSchema} onChanged={() => undefined} onOpenRun={() => undefined} onDeleted={() => undefined} busy={false} />);
    await waitFor(() => expect(screen.getByLabelText("source schema (grounding)")).toHaveValue("source_schema.yml"));
  });
});
