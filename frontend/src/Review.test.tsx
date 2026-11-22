import { fireEvent, render, screen, within } from "@testing-library/react";
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

// WP142: a decision's radio group, and its answers in order with the chosen one marked.
const choice = (name: string) => screen.getByRole("radiogroup", { name });
const answers = (group: HTMLElement) => within(group).getAllByRole("radio").map((r) => `${r.textContent}${r.getAttribute("aria-checked") === "true" ? " ✓" : ""}`);

describe("Review at the resolution checkpoint", () => {
  // WP142 (C52): the answer is a pair of named choices, not a checkbox whose word is its state.
  it("shows the license with allow as the default, no owner fields, and sends --no-link on decline", () => {
    const onDecide = vi.fn();
    render(<ReviewPerspective run={run} checkpoint={resolution} onDecide={onDecide} busy={false} error={null} />);
    expect(screen.getByText(/Resolution checkpoint/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/^owner for/)).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    const group = choice("decision for Account.CustomerID");
    expect(answers(group)).toEqual(["Allow ✓", "Decline"]);
    fireEvent.click(within(group).getByRole("radio", { name: "Decline" }));
    expect(answers(group)).toEqual(["Allow", "Decline ✓"]);
    fireEvent.click(screen.getByRole("button", { name: /decline 1/ }));
    expect(onDecide).toHaveBeenCalledWith(expect.objectContaining({ accept: true, links: { "Account.CustomerID": false }, owners: {} }));
  });
});

// WP140 (C74): an inferred key is declined by the bulk answer unless a human names it (ADR-0018 §4).
// The screen showed it under "Declared keys" with its box checked and sent nothing for it.
const withInferred: Checkpoint = {
  ...resolution,
  links: [
    { key: "Account.CustomerID", kind: "license", target: "Customer (no hub yet)", note: "declared_fk_pending: builds nothing", evidence: [], provenance: "declared" },
    { key: "WorkOrderRouting.productid", kind: "license", target: "Product (no hub yet)", note: "inferred from data, not declared — declared_fk_pending: builds nothing", evidence: ["67131 rows, 149 distinct values, all among 504"], provenance: "inferred" },
  ],
};

describe("Review — an inferred key at the resolution checkpoint (WP140)", () => {
  it("shows it declined in a section of its own and sends no yes for it", () => {
    const onDecide = vi.fn();
    render(<ReviewPerspective run={run} checkpoint={withInferred} onDecide={onDecide} busy={false} error={null} />);
    expect(screen.getByText(/^Inferred keys/)).toBeInTheDocument();
    expect(answers(choice("decision for WorkOrderRouting.productid"))).toEqual(["Decline ✓", "Allow"]);
    expect(answers(choice("decision for Account.CustomerID"))).toEqual(["Allow ✓", "Decline"]);
    fireEvent.click(screen.getByRole("button", { name: /build the model/ }));
    expect(onDecide).toHaveBeenCalledWith(expect.objectContaining({ accept: true, links: {} }));
  });

  it("sends the yes when a human allows it", () => {
    const onDecide = vi.fn();
    render(<ReviewPerspective run={run} checkpoint={withInferred} onDecide={onDecide} busy={false} error={null} />);
    fireEvent.click(within(choice("decision for WorkOrderRouting.productid")).getByRole("radio", { name: "Allow" }));
    fireEvent.click(screen.getByRole("button", { name: /allow 1 inferred/ }));
    expect(onDecide).toHaveBeenCalledWith(expect.objectContaining({ accept: true, links: { "WorkOrderRouting.productid": true } }));
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

// WP115 (C22): a proposed bridge is a decision — unchecked until the human builds it.
describe("Review — bridge proposals (WP115)", () => {
  it("lists a proposed bridge declined and sends the answer with the decision", () => {
    const onDecide = vi.fn();
    const run2 = { id: "stores:1", project: "stores", status: "paused", thread_id: "t", out_dir: "/tmp/x", cli_equivalents: [],
      started: "", finished: null, requirements: "req.md", schema: null, existing_run: null, error: null, profiling: null, target_platform: "postgres" } as unknown as Run;
    const checkpoint2 = { run: "stores:1", phase: "signoff", links: [], resolutions: [], answers: [], blocked: false, decisions: 1, disclosures: 0,
      items: [], bindings: [], unresolved: [],
      bridges: [{ path: "hub_customer,link_account_customer,hub_account", requirement_ids: ["REQ-007"], evidence: ["both links cite REQ-007"] }] } as unknown as Checkpoint;
    render(<ReviewPerspective run={run2} checkpoint={checkpoint2} onDecide={onDecide} busy={false} error={null} />);
    const group = choice("decision for bridge hub_customer,link_account_customer,hub_account");
    expect(answers(group)).toEqual(["Decline ✓", "Build"]);
    fireEvent.click(within(group).getByRole("radio", { name: "Build" }));
    fireEvent.click(screen.getByRole("button", { name: /^accept and continue$/i }));
    expect(onDecide).toHaveBeenCalledWith(expect.objectContaining({
      bridges: { "hub_customer,link_account_customer,hub_account": true },
    }));
  });
});

// WP144 (C53 a): one decision per link pair and shared hub; the ends are chosen when building.
describe("Review — bridge proposals in groups (WP144)", () => {
  const AB_T = "hub_branch,link_account_branch,hub_account,link_transfer,hub_account";
  const AB_C = "hub_branch,link_account_branch,hub_account,link_account_customer,hub_customer";
  const run2 = { id: "stores:1", project: "stores", status: "paused", thread_id: "t", out_dir: "/tmp/x", cli_equivalents: [],
    started: "", finished: null, requirements: "req.md", schema: null, existing_run: null, error: null, profiling: null, target_platform: "postgres" } as unknown as Run;
  const entry = (path: string, group: string, links: string[]) => ({ path, group, links, hub: "hub_account", requirement_ids: ["REQ-007"], evidence: ["both links cite REQ-007"] });
  const grouped = { run: "stores:1", phase: "signoff", links: [], resolutions: [], answers: [], blocked: false, decisions: 2, disclosures: 0,
    items: [], bindings: [], unresolved: [],
    bridges: [
      entry(AB_C, "link_account_branch+link_account_customer@hub_account", ["link_account_branch", "link_account_customer"]),
      entry(AB_T, "link_account_branch+link_transfer@hub_account", ["link_account_branch", "link_transfer"]),
      entry(AB_T + ":counterparty", "link_account_branch+link_transfer@hub_account", ["link_account_branch", "link_transfer"]),
    ] } as unknown as Checkpoint;

  it("shows one card per group and declines every path of a group left alone", () => {
    const onDecide = vi.fn();
    render(<ReviewPerspective run={run2} checkpoint={grouped} onDecide={onDecide} busy={false} error={null} />);
    expect(screen.getAllByRole("radiogroup")).toHaveLength(2);
    expect(answers(choice("decision for bridge link_account_branch+link_transfer@hub_account"))).toEqual(["Decline ✓", "Build"]);
    expect(screen.queryByLabelText(/^path for /)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^accept and continue$/i }));
    expect(onDecide).toHaveBeenCalledWith(expect.objectContaining({
      bridges: { [AB_C]: false, [AB_T]: false, [AB_T + ":counterparty"]: false },
    }));
  });

  it("asks for the path once a group with several is built, and sends that path alone as the yes", () => {
    const onDecide = vi.fn();
    render(<ReviewPerspective run={run2} checkpoint={grouped} onDecide={onDecide} busy={false} error={null} />);
    fireEvent.click(within(choice("decision for bridge link_account_branch+link_transfer@hub_account")).getByRole("radio", { name: "Build" }));
    const pick = screen.getByLabelText("path for link_account_branch+link_transfer@hub_account") as HTMLSelectElement;
    expect(Array.from(pick.options).map((o) => o.value)).toEqual([AB_T, AB_T + ":counterparty"]);
    expect(pick.value).toBe(AB_T);
    fireEvent.change(pick, { target: { value: AB_T + ":counterparty" } });
    fireEvent.click(within(choice("decision for bridge link_account_branch+link_account_customer@hub_account")).getByRole("radio", { name: "Build" }));
    expect(screen.queryByLabelText("path for link_account_branch+link_account_customer@hub_account")).not.toBeInTheDocument(); // one path: nothing to choose
    fireEvent.click(screen.getByRole("button", { name: /^accept and continue$/i }));
    expect(onDecide).toHaveBeenCalledWith(expect.objectContaining({
      bridges: { [AB_C]: true, [AB_T]: false, [AB_T + ":counterparty"]: true },
    }));
  });
});

const contested: Checkpoint = {
  ...resolution, links: [],
  keys: [{
    table: "AddressType", default: ["Name"], primary_key: ["AddressTypeID"], natural_keys: ["Name"],
    first_choice: "AddressTypeID", first_choice_score: 0.6,
    evidence: ["the requirements' first choice is AddressTypeID (0.60)", "AddressType declares Name unique"],
  }],
};

describe("Review — contested hub keys (WP126)", () => {
  it("shows the natural key as the default and sends no key answer when it is left alone", () => {
    const onDecide = vi.fn();
    render(<ReviewPerspective run={run} checkpoint={contested} onDecide={onDecide} busy={false} error={null} />);
    expect(screen.getByText("1 hub keys")).toBeInTheDocument();
    expect(screen.getByLabelText("hub key for AddressType")).toHaveValue("Name");
    expect(screen.getByText("AddressType declares Name unique")).toBeInTheDocument();
    expect(screen.queryByLabelText("reason for AddressType")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ratify as proposed and build the model" }));
    expect(onDecide.mock.calls[0]![0].keys).toEqual({});
  });
  it("asks a reason for the technical primary key and blocks until it is given", () => {
    const onDecide = vi.fn();
    render(<ReviewPerspective run={run} checkpoint={contested} onDecide={onDecide} busy={false} error={null} />);
    fireEvent.change(screen.getByLabelText("hub key for AddressType"), { target: { value: "AddressTypeID" } });
    const accept = screen.getByRole("button", { name: "Ratify as proposed and build the model" });
    expect(accept).toBeDisabled();
    expect(screen.getByText("a reason is required for the technical key")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("reason for AddressType"), { target: { value: "the name is renamed yearly" } });
    expect(accept).toBeEnabled();
    fireEvent.click(accept);
    expect(onDecide.mock.calls[0]![0].keys).toEqual({
      AddressType: { columns: ["AddressTypeID"], reason: "the name is renamed yearly" },
    });
  });
  it("shows no key section at sign-off", () => {
    render(<ReviewPerspective run={run} checkpoint={{ ...checkpoint, keys: contested.keys }} onDecide={() => undefined} busy={false} error={null} />);
    expect(screen.queryByLabelText("hub key for AddressType")).not.toBeInTheDocument();
  });
});

// WP142 (C51): an entity resolution is answered from a list in plain words — the proposal first and
// preselected, the hubs of the vault by name; the CLI's tokens are what is sent, not what is read.
describe("Review — the entity-resolution answer (WP142)", () => {
  const pending: Checkpoint = {
    ...resolution, links: [], hubs: ["hub_business_entity", "hub_person", "hub_vendor"],
    resolutions: [
      { concept: "employee::businessentityid", label: "businessentityid", entity: "employee", claim: "IS the existing 'hub_business_entity'", category: "exact_key", confidence: 0.9, evidence: ["the key is the hub's"], proposed: "hub_business_entity", same_as: null },
      { concept: "contact::contactid", label: "contactid", entity: "contact", claim: "equivalent to 'hub_person' but keyed differently", category: "semantic", confidence: 0.7, evidence: [], proposed: "same_as_candidate", same_as: "hub_person" },
    ],
  };
  const options = (el: HTMLElement) => Array.from(el.querySelectorAll("option")).map((o) => o.textContent);

  it("offers the proposal first and selected, then the other answers in words and the hubs by name", () => {
    render(<ReviewPerspective run={run} checkpoint={pending} onDecide={() => undefined} busy={false} error={null} />);
    const merge = screen.getByLabelText("resolution for employee::businessentityid") as HTMLSelectElement;
    expect(merge.tagName).toBe("SELECT");
    expect(merge.selectedOptions[0]!.textContent).toBe("Keep the proposal — is hub_business_entity");
    expect(options(merge)).toEqual(["Keep the proposal — is hub_business_entity", "New hub", "Leave unresolved", "hub_person", "hub_vendor"]);
    const sameAs = screen.getByLabelText("resolution for contact::contactid") as HTMLSelectElement;
    expect(sameAs.selectedOptions[0]!.textContent).toBe("Keep the proposal — same as hub_person, keyed differently");
    expect(options(sameAs)).toEqual(["Keep the proposal — same as hub_person, keyed differently", "New hub", "Leave unresolved", "hub_business_entity", "hub_person", "hub_vendor"]);
  });

  it("sends nothing for a proposal left alone, and the CLI's value for another answer", () => {
    const onDecide = vi.fn();
    render(<ReviewPerspective run={run} checkpoint={pending} onDecide={onDecide} busy={false} error={null} />);
    fireEvent.click(screen.getByRole("button", { name: /build the model/ }));
    expect(onDecide).toHaveBeenLastCalledWith(expect.objectContaining({ accept: true, resolutions: {} }));
    fireEvent.change(screen.getByLabelText("resolution for employee::businessentityid"), { target: { value: "NEW" } });
    fireEvent.change(screen.getByLabelText("resolution for contact::contactid"), { target: { value: "hub_vendor" } });
    fireEvent.click(screen.getByRole("button", { name: /build the model/ }));
    expect(onDecide).toHaveBeenLastCalledWith(expect.objectContaining({
      resolutions: { "employee::businessentityid": "NEW", "contact::contactid": "hub_vendor" },
    }));
  });
});
