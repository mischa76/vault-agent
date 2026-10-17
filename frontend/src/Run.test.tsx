import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProjectSection } from "./perspectives/Run";
import type { ProjectCheck } from "./types";

const check: ProjectCheck = {
  run: "bank:1", staging_models: 5, unresolved: ["stg_customer_details"], inferred: ["stg_account_customer"],
  dbt: { version: "1.9.10", adapter: "postgres" },
  parse: { status: "failed", adapter: "postgres", seconds: 12.5, errors: ["Compilation Error", "depends on a node named 'raw_x'"], log: "/x/.vault-agent/dbt-parse.log", command: "dbt parse" },
};

describe("Project section (WP78)", () => {
  it("shows unresolved and inferred stages, the dbt availability and the last parse", () => {
    const onParse = vi.fn();
    render(<ProjectSection check={check} onParse={onParse} parsing={false} />);
    expect(screen.getByText("1 unresolved")).toBeInTheDocument();
    expect(screen.getByText("stg_customer_details")).toBeInTheDocument();
    expect(screen.getByText("1 inferred")).toBeInTheDocument();
    expect(screen.getByText("dbt-core 1.9.10 with postgres")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText(/depends on a node named 'raw_x'/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "dbt parse" }));
    expect(onParse).toHaveBeenCalledTimes(1);
  });
  it("says so when no project is written and disables the button without dbt", () => {
    render(<ProjectSection check={{ ...check, staging_models: 0 }} onParse={() => undefined} parsing={false} />);
    expect(screen.getByText(/No dbt project written yet/)).toBeInTheDocument();
    render(<ProjectSection check={{ ...check, dbt: null, parse: null }} onParse={() => undefined} parsing={false} />);
    expect(screen.getByRole("button", { name: "dbt parse" })).toBeDisabled();
    expect(screen.getByText("not installed in the workbench's environment")).toBeInTheDocument();
  });
});
