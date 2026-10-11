import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { groupItems, ReviewPerspective } from "./perspectives/Review";
import type { Checkpoint, Run } from "./types";

const run: Run = {
  id: "bank:1", project: "bank", status: "paused", thread_id: "t", out_dir: "/x", requirements: "req.md", schema: null,
  existing_run: null, started: "2026-10-11T10:00:00+00:00", finished: null, error: null, cli_equivalents: ["vault-agent run req.md --out /x"],
};
const checkpoint: Checkpoint = {
  run: "bank:1", blocked: true, decisions: 1, disclosures: 1, unresolved: [],
  items: [
    { kind: "advisory", summary: "Inferred the satellite relation", detail: "", source: "modeler", group: "inference", asset: null, role: "disclosure" },
    { kind: "contract_owner", summary: "Contract has no owner", detail: "", source: "data_contract", group: "general", asset: "customer", role: "decision" },
  ],
};

describe("Review", () => {
  it("groups decisions before disclosures", () => {
    const groups = groupItems(checkpoint.items);
    expect(groups.map((g) => g.role)).toEqual(["decision", "disclosure"]);
    expect(groups[0]!.kinds[0]!.kind).toBe("contract_owner");
  });
  it("renders the owner input for the contract decision and blocks accept until it is filled", () => {
    render(<ReviewPerspective run={run} checkpoint={checkpoint} onDecide={() => undefined} busy={false} error={null} />);
    expect(screen.getByLabelText("owner for customer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Accept and continue" })).toBeDisabled();
    expect(screen.getByText("1 decisions")).toBeInTheDocument();
    expect(screen.queryByText("Inferred the satellite relation")).not.toBeInTheDocument(); // disclosures folded
  });
});
