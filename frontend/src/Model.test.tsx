import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ModelPerspective } from "./perspectives/Model";
import type { ModelView } from "./types";

// Mermaid renders in a browser; here the figure's title is what the perspective chose to show.
vi.mock("./components/Mermaid", () => ({
  Mermaid: ({ title }: { title: string; source: string }) => <figure data-testid="diagram">{title}</figure>,
}));

const view: ModelView = {
  run: "bank:1",
  model: {
    hubs: [{ name: "hub_customer" }, { name: "hub_account" }],
    links: [{ name: "link_account_customer" }],
    satellites: [{ name: "sat_customer_details" }, { name: "sat_account_details" }],
  },
  output_mermaid: "flowchart LR\n  A",
  input_mermaid: "erDiagram\n  A",
  existing: null,
  areas: [
    { name: "crm", increment: false, hubs: ["hub_customer"], links: [], satellites: ["sat_customer_details"], neighbours: [], mermaid: "flowchart LR\n  C" },
    { name: "fin", increment: true, hubs: ["hub_account"], links: ["link_account_customer"], satellites: ["sat_account_details"], neighbours: ["hub_customer"], mermaid: "flowchart LR\n  F" },
  ],
};

describe("Model perspective — subject areas (WP80)", () => {
  it("offers the whole model and one button per area, and narrows to an area on click", () => {
    render(<ModelPerspective view={view} error={null} />);
    expect(screen.getByRole("button", { name: /whole model/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^crm/ })).toHaveTextContent("2");
    const fin = screen.getByRole("button", { name: /^fin/ });
    expect(fin).toHaveTextContent("3");
    expect(fin).toHaveTextContent("increment");
    expect(screen.getAllByTestId("diagram")[0]).toHaveTextContent("Output model — the raw vault");
    fireEvent.click(fin);
    expect(screen.getAllByTestId("diagram")[0]).toHaveTextContent("Subject area fin");
    expect(screen.getByText("hub_account")).toBeInTheDocument();
    expect(screen.getByText("link_account_customer")).toBeInTheDocument();
    expect(screen.queryByText("sat_customer_details")).not.toBeInTheDocument();
    expect(screen.getByText("hub_customer").closest("li")).toHaveTextContent("neighbour");
  });
  it("shows no strip when there is one area only", () => {
    render(<ModelPerspective view={{ ...view, areas: view.areas.slice(0, 1) }} error={null} />);
    expect(screen.queryByRole("button", { name: /whole model/ })).not.toBeInTheDocument();
  });
});
