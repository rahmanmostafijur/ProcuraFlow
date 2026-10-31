import { type ReactNode, useId } from "react";

import { cn } from "@/lib/utils";

import { type ChartDatum, type ChartSeries, seriesColor, seriesDash } from "./chart-theme";

interface ChartFrameProps {
  title: string;
  description?: string;
  series: ChartSeries[];
  /** Rows for the visually hidden data table that stands in for the picture. */
  data: ChartDatum[];
  xKey: string;
  xLabel?: string;
  formatValue: (value: number) => string;
  marker?: "line" | "bar";
  /** The chart itself. It is hidden from assistive technology; the table and legend carry the content. */
  children: ReactNode;
  className?: string;
}

function LegendMarker({ index, marker }: { index: number; marker: "line" | "bar" }) {
  const color = seriesColor(index);
  return (
    <svg aria-hidden="true" width="20" height="10" viewBox="0 0 20 10">
      {marker === "bar" ? (
        <rect x="2" y="1" width="16" height="8" rx="2" fill={color} />
      ) : (
        <line x1="1" y1="5" x2="19" y2="5" stroke={color} strokeWidth="3" strokeDasharray={seriesDash(index)} />
      )}
    </svg>
  );
}

/** Title, legend and an accessible data table around a chart. */
export function ChartFrame({
  title,
  description,
  series,
  data,
  xKey,
  xLabel = "Category",
  formatValue,
  marker = "line",
  children,
  className,
}: ChartFrameProps) {
  const captionId = useId();
  return (
    <figure aria-labelledby={captionId} className={cn("space-y-3", className)}>
      <figcaption>
        <p id={captionId} className="text-title text-text-primary">
          {title}
        </p>
        {description && <p className="text-cell text-text-secondary">{description}</p>}
      </figcaption>
      <ul aria-label="Legend" className="flex flex-wrap gap-x-4 gap-y-1 text-cell text-text-secondary">
        {series.map((item, index) => (
          <li key={item.key} className="flex items-center gap-1.5">
            <LegendMarker index={index} marker={marker} />
            {item.label}
          </li>
        ))}
      </ul>
      <div aria-hidden="true">{children}</div>
      <table className="sr-only">
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">{xLabel}</th>
            {series.map((item) => (
              <th key={item.key} scope="col">
                {item.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={String(row[xKey])}>
              <th scope="row">{String(row[xKey])}</th>
              {series.map((item) => (
                <td key={item.key}>{formatValue(Number(row[item.key]))}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
