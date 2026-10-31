import { type KeyboardEvent, type ReactNode, useId, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import { FOCUS_RING } from "./focus";

export interface TabItem {
  id: string;
  label: string;
  content: ReactNode;
  disabled?: boolean;
  /** Short count or marker shown after the label. */
  badge?: ReactNode;
}

interface TabsProps {
  tabs: TabItem[];
  label: string;
  value?: string;
  defaultValue?: string;
  onChange?: (id: string) => void;
  orientation?: "horizontal" | "vertical";
}

/** Roving tabindex with automatic activation: arrows move focus and select; Home and End jump to the ends. */
export function Tabs({ tabs, label, value, defaultValue, onChange, orientation = "horizontal" }: TabsProps) {
  const baseId = useId();
  const [internal, setInternal] = useState(defaultValue ?? tabs.find((tab) => !tab.disabled)?.id ?? "");
  const selected = value ?? internal;
  const refs = useRef(new Map<string, HTMLButtonElement>());
  const isVertical = orientation === "vertical";

  const select = (id: string) => {
    setInternal(id);
    onChange?.(id);
    refs.current.get(id)?.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const enabled = tabs.filter((tab) => !tab.disabled);
    const index = enabled.findIndex((tab) => tab.id === selected);
    const next = isVertical ? "ArrowDown" : "ArrowRight";
    const previous = isVertical ? "ArrowUp" : "ArrowLeft";
    let target: number | null = null;
    if (event.key === next) target = (index + 1) % enabled.length;
    else if (event.key === previous) target = (index - 1 + enabled.length) % enabled.length;
    else if (event.key === "Home") target = 0;
    else if (event.key === "End") target = enabled.length - 1;
    if (target === null || enabled.length === 0) return;
    event.preventDefault();
    select(enabled[target].id);
  };

  const active = tabs.find((tab) => tab.id === selected);

  return (
    <div className={cn(isVertical && "flex gap-6")}>
      <div
        role="tablist"
        aria-label={label}
        aria-orientation={orientation}
        className={cn("flex gap-1 border-border", isVertical ? "flex-col border-r pr-2" : "overflow-x-auto border-b")}
      >
        {tabs.map((tab) => {
          const isSelected = tab.id === selected;
          return (
            <button
              key={tab.id}
              ref={(node) => {
                if (node) refs.current.set(tab.id, node);
                else refs.current.delete(tab.id);
              }}
              type="button"
              role="tab"
              id={`${baseId}-tab-${tab.id}`}
              aria-selected={isSelected}
              aria-controls={`${baseId}-panel-${tab.id}`}
              tabIndex={isSelected ? 0 : -1}
              disabled={tab.disabled}
              onClick={() => select(tab.id)}
              onKeyDown={onKeyDown}
              className={cn(
                "inline-flex items-center gap-2 whitespace-nowrap px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50 max-sm:min-h-11",
                FOCUS_RING,
                // The selected tab gets an underline (or a side bar when vertical) as well as a colour change.
                isSelected
                  ? cn("text-brand", isVertical ? "border-r-2 border-brand" : "-mb-px border-b-2 border-brand")
                  : "text-text-secondary hover:text-text-primary",
              )}
            >
              {tab.label}
              {tab.badge !== undefined && (
                <span className="rounded-full bg-bg px-1.5 text-xs text-text-secondary">{tab.badge}</span>
              )}
            </button>
          );
        })}
      </div>
      {active && (
        <div
          role="tabpanel"
          id={`${baseId}-panel-${active.id}`}
          aria-labelledby={`${baseId}-tab-${active.id}`}
          tabIndex={0}
          className={cn("min-w-0 flex-1 pt-4", FOCUS_RING)}
        >
          {active.content}
        </div>
      )}
    </div>
  );
}
