import type { VersionChange } from "@/api/types";
import { formatCurrency } from "@/lib/utils";

interface VersionDiffProps {
  changes: VersionChange[];
  currency: string;
}

const EMPTY = "—";

function show(value: string | number | null | undefined): string {
  return value === null || value === undefined || value === "" ? EMPTY : String(value);
}

function money(value: string | undefined, currency: string): string {
  return value === undefined ? EMPTY : formatCurrency(value, currency);
}

function Arrow({ from, to }: { from: string; to: string }) {
  return (
    <span>
      <span className="text-text-secondary line-through">{from}</span> <span aria-hidden="true">→</span>
      <span className="sr-only"> changed to </span> <span className="font-medium text-text-primary">{to}</span>
    </span>
  );
}

function LineSummary({ change, currency }: { change: VersionChange; currency: string }) {
  return (
    <>
      {change.quantity} × {money(change.unit_price, currency)} = {money(change.line_total, currency)}
    </>
  );
}

function ChangeRow({ change, currency }: { change: VersionChange; currency: string }) {
  switch (change.kind) {
    case "field":
      return (
        <>
          <span className="text-text-secondary">{change.label}: </span>
          <Arrow from={show(change.from)} to={show(change.to)} />
        </>
      );
    case "line_added":
      return (
        <>
          <span className="font-medium text-success-fg">Added</span> {change.label}:{" "}
          <LineSummary change={change} currency={currency} />
        </>
      );
    case "line_removed":
      return (
        <>
          <span className="font-medium text-danger-fg">Removed</span> {change.label}:{" "}
          <LineSummary change={change} currency={currency} />
        </>
      );
    case "line_changed":
      return (
        <>
          <span className="font-medium text-text-primary">Changed</span> {change.label}
          <ul className="ml-4 list-disc">
            {change.changes?.map((item) => (
              <li key={item.field}>
                {item.label}: <Arrow from={show(item.from)} to={show(item.to)} />
              </li>
            ))}
            <li>
              Line total: <Arrow from={money(change.from_total, currency)} to={money(change.to_total, currency)} />
            </li>
          </ul>
        </>
      );
    case "total":
      return (
        <>
          <span className="font-semibold text-text-primary">{change.label}: </span>
          <Arrow from={money(String(change.from ?? ""), currency)} to={money(String(change.to ?? ""), currency)} />
        </>
      );
  }
}

/** What changed from the version before, one readable line per field, line item or total. */
export function VersionDiff({ changes, currency }: VersionDiffProps) {
  if (changes.length === 0) return <p className="text-sm text-text-secondary">No changes from the version before.</p>;
  return (
    <ul className="space-y-1 text-sm text-text-secondary">
      {changes.map((change, index) => (
        <li key={`${change.kind}-${change.label}-${index}`}>
          <ChangeRow change={change} currency={currency} />
        </li>
      ))}
    </ul>
  );
}
