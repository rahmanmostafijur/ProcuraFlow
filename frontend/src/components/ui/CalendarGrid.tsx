import {
  addDays,
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameDay,
  isSameMonth,
  startOfMonth,
  startOfWeek,
} from "date-fns";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import { FOCUS_RING } from "./focus";

export interface DateRange {
  start: Date | null;
  end: Date | null;
}

interface CalendarGridProps {
  range: DateRange;
  onPick: (day: Date) => void;
  /** The day that has the roving tab stop when the grid opens. */
  initialFocus: Date;
}

const WEEK = { weekStartsOn: 1 } as const;
const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function isInRange(day: Date, { start, end }: DateRange): boolean {
  return Boolean(start && end && day >= start && day <= end);
}

/**
 * A month grid with a roving tabindex: Tab enters once, arrows move a day or a week, PageUp/PageDown change month,
 * Home/End jump to the week's ends, Enter or Space picks. Range ends are filled and carry a text label for readers.
 */
export function CalendarGrid({ range, onPick, initialFocus }: CalendarGridProps) {
  const [focused, setFocused] = useState(initialFocus);
  const gridRef = useRef<HTMLTableElement>(null);
  const shouldFocus = useRef(false);

  useEffect(() => {
    if (!shouldFocus.current) return;
    shouldFocus.current = false;
    gridRef.current?.querySelector<HTMLElement>('button[tabindex="0"]')?.focus();
  }, [focused]);

  const moveTo = (day: Date) => {
    shouldFocus.current = true;
    setFocused(day);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTableElement>) => {
    const steps: Record<string, Date | undefined> = {
      ArrowLeft: addDays(focused, -1),
      ArrowRight: addDays(focused, 1),
      ArrowUp: addDays(focused, -7),
      ArrowDown: addDays(focused, 7),
      PageUp: addMonths(focused, -1),
      PageDown: addMonths(focused, 1),
      Home: startOfWeek(focused, WEEK),
      End: endOfWeek(focused, WEEK),
    };
    const next = steps[event.key];
    if (!next) return;
    event.preventDefault();
    moveTo(next);
  };

  const days = eachDayOfInterval({
    start: startOfWeek(startOfMonth(focused), WEEK),
    end: endOfWeek(endOfMonth(focused), WEEK),
  });
  const weeks = Array.from({ length: days.length / 7 }, (_, index) => days.slice(index * 7, index * 7 + 7));
  const monthLabel = format(focused, "MMMM yyyy");

  return (
    <div className="w-72">
      <div className="mb-2 flex items-center justify-between">
        <button
          type="button"
          aria-label="Previous month"
          onClick={() => setFocused(addMonths(focused, -1))}
          className={cn("rounded-control p-1.5 text-text-secondary hover:bg-bg", FOCUS_RING)}
        >
          <ChevronLeft aria-hidden="true" className="h-4 w-4" />
        </button>
        <p aria-live="polite" className="text-sm font-semibold text-text-primary">
          {monthLabel}
        </p>
        <button
          type="button"
          aria-label="Next month"
          onClick={() => setFocused(addMonths(focused, 1))}
          className={cn("rounded-control p-1.5 text-text-secondary hover:bg-bg", FOCUS_RING)}
        >
          <ChevronRight aria-hidden="true" className="h-4 w-4" />
        </button>
      </div>
      <table ref={gridRef} role="grid" aria-label={monthLabel} onKeyDown={onKeyDown} className="w-full border-collapse">
        <thead>
          <tr>
            {WEEKDAYS.map((name) => (
              <th key={name} scope="col" className="pb-1 text-center text-xs font-semibold text-text-secondary">
                <abbr title={name} className="no-underline">
                  {name.slice(0, 2)}
                </abbr>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {weeks.map((week) => (
            <tr key={week[0].toISOString()}>
              {week.map((day) => {
                const isStart = Boolean(range.start && isSameDay(day, range.start));
                const isEnd = Boolean(range.end && isSameDay(day, range.end));
                const selected = isStart || isEnd;
                const inRange = isInRange(day, range);
                return (
                  <td
                    key={day.toISOString()}
                    role="gridcell"
                    aria-selected={selected || inRange}
                    className="p-0 text-center"
                  >
                    <button
                      type="button"
                      tabIndex={isSameDay(day, focused) ? 0 : -1}
                      aria-label={format(day, "EEEE d MMMM yyyy")}
                      onClick={() => onPick(day)}
                      className={cn(
                        "h-9 w-9 text-sm",
                        FOCUS_RING,
                        selected
                          ? "rounded-control bg-brand font-semibold text-on-brand"
                          : inRange
                            ? "bg-brand-subtle text-brand-subtle-fg"
                            : "rounded-control text-text-primary hover:bg-bg",
                        !isSameMonth(day, focused) && !selected && "text-text-secondary opacity-70",
                      )}
                    >
                      {format(day, "d")}
                      {isStart && <span className="sr-only"> (range start)</span>}
                      {isEnd && <span className="sr-only"> (range end)</span>}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
