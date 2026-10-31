interface TooltipPayloadItem {
  name?: string | number;
  value?: string | number | readonly (string | number)[];
  color?: string;
  stroke?: string;
  fill?: string;
}

interface ChartTooltipProps {
  // Recharts injects these when it renders the element passed as `content`.
  active?: boolean;
  payload?: readonly TooltipPayloadItem[];
  label?: string | number;
  formatValue: (value: number) => string;
  formatLabel?: (label: string | number) => string;
}

/** Tooltip card: each row has a colour chip, the series name and the value, so colour is never the only key. */
export function ChartTooltip({ active, payload, label, formatValue, formatLabel }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-card border border-border bg-surface-raised px-3 py-2 text-cell text-text-primary shadow-elev-2">
      {label !== undefined && <p className="mb-1 font-semibold">{formatLabel ? formatLabel(label) : String(label)}</p>}
      <ul className="space-y-0.5">
        {payload.map((item, index) => (
          <li key={`${item.name}-${index}`} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className="h-2.5 w-2.5 rounded-sm"
                style={{ background: item.color ?? item.stroke ?? item.fill }}
              />
              {item.name}
            </span>
            <span className="tabular font-medium">{formatValue(Number(item.value))}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
