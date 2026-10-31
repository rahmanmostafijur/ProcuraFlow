import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";

import { cn } from "@/lib/utils";

import { Checkbox } from "../Checkbox";
import { FOCUS_RING } from "../focus";
import { Input } from "../Input";
import { Select } from "../Select";
import { type Column, type SortState, columnId, isSortable } from "./types";

interface HeadProps<T> {
  columns: Column<T>[];
  sort: SortState | null;
  onSort: (columnId: string) => void;
  filters: Record<string, string>;
  onFilter: (columnId: string, value: string) => void;
  sticky: boolean;
  selectable: boolean;
  allSelected: boolean;
  someSelected: boolean;
  onToggleAll: () => void;
  cellPadding: string;
}

export function DataTableHead<T>({
  columns,
  sort,
  onSort,
  filters,
  onFilter,
  sticky,
  selectable,
  allSelected,
  someSelected,
  onToggleAll,
  cellPadding,
}: HeadProps<T>) {
  const th = cn(
    "bg-bg text-left text-caption uppercase text-text-secondary",
    cellPadding,
    sticky && "sticky top-0 z-10",
  );
  const hasFilters = columns.some((column) => column.filterable);

  return (
    <thead>
      <tr>
        {selectable && (
          <th scope="col" className={cn(th, "w-10")}>
            <Checkbox
              aria-label="Select all rows"
              checked={allSelected}
              indeterminate={someSelected && !allSelected}
              onChange={onToggleAll}
            />
          </th>
        )}
        {columns.map((column) => {
          const id = columnId(column);
          const isActive = sort?.columnId === id;
          const ariaSort = isSortable(column)
            ? isActive
              ? sort.direction === "asc"
                ? "ascending"
                : "descending"
              : "none"
            : undefined;
          return (
            <th key={id} scope="col" aria-sort={ariaSort} className={cn(th, column.isAmount && "text-right")}>
              {isSortable(column) ? (
                <button
                  type="button"
                  onClick={() => onSort(id)}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-control uppercase hover:text-text-primary",
                    column.isAmount && "flex-row-reverse",
                    FOCUS_RING,
                  )}
                >
                  {column.header}
                  {/* The arrow shape shows direction; aria-sort carries it for assistive technology. */}
                  {isActive ? (
                    sort.direction === "asc" ? (
                      <ArrowUp aria-hidden="true" className="h-3.5 w-3.5" />
                    ) : (
                      <ArrowDown aria-hidden="true" className="h-3.5 w-3.5" />
                    )
                  ) : (
                    <ChevronsUpDown aria-hidden="true" className="h-3.5 w-3.5 opacity-60" />
                  )}
                </button>
              ) : (
                column.header
              )}
            </th>
          );
        })}
      </tr>
      {hasFilters && (
        <tr>
          {selectable && <td className="bg-surface" />}
          {columns.map((column) => {
            const id = columnId(column);
            return (
              <td key={id} className="bg-surface px-4 py-2 font-normal normal-case">
                {column.filterable &&
                  (column.filterOptions ? (
                    <Select
                      aria-label={`Filter ${column.header}`}
                      value={filters[id] ?? ""}
                      onChange={(event) => onFilter(id, event.target.value)}
                    >
                      <option value="">All</option>
                      {column.filterOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <Input
                      aria-label={`Filter ${column.header}`}
                      placeholder="Filter…"
                      value={filters[id] ?? ""}
                      onChange={(event) => onFilter(id, event.target.value)}
                    />
                  ))}
              </td>
            );
          })}
        </tr>
      )}
    </thead>
  );
}
