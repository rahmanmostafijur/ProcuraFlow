import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { DateRangePicker, type IsoDateRange } from "./DateRangePicker";

const TODAY = new Date(2026, 9, 15); // Thursday 15 October 2026

function Harness({
  initial = { start: null, end: null },
  onChange,
}: {
  initial?: IsoDateRange;
  onChange?: (r: IsoDateRange) => void;
}) {
  const [range, setRange] = useState<IsoDateRange>(initial);
  return (
    <DateRangePicker
      value={range}
      today={TODAY}
      onChange={(next) => {
        setRange(next);
        onChange?.(next);
      }}
    />
  );
}

describe("DateRangePicker", () => {
  it("applies a preset to both inputs", () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Last 7 days" }));
    expect(onChange).toHaveBeenCalledWith({ start: "2026-10-09", end: "2026-10-15" });
    expect(screen.getByRole("textbox", { name: "Date range start" })).toHaveValue("2026-10-09");
    expect(screen.getByRole("textbox", { name: "Date range end" })).toHaveValue("2026-10-15");
  });

  it("covers this month and last month", () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Last month" }));
    expect(onChange).toHaveBeenLastCalledWith({ start: "2026-09-01", end: "2026-09-30" });
  });

  it("commits typed dates only when valid and explains bad input", () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const start = screen.getByRole("textbox", { name: "Date range start" });
    fireEvent.change(start, { target: { value: "2026-13-40" } });
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("YYYY-MM-DD");
    expect(start).toHaveAttribute("aria-invalid", "true");
    fireEvent.change(start, { target: { value: "2026-10-01" } });
    expect(onChange).toHaveBeenCalledWith({ start: "2026-10-01", end: null });
  });

  it("refuses an end date before the start", () => {
    render(<Harness initial={{ start: "2026-10-10", end: null }} />);
    fireEvent.change(screen.getByRole("textbox", { name: "Date range end" }), { target: { value: "2026-10-01" } });
    expect(screen.getByRole("alert")).toHaveTextContent("before the start");
  });

  it("opens a calendar grid, moves with arrow keys and picks a range", () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const trigger = screen.getByRole("button", { name: "Open calendar" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    const grid = screen.getByRole("grid", { name: "October 2026" });
    const today = screen.getByRole("button", { name: "Thursday 15 October 2026" });
    expect(today).toHaveAttribute("tabindex", "0");
    today.focus();
    fireEvent.keyDown(today, { key: "ArrowRight" });
    expect(screen.getByRole("button", { name: "Friday 16 October 2026" })).toHaveFocus();
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    expect(screen.getByRole("button", { name: "Friday 23 October 2026" })).toHaveFocus();
    fireEvent.keyDown(grid, { key: "PageDown" });
    expect(screen.getByRole("grid", { name: "November 2026" })).toBeInTheDocument();
  });

  it("picks start then end from the grid and closes on Escape with focus back on the trigger", () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const trigger = screen.getByRole("button", { name: "Open calendar" });
    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole("button", { name: "Thursday 15 October 2026" }));
    expect(onChange).toHaveBeenLastCalledWith({ start: "2026-10-15", end: null });
    fireEvent.click(screen.getByRole("button", { name: /Tuesday 20 October 2026/ }));
    expect(onChange).toHaveBeenLastCalledWith({ start: "2026-10-15", end: "2026-10-20" });
    expect(screen.queryByRole("grid")).not.toBeInTheDocument();

    fireEvent.click(trigger);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("grid")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
