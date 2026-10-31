import { endOfMonth, startOfMonth, startOfQuarter, startOfYear, subDays, subMonths } from "date-fns";

export interface Preset {
  label: string;
  range: (today: Date) => [Date, Date];
}

export const DATE_RANGE_PRESETS: Preset[] = [
  { label: "Today", range: (today) => [today, today] },
  { label: "Last 7 days", range: (today) => [subDays(today, 6), today] },
  { label: "Last 30 days", range: (today) => [subDays(today, 29), today] },
  { label: "This month", range: (today) => [startOfMonth(today), today] },
  { label: "Last month", range: (today) => [startOfMonth(subMonths(today, 1)), endOfMonth(subMonths(today, 1))] },
  { label: "This quarter", range: (today) => [startOfQuarter(today), today] },
  { label: "Year to date", range: (today) => [startOfYear(today), today] },
];
