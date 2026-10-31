import { format, isValid, parse } from "date-fns";
import { CalendarDays } from "lucide-react";
import { useId, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import { CalendarGrid, type DateRange } from "./CalendarGrid";
import { FieldError } from "./FieldError";
import { FOCUS_RING } from "./focus";
import { Input } from "./Input";
import { DATE_RANGE_PRESETS, type Preset } from "./date-range-presets";
import { useDismiss } from "./use-dismiss";

/** ISO calendar dates (yyyy-MM-dd), the same shape the API uses; null means open-ended. */
export interface IsoDateRange {
  start: string | null;
  end: string | null;
}

const ISO = "yyyy-MM-dd";
const toIso = (date: Date) => format(date, ISO);

function parseIso(text: string | null): Date | null {
  if (!text) return null;
  const parsed = parse(text, ISO, new Date());
  return isValid(parsed) && toIso(parsed) === text ? parsed : null;
}

interface DateRangePickerProps {
  value: IsoDateRange;
  onChange: (range: IsoDateRange) => void;
  label?: string;
  /** Injectable "today" so presets are deterministic in tests and screenshots. */
  today?: Date;
  presets?: Preset[];
}

export function DateRangePicker({
  value,
  onChange,
  label = "Date range",
  today = new Date(),
  presets = DATE_RANGE_PRESETS,
}: DateRangePickerProps) {
  const groupId = useId();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<{ start: string; end: string } | null>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  useDismiss(open, () => setOpen(false), popoverRef, triggerRef);

  const start = draft?.start ?? value.start ?? "";
  const end = draft?.end ?? value.end ?? "";
  const startDate = parseIso(start);
  const endDate = parseIso(end);
  const typed = Boolean(start || end);
  const startBad = Boolean(start) && !startDate;
  const endBad = Boolean(end) && !endDate;
  const reversed = Boolean(startDate && endDate && startDate > endDate);
  const error =
    startBad || endBad ? "Use the format YYYY-MM-DD" : reversed ? "The end date is before the start date" : undefined;

  // Commit only complete, valid text; partial typing stays in the draft so the field does not fight the user.
  const edit = (next: { start: string; end: string }) => {
    setDraft(next);
    const s = parseIso(next.start);
    const e = parseIso(next.end);
    const blank = (text: string) => text === "";
    if ((s || blank(next.start)) && (e || blank(next.end)) && !(s && e && s > e)) {
      onChange({ start: s ? toIso(s) : null, end: e ? toIso(e) : null });
      setDraft(null);
    }
  };

  const apply = (range: [Date, Date]) => {
    setDraft(null);
    onChange({ start: toIso(range[0]), end: toIso(range[1]) });
  };

  const pick = (day: Date) => {
    // First pick starts a range; the second ends it (swapped when earlier); a third starts over.
    if (!startDate || endDate) {
      setDraft(null);
      onChange({ start: toIso(day), end: null });
      return;
    }
    const [a, b] = day < startDate ? [day, startDate] : [startDate, day];
    apply([a, b]);
    setOpen(false);
    triggerRef.current?.focus();
  };

  const range: DateRange = { start: startDate, end: endDate };

  return (
    <div role="group" aria-labelledby={groupId} className="space-y-2">
      <p id={groupId} className="text-sm font-medium text-text-primary">
        {label}
      </p>
      <div role="group" aria-label="Quick ranges" className="flex flex-wrap gap-1.5">
        {presets.map((preset) => (
          <button
            key={preset.label}
            type="button"
            onClick={() => apply(preset.range(today))}
            className={cn(
              "rounded-full border border-border-strong px-3 py-1 text-xs font-medium text-text-primary hover:bg-bg max-sm:min-h-11",
              FOCUS_RING,
            )}
          >
            {preset.label}
          </button>
        ))}
      </div>
      <div className="relative flex flex-wrap items-center gap-2">
        <Input
          aria-label={`${label} start`}
          placeholder="YYYY-MM-DD"
          inputMode="numeric"
          value={start}
          aria-invalid={startBad || reversed || undefined}
          onChange={(event) => edit({ start: event.target.value.trim(), end })}
          className="w-36"
        />
        <span aria-hidden="true" className="text-text-secondary">
          to
        </span>
        <Input
          aria-label={`${label} end`}
          placeholder="YYYY-MM-DD"
          inputMode="numeric"
          value={end}
          aria-invalid={endBad || reversed || undefined}
          onChange={(event) => edit({ start, end: event.target.value.trim() })}
          className="w-36"
        />
        <button
          ref={triggerRef}
          type="button"
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-label="Open calendar"
          onClick={() => setOpen((current) => !current)}
          className={cn("rounded-control border border-border-strong p-2 text-text-secondary hover:bg-bg", FOCUS_RING)}
        >
          <CalendarDays aria-hidden="true" className="h-4 w-4" />
        </button>
        {open && (
          <div
            ref={popoverRef}
            role="dialog"
            aria-label="Choose dates"
            className="absolute left-0 top-full z-30 mt-2 rounded-card border border-border bg-surface-raised p-3 shadow-elev-2"
          >
            <CalendarGrid range={range} onPick={pick} initialFocus={startDate ?? today} />
          </div>
        )}
      </div>
      {typed && error && <FieldError>{error}</FieldError>}
    </div>
  );
}
