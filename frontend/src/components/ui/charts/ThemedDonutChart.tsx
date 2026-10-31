import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { formatNumber, formatPercent } from "@/lib/format";

import { CHART_MIN_WIDTH, seriesColor } from "./chart-theme";
import { ChartTooltip } from "./ChartTooltip";

export interface DonutSlice {
  name: string;
  value: number;
}

interface ThemedDonutChartProps {
  title: string;
  description?: string;
  data: DonutSlice[];
  formatValue?: (value: number) => string;
  height?: number;
}

/** Donut with a legend that lists every slice with its value and share, which also serves as the text alternative. */
export function ThemedDonutChart({
  title,
  description,
  data,
  formatValue = (value) => formatNumber(value),
  height = 200,
}: ThemedDonutChartProps) {
  const total = data.reduce((sum, slice) => sum + slice.value, 0);
  return (
    <figure className="space-y-3">
      <figcaption>
        <p className="text-title text-text-primary">{title}</p>
        {description && <p className="text-cell text-text-secondary">{description}</p>}
      </figcaption>
      <div className="flex flex-wrap items-center gap-6">
        <div aria-hidden="true" className="w-48 max-w-full flex-none">
          <ResponsiveContainer width="100%" height={height} initialDimension={{ width: CHART_MIN_WIDTH, height }}>
            <PieChart>
              <Tooltip content={<ChartTooltip formatValue={formatValue} />} />
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius="58%"
                outerRadius="90%"
                stroke="var(--surface)"
                strokeWidth={2}
                isAnimationActive={false}
              >
                {data.map((slice, index) => (
                  <Cell key={slice.name} fill={seriesColor(index)} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <table className="text-cell text-text-primary">
          <caption className="sr-only">{title}</caption>
          <thead className="sr-only">
            <tr>
              <th scope="col">Slice</th>
              <th scope="col">Value</th>
              <th scope="col">Share</th>
            </tr>
          </thead>
          <tbody>
            {data.map((slice, index) => (
              <tr key={slice.name}>
                <th scope="row" className="py-0.5 pr-4 text-left font-normal">
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      aria-hidden="true"
                      className="h-2.5 w-2.5 rounded-sm"
                      style={{ background: seriesColor(index) }}
                    />
                    {slice.name}
                  </span>
                </th>
                <td className="py-0.5 pr-4 text-right font-medium">{formatValue(slice.value)}</td>
                <td className="py-0.5 text-right text-text-secondary">
                  {formatPercent(total ? (slice.value / total) * 100 : 0)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}
