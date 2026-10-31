import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatNumber } from "@/lib/format";

import {
  AXIS_LINE,
  AXIS_TICK,
  CHART_MIN_WIDTH,
  type ChartDatum,
  type ChartSeries,
  GRID_STROKE,
  seriesColor,
} from "./chart-theme";
import { ChartFrame } from "./ChartFrame";
import { ChartTooltip } from "./ChartTooltip";

interface ThemedBarChartProps {
  title: string;
  description?: string;
  data: ChartDatum[];
  xKey: string;
  series: ChartSeries[];
  formatValue?: (value: number) => string;
  height?: number;
  stacked?: boolean;
}

const compact = (value: number) => formatNumber(value, { notation: "compact", maximumFractionDigits: 1 });

export function ThemedBarChart({
  title,
  description,
  data,
  xKey,
  series,
  formatValue = (value) => formatNumber(value),
  height = 240,
  stacked = false,
}: ThemedBarChartProps) {
  return (
    <ChartFrame
      title={title}
      description={description}
      series={series}
      data={data}
      xKey={xKey}
      formatValue={formatValue}
      marker="bar"
    >
      <ResponsiveContainer width="100%" height={height} initialDimension={{ width: CHART_MIN_WIDTH, height }}>
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey={xKey} tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} />
          <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={48} tickFormatter={compact} />
          <Tooltip cursor={{ fill: "var(--brand-subtle)" }} content={<ChartTooltip formatValue={formatValue} />} />
          {series.map((item, index) => (
            <Bar
              key={item.key}
              dataKey={item.key}
              name={item.label}
              fill={seriesColor(index)}
              stackId={stacked ? "stack" : undefined}
              // A surface-coloured edge separates touching bars and stacked segments by shape, not just hue.
              stroke="var(--surface)"
              strokeWidth={1}
              radius={stacked ? 0 : [4, 4, 0, 0]}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
