import { readFileSync } from "node:fs";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectPerspective } from "./perspectives/Project";
import { ReviewPerspective } from "./perspectives/Review";
import { RunPerspective } from "./perspectives/Run";
import { SourceSection } from "./components/Source";
import type { Checkpoint, Project, Run, SourceView } from "./types";

// WP141 (C45): the button kinds follow a written rule (manual 14, `BUTTON_KINDS` in ui.tsx) —
// primary at most once per perspective, add for what adds, danger for what destroys at every
// size, ghost for navigation and toggles. Committed red: no control carried its kind.
vi.mock("./api", () => ({
  ApiError: class extends Error {},
  api: {
    source: vi.fn(), sourceTables: vi.fn(async () => []),
    settings: vi.fn(async () => ({
      settings: {},
      effective: { target_platform: "postgres", primary_model: "claude-sonnet-5-5", heavy_model: "claude-opus-5-5", anthropic_base_url: null },
      environment: { llm_provider: "anthropic", anthropic_api_key_set: false, primary_model: "claude-sonnet-5-5", heavy_model: "claude-opus-5-5", anthropic_base_url: null },
    })),
    addFile: vi.fn(async () => ({ kind: "requirements", name: "brd.md", bytes: 3 })),
    check: vi.fn(async () => null), cost: vi.fn(async () => null),
  },
}));
import { api } from "./api";

afterEach(() => vi.clearAllMocks());

const kindOf = (el: Element | null) => el?.closest("[data-kind]")?.getAttribute("data-kind");
const primaries = (root: HTMLElement) => Array.from(root.querySelectorAll('[data-kind="primary"]')).map((e) => e.textContent);

const project: Project = {
  id: "stores", name: "Stores", created: "2026-11-17T08:00:00+00:00",
  files: [{ kind: "requirements", name: "brd.md", bytes: 3 }, { kind: "schema", name: "s.yml", bytes: 9 }],
  runs: [{ id: "stores:20261117T080000000000Z", status: "finished", started: "2026-11-17T08:00:00+00:00", finished: null, requirements: "brd.md", schema: null, existing_run: null, error: null }],
} as unknown as Project;
const okSource: SourceView = { state: "ok", url: "sqlite:///x.db", dialect: "sqlite", schemas: ["main"] };

describe("Button kinds (WP141)", () => {
  it("G1 Project: attach adds, delete destroys, one primary", async () => {
    vi.mocked(api.source).mockResolvedValue({ state: "unset", url: null, dialect: null, schemas: [] });
    const { container } = render(<ProjectPerspective project={project} onChanged={() => undefined} onOpenRun={() => undefined} onDeleted={() => undefined} busy={false} />);
    await screen.findByText("source: not set");
    for (const kind of ["requirements", "schema", "profiling"]) {
      expect(kindOf(screen.getByLabelText(`attach ${kind}`))).toBe("add");
    }
    const file = new File(["# x"], "brd.md", { type: "text/markdown" });
    fireEvent.change(screen.getByLabelText("attach requirements"), { target: { files: [file] } });
    await waitFor(() => expect(api.addFile).toHaveBeenCalled());
    expect(kindOf(screen.getByRole("button", { name: "delete file s.yml" }))).toBe("danger");
    expect(kindOf(screen.getByRole("button", { name: "delete run 20261117T080000000000Z" }))).toBe("danger");
    expect(kindOf(screen.getByRole("button", { name: "delete project" }))).toBe("danger");
    expect(kindOf(screen.getByRole("button", { name: "save settings" }))).toBe("add");
    expect(primaries(container)).toEqual(["Run the generator"]);
  });

  it("G2 Source: the three producers add", async () => {
    vi.mocked(api.source).mockResolvedValue(okSource);
    render(<SourceSection projectId="stores" files={project.files} onChanged={() => undefined} busy={false} />);
    for (const name of ["read catalogue", "make profile", "infer keys"]) {
      expect(kindOf(await screen.findByRole("button", { name }))).toBe("add");
    }
  });

  const run = { id: "stores:1", project: "stores", status: "paused", cli_equivalents: [] } as unknown as Run;
  const signoff: Checkpoint = {
    run: "stores:1", phase: "signoff", blocked: false, decisions: 0, disclosures: 0, items: [], unresolved: [],
    links: [], resolutions: [], answers: [],
  } as unknown as Checkpoint;

  it("G3 Review: one primary per phase, discard destroys, record adds", () => {
    const first = render(<ReviewPerspective run={run} checkpoint={signoff} onDecide={() => undefined} busy={false} error={null} />);
    expect(primaries(first.container)).toEqual(["Accept and continue"]);
    expect(kindOf(screen.getByRole("button", { name: "Discard the run" }))).toBe("danger");
    expect(kindOf(screen.getByRole("button", { name: "Record without accepting" }))).toBe("add");
    first.unmount();
    const second = render(<ReviewPerspective run={run} checkpoint={{ ...signoff, phase: "resolution" }} onDecide={() => undefined} busy={false} error={null} />);
    expect(primaries(second.container)).toEqual(["Ratify as proposed and build the model"]);
  });

  it("G4 Run: the step forward is the one primary; cancel and discard destroy", () => {
    const props = { events: [], nodes: [], cost: null, check: null, onReview: () => undefined, onCancel: () => undefined, onContinue: () => undefined, onDiscard: () => undefined, busy: false };
    const paused = render(<RunPerspective {...props} run={run} />);
    expect(primaries(paused.container)).toEqual(["Open the checkpoint"]);
    paused.unmount();
    const running = render(<RunPerspective {...props} run={{ ...run, status: "running" }} />);
    expect(primaries(running.container)).toEqual([]);
    expect(kindOf(screen.getByRole("button", { name: "Cancel the run" }))).toBe("danger");
    running.unmount();
    const interrupted = render(<RunPerspective {...props} run={{ ...run, status: "interrupted" }} />);
    expect(primaries(interrupted.container)).toEqual(["Continue the run"]);
    expect(kindOf(screen.getByRole("button", { name: "Discard the run" }))).toBe("danger");
  });

  it("G5 the palette: danger is a hue of its own and readable on every surface", () => {
    const css = readFileSync("src/styles.css", "utf8");
    const token = (name: string) => /#[0-9a-f]{6}/i.exec(css.slice(css.indexOf(`--color-${name}:`)))![0];
    const rgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255) as [number, number, number];
    const hue = (hex: string) => {
      const [r, g, b] = rgb(hex); const max = Math.max(r, g, b), d = max - Math.min(r, g, b);
      const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
      return (h * 60 + 360) % 360;
    };
    const lum = (hex: string) => { const [r, g, b] = rgb(hex).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)) as [number, number, number]; return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
    const contrast = (a: string, b: string) => { const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x) as [number, number]; return (hi + 0.05) / (lo + 0.05); };
    const apart = Math.abs(hue(token("bad")) - hue(token("accent")));
    expect(Math.min(apart, 360 - apart)).toBeGreaterThanOrEqual(20);
    for (const surface of ["bg", "pane", "pane-2"]) expect(contrast(token("bad"), token(surface))).toBeGreaterThanOrEqual(4.5);
  });
});
