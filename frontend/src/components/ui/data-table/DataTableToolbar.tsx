import { Columns3, Rows3 } from "lucide-react";
import { useId, useRef, useState } from "react";

import { Checkbox } from "../Checkbox";
import { FOCUS_RING } from "../focus";
import { useDismiss } from "../use-dismiss";
import { cn } from "@/lib/utils";

import { type Column, type Density, columnId } from "./types";

interface ToolbarProps<T> {
  columns: Column<T>[];
  hidden: Set<string>;
  onToggleColumn: (id: string) => void;
  showColumnMenu: boolean;
  density: Density;
  onDensityChange?: (density: Density) => void;
}

const BUTTON =
  "inline-flex items-center gap-1.5 rounded-control border border-border-strong bg-surface px-3 py-1.5 text-sm font-medium text-text-primary hover:bg-bg max-sm:min-h-11";

export function DataTableToolbar<T>({
  columns,
  hidden,
  onToggleColumn,
  showColumnMenu,
  density,
  onDensityChange,
}: ToolbarProps<T>) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  useDismiss(open, () => setOpen(false), menuRef, triggerRef);

  return (
    <div className="flex flex-wrap items-center justify-end gap-2 border-b border-border px-4 py-2">
      {onDensityChange && (
        <button
          type="button"
          aria-pressed={density === "compact"}
          onClick={() => onDensityChange(density === "compact" ? "comfortable" : "compact")}
          className={cn(BUTTON, FOCUS_RING)}
        >
          <Rows3 aria-hidden="true" className="h-4 w-4" />
          {density === "compact" ? "Compact rows" : "Comfortable rows"}
        </button>
      )}
      {showColumnMenu && (
        <div className="relative">
          <button
            ref={triggerRef}
            type="button"
            aria-expanded={open}
            aria-controls={menuId}
            onClick={() => setOpen((current) => !current)}
            className={cn(BUTTON, FOCUS_RING)}
          >
            <Columns3 aria-hidden="true" className="h-4 w-4" />
            Columns
          </button>
          {open && (
            <div
              ref={menuRef}
              id={menuId}
              role="group"
              aria-label="Visible columns"
              className="absolute right-0 z-30 mt-1 min-w-48 space-y-2 rounded-card border border-border bg-surface-raised p-3 shadow-elev-2"
            >
              {columns.map((column) => (
                <Checkbox
                  key={columnId(column)}
                  label={column.header}
                  checked={!hidden.has(columnId(column))}
                  disabled={column.alwaysVisible}
                  onChange={() => onToggleColumn(columnId(column))}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
