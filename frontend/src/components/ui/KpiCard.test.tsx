import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { KpiCard } from "./KpiCard";
import { Sparkline } from "./Sparkline";
import { summariseTrend } from "./trend-summary";

describe("Sparkline", () => {
  it("summarises the trend for assistive technology", () => {
    render(<Sparkline data={[10, 12, 20]} />);
    expect(screen.getByRole("img", { name: "Trend rose from 10 to 20 over 3 periods" })).toBeInTheDocument();
  });

  it("handles flat, falling and too-short series", () => {
    expect(summariseTrend([5, 5, 5])).toBe("Trend stayed level over 3 periods");
    expect(summariseTrend([9, 3])).toBe("Trend fell from 9 to 3 over 2 periods");
    expect(summariseTrend([1])).toBe("Not enough data for a trend");
  });

  it("takes a custom label and draws in a token colour", () => {
    const { container } = render(<Sparkline data={[1, 2]} ariaLabel="Spend per week" />);
    expect(screen.getByRole("img", { name: "Spend per week" })).toHaveClass("text-brand");
    expect(container.querySelector("polyline")).toHaveAttribute("stroke", "currentColor");
  });
});

describe("KpiCard", () => {
  it("shows the figure, the exact value for readers and a favourable delta in words", () => {
    render(
      <KpiCard label="Spend" value="$1.3M" exactValue="$1,284,000.00" delta={-4.2} goodWhen="down" trend={[3, 2, 1]} />,
    );
    expect(screen.getByText("$1.3M")).toHaveAttribute("data-kpi");
    expect(screen.getByText(/\$1,284,000.00/)).toBeInTheDocument();
    expect(screen.getByText(/down 4.2% versus previous period, favourable/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Spend: falling over 3 periods/ })).toBeInTheDocument();
  });

  it("calls an unwanted change unfavourable and a zero change unchanged", () => {
    const { rerender } = render(<KpiCard label="Approvals" value="12" delta={-10} />);
    expect(screen.getByText(/unfavourable/)).toBeInTheDocument();
    rerender(<KpiCard label="Approvals" value="12" delta={0} />);
    expect(screen.getByText(/unchanged/)).toBeInTheDocument();
  });

  it("shows a loading skeleton with a status message", () => {
    render(<KpiCard label="Spend" value="x" isLoading />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading Spend");
    expect(screen.queryByText("x")).not.toBeInTheDocument();
  });
});
