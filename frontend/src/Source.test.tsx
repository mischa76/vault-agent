import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SourceSection } from "./components/Source";
import type { SourceView } from "./types";

// WP119 (C46) G5: the source section — state from the API, the schema choice from the catalogue,
// the catalogue read and the profile posted as chosen, the row read confirmed before it is asked.
vi.mock("./api", () => ({
  ApiError: class extends Error {},
  api: {
    source: vi.fn(),
    sourceTables: vi.fn(async () => [{ schema: "Sales", table: "Customer" }, { schema: "Sales", table: "Store" }]),
    readCatalogue: vi.fn(async () => ({
      file: { kind: "schema", name: "source_schema.yml", bytes: 10 }, command: "vault-agent source-schema --schema Sales --out inputs/source_schema.yml",
      warnings: [], summary: { tables: 2, columns: 7, comments: 0, foreign_keys: 1 },
    })),
    makeProfile: vi.fn(async () => ({
      file: { kind: "profiling", name: "profiling.yml", bytes: 10 }, command: "vault-agent profile --schema Sales --out inputs/profiling.yml",
      refused: [], summary: { tables: 1, columns: 3, rows: 5, checks: ["range", "lengths", "patterns"] },
    })),
  },
}));
import { api } from "./api";

const ok: SourceView = { state: "ok", url: "postgresql+psycopg2://reader:***@db.local/aw", dialect: "postgresql", schemas: ["Person", "Sales"] };

afterEach(() => vi.clearAllMocks());

describe("Source (WP119)", () => {
  it("says the source is not set and offers nothing to press", async () => {
    vi.mocked(api.source).mockResolvedValue({ state: "unset", url: null, dialect: null, schemas: [] } satisfies SourceView);
    render(<SourceSection projectId="stores" onChanged={() => undefined} busy={false} />);
    expect(await screen.findByText("source: not set")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "read catalogue" })).toBeNull();
  });

  it("reads the catalogue of the chosen schemas", async () => {
    vi.mocked(api.source).mockResolvedValue(ok);
    const onChanged = vi.fn();
    render(<SourceSection projectId="stores" onChanged={onChanged} busy={false} />);
    const read = await screen.findByRole("button", { name: "read catalogue" });
    expect(read).toBeDisabled();
    fireEvent.click(screen.getByLabelText("schema Sales"));
    fireEvent.click(read);
    await screen.findByText(/metadata only$/);
    expect(api.readCatalogue).toHaveBeenCalledWith("stores", { schemas: ["Sales"], views: false });
    expect(onChanged).toHaveBeenCalled();
    expect(screen.getByText(/\$ vault-agent source-schema --schema Sales/)).toBeInTheDocument();
  });

  it("asks before the row read and sends the acknowledgement with the choice", async () => {
    vi.mocked(api.source).mockResolvedValue(ok);
    render(<SourceSection projectId="stores" onChanged={() => undefined} busy={false} />);
    fireEvent.click(await screen.findByLabelText("schema Sales"));
    fireEvent.click(await screen.findByLabelText("table Sales.Customer"));
    fireEvent.click(screen.getByLabelText("check patterns"));
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    fireEvent.click(screen.getByRole("button", { name: "make profile" }));
    expect(api.makeProfile).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "make profile" }));
    await waitFor(() => expect(api.makeProfile).toHaveBeenCalledWith("stores", {
      schemas: ["Sales"], tables: ["Sales.Customer"], checks: ["range", "lengths"], sample: 10000,
      examples: 0, reads_rows: true,
    }));
    expect(confirm.mock.calls[1]?.[0]).toMatch(/reads rows/);
  });
});

// WP119 follow-up (2026-11-07, C50 option c): the API took a file name, the section never sent one,
// so every read landed on `source_schema.yml` / `profiling.yml` and replaced an earlier steps input.

// WP119 follow-up (2026-11-07, C50 option c): the API took a file name, the section never sent one,
// so every read landed on `source_schema.yml` / `profiling.yml` and replaced an earlier step's input.
describe("Source — file names per schema choice (WP119 follow-up)", () => {
  it("names the files after the chosen schemas and sends the names", async () => {
    vi.mocked(api.source).mockResolvedValue(ok);
    render(<SourceSection projectId="stores" onChanged={() => undefined} busy={false} />);
    fireEvent.click(await screen.findByLabelText("schema Sales"));
    expect(screen.getByLabelText("catalogue file name")).toHaveValue("sales_source_schema.yml");
    expect(screen.getByLabelText("profile file name")).toHaveValue("sales_profiling.yml");
    fireEvent.click(screen.getByLabelText("schema Person"));
    expect(screen.getByLabelText("catalogue file name")).toHaveValue("sales_person_source_schema.yml");
    fireEvent.click(screen.getByRole("button", { name: "read catalogue" }));
    await waitFor(() => expect(api.readCatalogue).toHaveBeenCalledWith("stores",
      { schemas: ["Sales", "Person"], views: false, name: "sales_person_source_schema.yml" }));
    vi.spyOn(window, "confirm").mockReturnValueOnce(true);
    fireEvent.click(screen.getByRole("button", { name: "make profile" }));
    await waitFor(() => expect(api.makeProfile).toHaveBeenCalledWith("stores", expect.objectContaining({ name: "sales_person_profiling.yml" })));
  });

  it("keeps a name the operator typed when the schema choice changes", async () => {
    vi.mocked(api.source).mockResolvedValue(ok);
    render(<SourceSection projectId="stores" onChanged={() => undefined} busy={false} />);
    fireEvent.click(await screen.findByLabelText("schema Sales"));
    fireEvent.change(screen.getByLabelText("catalogue file name"), { target: { value: "step3.yml" } });
    fireEvent.click(screen.getByLabelText("schema Person"));
    expect(screen.getByLabelText("catalogue file name")).toHaveValue("step3.yml");
    fireEvent.click(screen.getByRole("button", { name: "read catalogue" }));
    await waitFor(() => expect(api.readCatalogue).toHaveBeenCalledWith("stores",
      { schemas: ["Sales", "Person"], views: false, name: "step3.yml" }));
  });
});
