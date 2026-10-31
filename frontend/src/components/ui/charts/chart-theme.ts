/** Series colours are CSS variables (src/styles/chart-tokens.css), so a chart repaints when the theme changes. */
export const SERIES_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
] as const;

/** Line series differ by dash as well as colour, so they stay distinguishable without colour vision. */
export const SERIES_DASHES: Array<string | undefined> = [undefined, "7 4", "2 4", "9 4 2 4", "4 2", "12 4"];

export const AXIS_TICK = { fill: "var(--text-secondary)", fontSize: 12 } as const;
export const AXIS_LINE = { stroke: "var(--border-strong)" } as const;
export const GRID_STROKE = "var(--border)";
export const CHART_MIN_WIDTH = 320;

export interface ChartSeries {
  key: string;
  label: string;
}

export type ChartDatum = Record<string, string | number>;

export const seriesColor = (index: number): string => SERIES_COLORS[index % SERIES_COLORS.length];
export const seriesDash = (index: number): string | undefined => SERIES_DASHES[index % SERIES_DASHES.length];
