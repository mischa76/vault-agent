import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
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
