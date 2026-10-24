import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProjectPerspective } from "./perspectives/Project";
import type { Project } from "./types";

// WP82: the start options the CLI has — profiling and the target platform — reach the API.
vi.mock("./api", () => ({
  ApiError: class extends Error {},
  api: { startRun: vi.fn(async () => ({ id: "stores:1" })), addFile: vi.fn() },
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
    render(<ProjectPerspective project={project} onChanged={() => undefined} onOpenRun={onOpenRun} busy={false} />);
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
