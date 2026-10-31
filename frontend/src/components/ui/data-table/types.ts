import type { ReactNode } from "react";

export type SortDirection = "asc" | "desc";
export interface SortState {
  columnId: string;
  direction: SortDirection;
}
export type Density = "comfortable" | "compact";
export type RowKey = string | number;

export interface FilterOption {
  value: string;
  label: string;
}

/** Legacy columns (header, accessor, className) are valid; every other field is optional. */
export interface Column<T> {
  header: string;
  accessor: (row: T) => ReactNode;
  className?: string;
  /** Stable id for sort, filter and visibility state. Defaults to the header text. */
  id?: string;
  /** Amounts: right-aligned with tabular numerals. */
  isAmount?: boolean;
  /** Sorts client-side by this value, or just marks the column sortable when sorting is server-side. */
  sortValue?: (row: T) => string | number | null | undefined;
  sortable?: boolean;
  /** A text box, or a select when `filterOptions` is given. Matching uses `filterValue`, else the sort value. */
  filterable?: boolean;
  filterOptions?: FilterOption[];
  filterValue?: (row: T) => string;
  /** Columns that cannot be hidden from the column menu (the identifying column). */
  alwaysVisible?: boolean;
  defaultHidden?: boolean;
}

export const columnId = <T>(column: Column<T>): string => column.id ?? column.header;
export const isSortable = <T>(column: Column<T>): boolean => column.sortable ?? column.sortValue !== undefined;
