import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatNumber } from "@/lib/format";

import {
  AXIS_LINE,
  AXIS_TICK,
  CHART_MIN_WIDTH,
  type ChartDatum,
  type ChartSeries,
  GRID_STROKE,
  seriesColor,
  seriesDash,
} from "./chart-theme";
import { ChartFrame } from "./ChartFrame";
import { ChartTooltip } from "./ChartTooltip";

interface ThemedLineChartProps {
  title: string;
  description?: string;
  data: ChartDatum[];
  xKey: string;
  series: ChartSeries[];
  formatValue?: (value: number) => string;
  formatX?: (value: string | number) => string;
  height?: number;
  /** Fill under each line. Use for a single series; several filled series hide each other. */
  area?: boolean;
}

const compact = (value: number) => formatNumber(value, { notation: "compact", maximumFractionDigits: 1 });

export function ThemedLineChart({
  title,
  description,
  data,
  xKey,
  series,
  formatValue = (value) => formatNumber(value),
  formatX,
  height = 240,
  area = false,
}: ThemedLineChartProps) {
  const axes = (
    <>
      <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
      <XAxis dataKey={xKey} tick={AXIS_TICK} axisLine={AXIS_LINE} tickLine={false} tickFormatter={formatX} />
      <YAxis tick={AXIS_TICK} axisLine={false} tickLine={false} width={48} tickFormatter={compact} />
      <Tooltip
        cursor={{ stroke: "var(--border-strong)" }}
        content={<ChartTooltip formatValue={formatValue} formatLabel={formatX} />}
      />
    </>
  );
  const chartProps = { data, margin: { top: 8, right: 12, bottom: 0, left: 0 } };

  return (
    <ChartFrame
      title={title}
      description={description}
      series={series}
      data={data}
      xKey={xKey}
      formatValue={formatValue}
    >
      <ResponsiveContainer width="100%" height={height} initialDimension={{ width: CHART_MIN_WIDTH, height }}>
        {area ? (
          <AreaChart {...chartProps}>
            {axes}
            {series.map((item, index) => (
              <Area
                key={item.key}
                dataKey={item.key}
                name={item.label}
                type="monotone"
                stroke={seriesColor(index)}
                strokeWidth={2}
                strokeDasharray={seriesDash(index)}
                fill={seriesColor(index)}
                fillOpacity={0.14}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        ) : (
          <LineChart {...chartProps}>
            {axes}
            {series.map((item, index) => (
              <Line
                key={item.key}
                dataKey={item.key}
                name={item.label}
                type="monotone"
                stroke={seriesColor(index)}
                strokeWidth={2.5}
                strokeDasharray={seriesDash(index)}
                dot={{ r: 3, fill: seriesColor(index), stroke: "var(--surface)" }}
                activeDot={{ r: 5 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        )}
      </ResponsiveContainer>
    </ChartFrame>
  );
}
