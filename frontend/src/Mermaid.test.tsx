import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import mermaid from "mermaid";
import { Mermaid } from "./components/Mermaid";

// WP88: Mermaid itself is mocked — what is tested is the tile around the SVG it returns.
vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async () => ({ svg: '<svg width="100%" viewBox="0 0 800 400" style="max-width: 800px;"><g></g></svg>' })),
  },
}));

async function mount(title: string) {
  const view = render(<Mermaid title={title} source={"flowchart LR\n  A --> B"} />);
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  const svg = view.container.querySelector("svg") as SVGSVGElement;
  return { ...view, svg };
}

describe("Mermaid tile (WP88)", () => {
  it("offers zoom out, zoom in, fit, 1:1 and full screen", async () => {
    await mount("Model A");
    for (const name of ["zoom out", "zoom in", "fit", "actual size", "full screen"]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
  });
  it("1:1 is the natural width, zoom scales it, fit returns to the tile", async () => {
    const { svg } = await mount("Model B");
    expect(svg.style.width).toBe("100%");
    fireEvent.click(screen.getByRole("button", { name: "actual size" }));
    expect(svg.style.width).toBe("800px");
    fireEvent.click(screen.getByRole("button", { name: "zoom in" }));
    expect(svg.style.width).toBe("1000px");
    fireEvent.click(screen.getByRole("button", { name: "zoom out" }));
    expect(svg.style.width).toBe("800px");
    fireEvent.click(screen.getByRole("button", { name: "fit" }));
    expect(svg.style.width).toBe("100%");
  });
  it("zooms with ctrl and the mouse wheel", async () => {
    const { svg } = await mount("Model C");
    fireEvent.click(screen.getByRole("button", { name: "actual size" }));
    fireEvent.wheel(svg.parentElement as HTMLElement, { deltaY: -100, ctrlKey: true });
    expect(svg.style.width).toBe("1000px");
  });
  it("opens full screen as a dialog and closes on Escape", async () => {
    await mount("Model D");
    fireEvent.click(screen.getByRole("button", { name: "full screen" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it("remembers the zoom per tile while the page is open", async () => {
    const first = await mount("Model E");
    fireEvent.click(screen.getByRole("button", { name: "actual size" }));
    first.unmount();
    const { svg } = await mount("Model E");
    expect(svg.style.width).toBe("800px");
  });
});

// WP143 (C49): the tile's picture printed and saved — drawn again in Mermaid's light theme, on a
// sheet of its own for the print, as a file for the rest. Committed red: the tile had neither tool.
describe("Mermaid tile — print and save (WP143)", () => {
  afterEach(() => { vi.restoreAllMocks(); vi.mocked(mermaid.initialize).mockClear(); });
  const settle = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

  it("G1 offers print and save SVG on a diagram, neither on an empty tile", async () => {
    const view = await mount("Model P1");
    expect(screen.getByRole("button", { name: "print" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "save SVG" })).toBeInTheDocument();
    view.unmount();
    render(<Mermaid title="Empty" source={"erDiagram"} />);
    await settle();
    expect(screen.queryByRole("button", { name: "print" })).toBeNull();
    expect(screen.queryByRole("button", { name: "save SVG" })).toBeNull();
  });

  it("G2 prints the light picture on a sheet of its own and removes the sheet afterwards", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    const view = render(<Mermaid title="Output model — the raw vault" sheet="run stores:20261117T080000000000Z" source={"flowchart LR\n  A --> B"} />);
    await settle();
    const onScreen = view.container.querySelector("svg");
    fireEvent.click(screen.getByRole("button", { name: "print" }));
    await settle();
    expect(vi.mocked(mermaid.initialize).mock.calls.some(([config]) => config.theme === "default")).toBe(true);
    const sheet = document.querySelector(".print-sheet");
    expect(sheet).not.toBeNull();
    expect(sheet!.textContent).toContain("Output model — the raw vault");
    expect(sheet!.textContent).toContain("run stores:20261117T080000000000Z");
    expect(sheet!.querySelector("svg")).not.toBeNull();
    expect(document.documentElement.classList.contains("printing")).toBe(true);
    expect(print).toHaveBeenCalledTimes(1);
    fireEvent(window, new Event("afterprint"));
    expect(document.querySelector(".print-sheet")).toBeNull();
    expect(document.documentElement.classList.contains("printing")).toBe(false);
    expect(view.container.querySelector("svg")).toBe(onScreen);
  });

  it("G3 saves the light picture as an SVG file named after the title", async () => {
    let saved: Blob | null = null;
    let name = "";
    URL.createObjectURL = vi.fn((blob: Blob) => { saved = blob; return "blob:x"; });
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { name = this.download; });
    await mount("Output model — the raw vault (hubs, links, satellites)");
    fireEvent.click(screen.getByRole("button", { name: "save SVG" }));
    await settle();
    expect(name).toBe("output-model-the-raw-vault-hubs-links-satellites.svg");
    expect(saved).not.toBeNull();
    expect(saved!.type).toBe("image/svg+xml");
    const text = await new Promise<string>((resolve) => { const r = new FileReader(); r.onload = () => resolve(String(r.result)); r.readAsText(saved!); });
    expect(text).toMatch(/^<\?xml/);
    expect(text).toContain('xmlns="http://www.w3.org/2000/svg"');
    expect(text).toContain("<g>");
  });

  it("G4 the stylesheet prints the sheet and nothing else", async () => {
    const { readFileSync } = await import("node:fs");
    const css = readFileSync("src/styles.css", "utf8");
    const print = css.slice(css.indexOf("@media print"));
    expect(css).toContain("@media print");
    expect(print).toMatch(/html\.printing body > \*:not\(\.print-sheet\)\s*\{\s*display:\s*none/);
    expect(css).toMatch(/\.print-sheet\s*\{\s*display:\s*none/);
  });
});
