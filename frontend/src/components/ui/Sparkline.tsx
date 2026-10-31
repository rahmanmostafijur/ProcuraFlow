import { cn } from "@/lib/utils";

import { summariseTrend } from "./trend-summary";

interface SparklineProps {
  data: number[];
  /** Overrides the generated summary (use it when the series has a meaning, like "Spend per week"). */
  ariaLabel?: string;
  width?: number;
  height?: number;
  className?: string;
}

/** Tiny line chart. It draws in currentColor, so the colour comes from a text token class (default brand). */
export function Sparkline({ data, ariaLabel, width = 96, height = 32, className }: SparklineProps) {
  const label = ariaLabel ?? summariseTrend(data);
  if (data.length < 2) {
    return <span role="img" aria-label={label} className={cn("inline-block", className)} style={{ width, height }} />;
  }
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const pad = 2;
  const points = data.map((value, index) => {
    const x = pad + (index * (width - pad * 2)) / (data.length - 1);
    const y = height - pad - ((value - min) / span) * (height - pad * 2);
    return [x, y] as const;
  });
  const line = points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${pad},${height - pad} ${line} ${width - pad},${height - pad}`;
  const [lastX, lastY] = points[points.length - 1];

  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      className={cn("text-brand", className)}
    >
      <polygon points={area} fill="currentColor" opacity={0.12} />
      <polyline
        points={line}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={lastX} cy={lastY} r={2.5} fill="currentColor" />
    </svg>
  );
}
