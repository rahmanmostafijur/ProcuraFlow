import { formatNumber } from "@/lib/format";

/** Plain-language trend for readers who cannot see the line. */
export function summariseTrend(data: number[]): string {
  if (data.length < 2) return "Not enough data for a trend";
  const first = data[0];
  const last = data[data.length - 1];
  const direction = last > first ? "rose" : last < first ? "fell" : "stayed level";
  const range = direction === "stayed level" ? "" : ` from ${formatNumber(first)} to ${formatNumber(last)}`;
  return `Trend ${direction}${range} over ${data.length} periods`;
}
