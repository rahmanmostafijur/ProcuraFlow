import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DiffViewer } from "./DiffViewer";
import { diffLines } from "./diff-lines";

describe("diffLines", () => {
  it("marks added, removed and unchanged lines in order", () => {
    expect(diffLines("a\nb\nc", "a\nx\nc\nd")).toEqual([
      { kind: "same", text: "a" },
      { kind: "removed", text: "b" },
      { kind: "added", text: "x" },
      { kind: "same", text: "c" },
      { kind: "added", text: "d" },
    ]);
  });

  it("handles empty sides", () => {
    expect(diffLines("", "a")).toEqual([{ kind: "added", text: "a" }]);
    expect(diffLines("a", "")).toEqual([{ kind: "removed", text: "a" }]);
    expect(diffLines("", "")).toEqual([]);
  });
});

describe("DiffViewer", () => {
  it("shows field changes as a table with + and − markers and spoken words", () => {
    render(
      <DiffViewer
        label="Supplier changes"
        changes={[
          { field: "Payment terms", before: "Net 30", after: "Net 45" },
          { field: "Email", before: null, after: "ap@acme.test" },
        ]}
      />,
    );
    const group = screen.getByRole("group", { name: "Supplier changes" });
    const row = within(group).getByRole("row", { name: /Payment terms/ });
    expect(within(row).getByText("Net 30").tagName).toBe("DEL");
    expect(within(row).getByText("Net 45").tagName).toBe("INS");
    expect(within(row).getByText("Removed:", { exact: false })).toBeInTheDocument();
    expect(within(row).getByText("Added:", { exact: false })).toBeInTheDocument();
    expect(row.textContent).toContain("+");
    expect(row.textContent).toContain("−");
    expect(within(group).getByRole("row", { name: /Email/ })).toHaveTextContent("—");
  });

  it("shows a text diff with a sign and a word on every changed line", () => {
    render(<DiffViewer before={"Deliver to dock 2\nCall ahead"} after={"Deliver to dock 4\nCall ahead"} />);
    const group = screen.getByRole("group", { name: "Changes" });
    expect(group).toHaveTextContent("−");
    expect(group).toHaveTextContent("+");
    expect(within(group).getByText("Removed:", { exact: false })).toBeInTheDocument();
    expect(within(group).getByText("Added:", { exact: false })).toBeInTheDocument();
    expect(within(group).getByText("Unchanged:", { exact: false })).toBeInTheDocument();
  });
});
