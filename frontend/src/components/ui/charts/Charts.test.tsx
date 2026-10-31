import { render, screen, within } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";

import { ChartTooltip } from "./ChartTooltip";
import { SERIES_COLORS, seriesColor, seriesDash } from "./chart-theme";
import { ThemedBarChart } from "./ThemedBarChart";
import { ThemedDonutChart } from "./ThemedDonutChart";
import { ThemedLineChart } from "./ThemedLineChart";

const DATA = [
  { month: "Jan", spend: 1200, budget: 1500 },
  { month: "Feb", spend: 1800, budget: 1500 },
];
const SERIES = [
  { key: "spend", label: "Spend" },
  { key: "budget", label: "Budget" },
];

beforeAll(() => {
  // jsdom has no ResizeObserver, which recharts' ResponsiveContainer needs.
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

describe("themed charts", () => {
  it("names the figure and gives screen readers a data table", () => {
    render(<ThemedLineChart title="Spend by month" data={DATA} xKey="month" series={SERIES} />);
    expect(screen.getByRole("figure", { name: "Spend by month" })).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Spend by month" });
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((cell) => cell.textContent),
    ).toEqual(["Category", "Spend", "Budget"]);
    expect(within(table).getByRole("row", { name: /Feb/ })).toHaveTextContent("1,800");
  });

  it("hides the drawn chart from assistive technology and lists series in a legend", () => {
    const { container } = render(<ThemedBarChart title="Orders" data={DATA} xKey="month" series={SERIES} stacked />);
    expect(container.querySelector('[aria-hidden="true"] .recharts-responsive-container')).not.toBeNull();
    const legend = screen.getByRole("list", { name: "Legend" });
    expect(within(legend).getAllByRole("listitem")).toHaveLength(2);
  });

  it("formats table values with the supplied formatter", () => {
    render(
      <ThemedLineChart title="Spend" data={DATA} xKey="month" series={[SERIES[0]]} formatValue={(v) => `$${v}`} area />,
    );
    expect(screen.getByRole("cell", { name: "$1200" })).toBeInTheDocument();
  });

  it("lists every donut slice with its value and share", () => {
    render(
      <ThemedDonutChart
        title="By category"
        data={[
          { name: "Office", value: 75 },
          { name: "IT", value: 25 },
        ]}
      />,
    );
    const row = screen.getByRole("row", { name: /Office/ });
    expect(row).toHaveTextContent("75");
    expect(row).toHaveTextContent("75.0%");
  });
});

describe("chart theme and tooltip", () => {
  it("takes series colours from CSS variables and varies the dash", () => {
    expect(seriesColor(0)).toBe("var(--chart-1)");
    expect(seriesColor(SERIES_COLORS.length)).toBe("var(--chart-1)");
    expect(seriesDash(0)).toBeUndefined();
    expect(seriesDash(1)).toBeDefined();
  });

  it("renders a labelled row per series and nothing when inactive", () => {
    const payload = [{ name: "Spend", value: 5, color: "var(--chart-1)" }];
    const { container, rerender } = render(
      <ChartTooltip active payload={payload} label="Jan" formatValue={(v) => `#${v}`} />,
    );
    expect(screen.getByText("Jan")).toBeInTheDocument();
    expect(screen.getByText("Spend")).toBeInTheDocument();
    expect(screen.getByText("#5")).toBeInTheDocument();
    rerender(<ChartTooltip active={false} payload={payload} formatValue={String} />);
    expect(container).toBeEmptyDOMElement();
  });
});
