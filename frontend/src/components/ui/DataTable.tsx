import { type KeyboardEvent, type ReactNode, useMemo, useState } from "react";

import { cn } from "@/lib/utils";

import { Button } from "./Button";
import { Checkbox } from "./Checkbox";
import { DataTableHead } from "./data-table/DataTableHead";
import { DataTableToolbar } from "./data-table/DataTableToolbar";
import { type Column, type Density, type RowKey, type SortState, columnId } from "./data-table/types";
import { useTablePipeline } from "./data-table/use-table-pipeline";
import { EmptyState, type IllustrationName } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { FOCUS_RING } from "./focus";
import { Pagination } from "./Pagination";
import { Skeleton } from "./Skeleton";
import { VisuallyHidden } from "./VisuallyHidden";

// Re-exported so existing `import { DataTable, type Column }` call sites keep working.
export type { Column, Density, RowKey, SortState } from "./data-table/types";

interface ServerPagination {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  keyExtractor: (row: T) => RowKey;
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  emptyIllustration?: IllustrationName;
  onRowClick?: (row: T) => void;
  /** Accessible name of the table; also names the scrollable region. */
  caption?: string;
  selectable?: boolean;
  selectedKeys?: ReadonlySet<RowKey>;
  onSelectionChange?: (keys: Set<RowKey>) => void;
  rowLabel?: (row: T) => string;
  /** Controlled sort. With `onSortChange` and no sortValue the parent sorts (server side). */
  sort?: SortState | null;
  onSortChange?: (sort: SortState | null) => void;
  /** Client-side paging. Use `pagination` instead when the server pages. */
  pageSize?: number;
  pagination?: ServerPagination;
  stickyHeader?: boolean;
  maxHeightClass?: string;
  density?: Density;
  onDensityChange?: (density: Density) => void;
  showDensityToggle?: boolean;
  showColumnMenu?: boolean;
}

const SKELETON_ROWS = 5;
const nextSort = (current: SortState | null, id: string): SortState | null => {
  if (current?.columnId !== id) return { columnId: id, direction: "asc" };
  return current.direction === "asc" ? { columnId: id, direction: "desc" } : null;
};

export function DataTable<T>({
  columns,
  rows,
  keyExtractor,
  isLoading,
  error,
  onRetry,
  emptyTitle = "No records found",
  emptyDescription,
  emptyAction,
  emptyIllustration,
  onRowClick,
  caption,
  selectable,
  selectedKeys,
  onSelectionChange,
  rowLabel,
  sort: controlledSort,
  onSortChange,
  pageSize,
  pagination,
  stickyHeader,
  maxHeightClass = "max-h-[32rem]",
  density: controlledDensity,
  onDensityChange,
  showDensityToggle,
  showColumnMenu,
}: DataTableProps<T>) {
  const [internalSort, setInternalSort] = useState<SortState | null>(null);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [hidden, setHidden] = useState<Set<string>>(
    () => new Set(columns.filter((column) => column.defaultHidden).map(columnId)),
  );
  const [internalDensity, setInternalDensity] = useState<Density>("comfortable");
  const [internalSelection, setInternalSelection] = useState<Set<RowKey>>(new Set());
  const [page, setPage] = useState(1);

  const sort = controlledSort !== undefined ? controlledSort : internalSort;
  const serverSort = onSortChange !== undefined && columns.every((column) => !column.sortValue);
  const density = controlledDensity ?? internalDensity;
  const selection = selectedKeys ?? internalSelection;

  const visibleColumns = useMemo(() => columns.filter((column) => !hidden.has(columnId(column))), [columns, hidden]);
  const processed = useTablePipeline({ rows, columns, filters, sort: serverSort ? null : sort });

  const totalPages = pageSize ? Math.max(1, Math.ceil(processed.length / pageSize)) : 1;
  const currentPage = Math.min(page, totalPages);
  const pageRows = pageSize ? processed.slice((currentPage - 1) * pageSize, currentPage * pageSize) : processed;

  const handleSort = (id: string) => {
    const next = nextSort(sort, id);
    setPage(1);
    if (controlledSort === undefined) setInternalSort(next);
    onSortChange?.(next);
  };

  const setSelection = (next: Set<RowKey>) => {
    if (selectedKeys === undefined) setInternalSelection(next);
    onSelectionChange?.(next);
  };
  const pageKeys = pageRows.map(keyExtractor);
  const selectedOnPage = pageKeys.filter((key) => selection.has(key)).length;
  const toggleAll = () => {
    const next = new Set(selection);
    const everySelected = selectedOnPage === pageKeys.length;
    for (const key of pageKeys) {
      if (everySelected) next.delete(key);
      else next.add(key);
    }
    setSelection(next);
  };
  const toggleRow = (key: RowKey) => {
    const next = new Set(selection);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setSelection(next);
  };

  const hasFilters = Object.values(filters).some(Boolean);
  const colSpan = visibleColumns.length + (selectable ? 1 : 0);
  const cellPadding = density === "compact" ? "px-4 py-1.5" : "px-4 py-3";
  const toolbar = showColumnMenu || showDensityToggle;

  if (error) {
    return (
      <ErrorState
        message={error}
        action={
          onRetry && (
            <Button variant="secondary" size="sm" onClick={onRetry}>
              Try again
            </Button>
          )
        }
      />
    );
  }
  if (!isLoading && rows.length === 0 && !hasFilters) {
    return (
      <EmptyState
        title={emptyTitle}
        description={emptyDescription}
        action={emptyAction}
        illustration={emptyIllustration}
      />
    );
  }

  const onRowKeyDown = (event: KeyboardEvent<HTMLTableRowElement>, row: T) => {
    // Only the row itself activates; Enter or Space on a checkbox or button inside keeps its own meaning.
    if (event.target !== event.currentTarget) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onRowClick?.(row);
    }
  };

  const sortedBy = sort && columns.find((column) => columnId(column) === sort.columnId);
  const announcement = isLoading
    ? ""
    : `${processed.length} ${processed.length === 1 ? "row" : "rows"}${
        sortedBy ? `, sorted by ${sortedBy.header} ${sort.direction === "asc" ? "ascending" : "descending"}` : ""
      }`;

  return (
    <div>
      {toolbar && (
        <DataTableToolbar
          columns={columns}
          hidden={hidden}
          onToggleColumn={(id) =>
            setHidden((current) => {
              const next = new Set(current);
              if (next.has(id)) next.delete(id);
              else next.add(id);
              return next;
            })
          }
          showColumnMenu={Boolean(showColumnMenu)}
          density={density}
          onDensityChange={
            showDensityToggle
              ? (value) => {
                  setInternalDensity(value);
                  onDensityChange?.(value);
                }
              : undefined
          }
        />
      )}
      {/* The scroll container is focusable so keyboard users can scroll a wide table (WCAG 2.1.1). */}
      <div
        // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- scrollable regions must be focusable
        tabIndex={0}
        role="region"
        aria-label={caption ? `${caption} (scrollable)` : "Table (scrollable)"}
        className={cn("overflow-auto", FOCUS_RING, stickyHeader && maxHeightClass)}
      >
        <table
          className="min-w-full divide-y divide-border text-sm text-text-primary"
          aria-busy={isLoading || undefined}
        >
          {caption && <caption className="sr-only">{caption}</caption>}
          <DataTableHead
            columns={visibleColumns}
            sort={sort}
            onSort={handleSort}
            filters={filters}
            onFilter={(id, value) => {
              setPage(1);
              setFilters((current) => ({ ...current, [id]: value }));
            }}
            sticky={Boolean(stickyHeader)}
            selectable={Boolean(selectable)}
            allSelected={pageKeys.length > 0 && selectedOnPage === pageKeys.length}
            someSelected={selectedOnPage > 0}
            onToggleAll={toggleAll}
            cellPadding={cellPadding}
          />
          <tbody className="divide-y divide-border bg-surface">
            {isLoading &&
              Array.from({ length: SKELETON_ROWS }, (_, index) => (
                <tr key={index} aria-hidden="true">
                  {Array.from({ length: colSpan }, (_, cell) => (
                    <td key={cell} className={cellPadding}>
                      <Skeleton className="h-4 w-full" />
                    </td>
                  ))}
                </tr>
              ))}
            {!isLoading && pageRows.length === 0 && (
              <tr>
                <td colSpan={colSpan}>
                  <EmptyState
                    title="No matching records"
                    description="No rows match the current filters."
                    illustration="search"
                    action={
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          setPage(1);
                          setFilters({});
                        }}
                      >
                        Clear filters
                      </Button>
                    }
                  />
                </td>
              </tr>
            )}
            {!isLoading &&
              pageRows.map((row) => {
                const key = keyExtractor(row);
                const isSelected = selection.has(key);
                return (
                  <tr
                    key={key}
                    tabIndex={onRowClick ? 0 : undefined}
                    aria-selected={selectable ? isSelected : undefined}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    onKeyDown={onRowClick ? (event) => onRowKeyDown(event, row) : undefined}
                    className={cn(
                      isSelected && "bg-brand-subtle",
                      onRowClick && cn("cursor-pointer hover:bg-bg", FOCUS_RING, "focus-visible:ring-inset"),
                    )}
                  >
                    {selectable && (
                      <td className={cn(cellPadding, "w-10")} onClick={(event) => event.stopPropagation()}>
                        <Checkbox
                          aria-label={rowLabel ? `Select ${rowLabel(row)}` : `Select row ${key}`}
                          checked={isSelected}
                          onChange={() => toggleRow(key)}
                        />
                      </td>
                    )}
                    {visibleColumns.map((column) => (
                      <td
                        key={columnId(column)}
                        className={cn(
                          cellPadding,
                          "text-text-primary",
                          column.isAmount && "text-right",
                          column.className,
                        )}
                      >
                        {column.accessor(row)}
                      </td>
                    ))}
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
      {isLoading && <VisuallyHidden as="p">Loading…</VisuallyHidden>}
      <div role="status" className="sr-only">
        {announcement}
      </div>
      {selectable && selection.size > 0 && (
        <p className="border-t border-border px-4 py-2 text-sm text-text-secondary">{selection.size} selected</p>
      )}
      {pagination ? (
        <Pagination
          page={pagination.page}
          pageSize={pagination.pageSize}
          total={pagination.total}
          totalPages={Math.max(1, Math.ceil(pagination.total / pagination.pageSize))}
          onPageChange={pagination.onPageChange}
        />
      ) : (
        pageSize &&
        !isLoading && (
          <Pagination
            page={currentPage}
            pageSize={pageSize}
            total={processed.length}
            totalPages={totalPages}
            onPageChange={setPage}
          />
        )
      )}
    </div>
  );
}
