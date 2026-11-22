import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Console } from "./components/Console";
import type { ConsoleEntry } from "./types";

const entries: ConsoleEntry[] = [{
  question: "what if accept",
  answer: { text: "That would be:\n  vault-agent resume --out /x --accept\nNothing ran.", kind: "answer",
    refs: [{ perspective: "review", label: "open Review" }], command: "vault-agent resume --out /x --accept" },
}];

describe("Console", () => {
  it("renders the transcript, offers the answer's refs, and submits a question", () => {
    const onAsk = vi.fn(), onNavigate = vi.fn();
    render(<Console entries={entries} onAsk={onAsk} onNavigate={onNavigate} busy={false} enabled />);
    expect(screen.getByText("› what if accept")).toBeInTheDocument();
    expect(screen.getByText(/vault-agent resume --out \/x --accept/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "open Review" }));
    expect(onNavigate).toHaveBeenCalledWith("review");
    const input = screen.getByLabelText("console input");
    fireEvent.change(input, { target: { value: "items" } });
    fireEvent.submit(input.closest("form")!);
    expect(onAsk).toHaveBeenCalledWith("items");
    expect(input).toHaveValue("");
  });
  it("is disabled without a run", () => {
    render(<Console entries={[]} onAsk={() => undefined} onNavigate={() => undefined} busy={false} enabled={false} />);
    expect(screen.getByLabelText("console input")).toBeDisabled();
  });
});
