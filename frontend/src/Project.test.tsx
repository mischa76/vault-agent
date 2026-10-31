import { fireEvent, render, screen } from "@testing-library/react";
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
