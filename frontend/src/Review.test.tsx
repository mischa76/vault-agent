import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { groupItems, ReviewPerspective } from "./perspectives/Review";
import type { Checkpoint, Run } from "./types";

const run: Run = {
  id: "bank:1", project: "bank", status: "paused", thread_id: "t", out_dir: "/x", requirements: "req.md", schema: null,
  existing_run: null, started: "2026-10-11T10:00:00+00:00", finished: null, error: null, cli_equivalents: ["vault-agent run req.md --out /x"],
};
const checkpoint: Checkpoint = {
  run: "bank:1", phase: "signoff", blocked: true, decisions: 1, disclosures: 1, unresolved: [],
  links: [], resolutions: [], answers: ["NEW", "same_as_candidate", "unresolved"],
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

describe("Review — the owner field (WP87)", () => {
  it("accepts a bare email address as a filled owner", () => {
    render(<ReviewPerspective run={run} checkpoint={checkpoint} onDecide={() => undefined} busy={false} error={null} />);
    fireEvent.change(screen.getByLabelText("owner for customer"), { target: { value: "john.doe@acme.com" } });
    expect(screen.getByRole("button", { name: "Accept and continue" })).toBeEnabled();
  });
  it("says at the field what is wrong", () => {
    render(<ReviewPerspective run={run} checkpoint={checkpoint} onDecide={() => undefined} busy={false} error={null} />);
    fireEvent.change(screen.getByLabelText("owner for customer"), { target: { value: "John" } });
    expect(screen.getByText("Name <email> or an email address")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Accept and continue" })).toBeDisabled();
  });
});

const resolution: Checkpoint = {
  ...checkpoint, phase: "resolution", blocked: false, decisions: 0, disclosures: 0, items: [],
  links: [{ key: "Account.CustomerID", kind: "license", target: "Customer (no hub yet)", note: "declared_fk_pending: builds nothing", evidence: ["Account.CustomerID → Customer.CustomerID"] }],
};

describe("Review at the resolution checkpoint", () => {
  it("shows the license with build as the default, no owner fields, and sends --no-link on decline", () => {
    const onDecide = vi.fn();
    render(<ReviewPerspective run={run} checkpoint={resolution} onDecide={onDecide} busy={false} error={null} />);
    expect(screen.getByText(/Resolution checkpoint/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/^owner for/)).not.toBeInTheDocument();
    const box = screen.getByLabelText("build Account.CustomerID");
    expect(box).toBeChecked();
    fireEvent.click(box);
    fireEvent.click(screen.getByRole("button", { name: /decline 1/ }));
    expect(onDecide).toHaveBeenCalledWith(expect.objectContaining({ accept: true, links: { "Account.CustomerID": false }, owners: {} }));
  });
});

// WP82: bindings at sign-off — a relation and its column aliases for every stage no rule could bind,
// and the `--map` field on an unresolved mapping; both reach the decision the API takes.
const withBindings: Checkpoint = {
  ...checkpoint,
  items: [
    ...checkpoint.items,
    { kind: "mapping_unresolved", summary: "concept 'partner number' could not be resolved", detail: "", source: "source_mapper", group: "general", asset: "partner number", role: "decision" },
  ],
  bindings: [
    { stage: "stg_store_sales_person", reads: "raw_store_sales_person", reason: "rejected", tried: "StoreMaster", expected_columns: ["STOREID", "BUSINESSENTITYID"], role: "decision" },
    { stage: "stg_work_order_operation", reads: "raw_work_order_operation", reason: "none", tried: null, expected_columns: ["WORKORDERID", "OPERATIONSEQUENCE"], role: "disclosure" },
  ],
};

describe("Review — bindings at sign-off (WP82)", () => {
  it("offers a relation and an aliases field per pending stage and sends them as bindings", () => {
    const onDecide = vi.fn();
    render(<ReviewPerspective run={run} checkpoint={withBindings} onDecide={onDecide} busy={false} error={null} />);
    expect(screen.getByText("raw_store_sales_person")).toBeInTheDocument();
    expect(screen.getByText(/StoreMaster/)).toBeInTheDocument(); // what the rule tried, and was refused
    fireEvent.change(screen.getByLabelText("relation for stg_store_sales_person"), { target: { value: "StoreMaster" } });
    fireEvent.change(screen.getByLabelText("column aliases for stg_store_sales_person"), { target: { value: "BUSINESSENTITYID=SalesPersonID, STOREID = StoreID" } });
    fireEvent.change(screen.getByLabelText("relation for stg_work_order_operation"), { target: { value: "WorkOrderRouting" } });
    fireEvent.change(screen.getByLabelText("source for partner number"), { target: { value: "VICTOR_PARTNER.PARTN_NR" } });
    fireEvent.change(screen.getByLabelText("owner for customer"), { target: { value: "jane@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Accept and continue" }));
    expect(onDecide).toHaveBeenCalledTimes(1);
    const decision = onDecide.mock.calls[0]![0];
    expect(decision.bindings).toEqual({
      stg_store_sales_person: { relation: "StoreMaster", columns: { BUSINESSENTITYID: "SalesPersonID", STOREID: "StoreID" } },
      stg_work_order_operation: { relation: "WorkOrderRouting", columns: {} },
    });
    expect(decision.mappings).toEqual({ "partner number": "VICTOR_PARTNER.PARTN_NR" });
  });
  it("sends no bindings when the fields stay empty, and says at the field when an alias is malformed", () => {
    const onDecide = vi.fn();
    render(<ReviewPerspective run={run} checkpoint={withBindings} onDecide={onDecide} busy={false} error={null} />);
    fireEvent.change(screen.getByLabelText("column aliases for stg_store_sales_person"), { target: { value: "BUSINESSENTITYID" } });
    expect(screen.getByText("STAGE_COLUMN=column, separated by commas")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("column aliases for stg_store_sales_person"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("owner for customer"), { target: { value: "jane@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Accept and continue" }));
    expect(onDecide.mock.calls[0]![0].bindings).toEqual({});
    expect(onDecide.mock.calls[0]![0].mappings).toEqual({});
  });
});
