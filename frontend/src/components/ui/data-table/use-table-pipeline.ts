import { useMemo } from "react";

import { type Column, type SortState, columnId } from "./types";

function cellText<T>(column: Column<T>, row: T): string {
  if (column.filterValue) return column.filterValue(row);
  const sortValue = column.sortValue?.(row);
  return sortValue === null || sortValue === undefined ? "" : String(sortValue);
}

function compare(a: string | number | null | undefined, b: string | number | null | undefined): number {
  // Empty values sort last in both directions' ascending base order, so "no value" never hides real data.
  if (a === null || a === undefined) return b === null || b === undefined ? 0 : 1;
  if (b === null || b === undefined) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

interface PipelineInput<T> {
  rows: T[];
  columns: Column<T>[];
  filters: Record<string, string>;
  /** Pass null when sorting happens on the server. */
  sort: SortState | null;
}

/** Filter, then sort. Pagination is applied by the caller so it can also run on the server. */
export function useTablePipeline<T>({ rows, columns, filters, sort }: PipelineInput<T>): T[] {
  return useMemo(() => {
    const active = columns.filter((column) => filters[columnId(column)]);
    const filtered = active.length
      ? rows.filter((row) =>
          active.every((column) => {
            const needle = filters[columnId(column)].toLowerCase();
            const text = cellText(column, row).toLowerCase();
            return column.filterOptions ? text === needle : text.includes(needle);
          }),
        )
      : rows;
    const sortColumn = sort && columns.find((column) => columnId(column) === sort.columnId);
    if (!sort || !sortColumn?.sortValue) return filtered;
    const sign = sort.direction === "asc" ? 1 : -1;
    const getValue = sortColumn.sortValue;
    return [...filtered].sort((a, b) => sign * compare(getValue(a), getValue(b)));
  }, [rows, columns, filters, sort]);
}
