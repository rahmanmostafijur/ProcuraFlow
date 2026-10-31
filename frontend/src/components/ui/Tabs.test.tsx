import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Tabs } from "./Tabs";

const TABS = [
  { id: "overview", label: "Overview", content: <p>Overview body</p> },
  { id: "lines", label: "Lines", content: <p>Lines body</p>, badge: 3 },
  { id: "locked", label: "Locked", content: <p>Locked body</p>, disabled: true },
  { id: "history", label: "History", content: <p>History body</p> },
];

describe("Tabs", () => {
  it("wires tablist, tabs and the active panel together with a roving tabindex", () => {
    render(<Tabs label="Order sections" tabs={TABS} />);
    expect(screen.getByRole("tablist", { name: "Order sections" })).toBeInTheDocument();
    const overview = screen.getByRole("tab", { name: "Overview" });
    expect(overview).toHaveAttribute("aria-selected", "true");
    expect(overview).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tab", { name: /Lines/ })).toHaveAttribute("tabindex", "-1");
    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveAccessibleName("Overview");
    expect(overview).toHaveAttribute("aria-controls", panel.id);
  });

  it("moves selection and focus with the arrow keys, skipping disabled tabs and wrapping", () => {
    const onChange = vi.fn();
    render(<Tabs label="Sections" tabs={TABS} onChange={onChange} />);
    fireEvent.keyDown(screen.getByRole("tab", { name: "Overview" }), { key: "ArrowRight" });
    const lines = screen.getByRole("tab", { name: /Lines/ });
    expect(lines).toHaveAttribute("aria-selected", "true");
    expect(lines).toHaveFocus();
    expect(screen.getByText("Lines body")).toBeInTheDocument();
    fireEvent.keyDown(lines, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "History" })).toHaveFocus();
    fireEvent.keyDown(screen.getByRole("tab", { name: "History" }), { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveFocus();
    fireEvent.keyDown(screen.getByRole("tab", { name: "Overview" }), { key: "ArrowLeft" });
    expect(screen.getByRole("tab", { name: "History" })).toHaveFocus();
    expect(onChange).toHaveBeenLastCalledWith("history");
  });

  it("jumps to the first and last tab with Home and End", () => {
    render(<Tabs label="Sections" tabs={TABS} defaultValue="lines" />);
    fireEvent.keyDown(screen.getByRole("tab", { name: /Lines/ }), { key: "End" });
    expect(screen.getByRole("tab", { name: "History" })).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(screen.getByRole("tab", { name: "History" }), { key: "Home" });
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
  });

  it("uses Up and Down when vertical and ignores the horizontal keys", () => {
    render(<Tabs label="Sections" tabs={TABS} orientation="vertical" />);
    const overview = screen.getByRole("tab", { name: "Overview" });
    fireEvent.keyDown(overview, { key: "ArrowRight" });
    expect(overview).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(overview, { key: "ArrowDown" });
    expect(screen.getByRole("tab", { name: /Lines/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tablist")).toHaveAttribute("aria-orientation", "vertical");
  });

  it("selects on click and never selects a disabled tab", () => {
    render(<Tabs label="Sections" tabs={TABS} />);
    fireEvent.click(screen.getByRole("tab", { name: "Locked" }));
    expect(screen.getByRole("tab", { name: "Locked" })).toBeDisabled();
    expect(screen.queryByText("Locked body")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "History" }));
    expect(screen.getByText("History body")).toBeInTheDocument();
  });
});
