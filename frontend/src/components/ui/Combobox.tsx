import { Check, ChevronDown } from "lucide-react";
import { type KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import { useFieldControl } from "./field-context";
import { controlClasses } from "./field-styles";
import { Spinner } from "./Spinner";
import { useDebouncedValue } from "./use-debounced-value";
import { VisuallyHidden } from "./VisuallyHidden";

export interface ComboboxOption {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
}

interface ComboboxProps {
  value: ComboboxOption | null;
  onChange: (option: ComboboxOption | null) => void;
  /** Static options, filtered locally by label. */
  options?: ComboboxOption[];
  /** Async options for a query. Takes precedence over `options`. The signal aborts when a newer query starts. */
  fetchOptions?: (query: string, signal: AbortSignal) => Promise<ComboboxOption[]>;
  debounceMs?: number;
  placeholder?: string;
  emptyText?: string;
  loadingText?: string;
  errorText?: string;
  disabled?: boolean;
  id?: string;
  "aria-label"?: string;
  error?: string;
}

/** ARIA 1.2 combobox with a list popup: focus stays on the input, aria-activedescendant names the highlighted row. */
export function Combobox({
  value,
  onChange,
  options = [],
  fetchOptions,
  debounceMs = 200,
  placeholder,
  emptyText = "No results",
  loadingText = "Loading…",
  errorText = "Could not load results",
  disabled,
  error,
  ...rest
}: ComboboxProps) {
  const control = useFieldControl({ id: rest.id, error });
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState<string | null>(null);
  const [active, setActive] = useState(0);
  // The answer carries the query it was for, so "loading" is derived (no answer for the current query yet).
  const [answer, setAnswer] = useState<{ query: string; options: ComboboxOption[]; failed: boolean } | null>(null);

  const text = query ?? value?.label ?? "";
  const debouncedQuery = useDebouncedValue(query ?? "", debounceMs);

  useEffect(() => {
    if (!fetchOptions || !open) return;
    const controller = new AbortController();
    fetchOptions(debouncedQuery, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setAnswer({ query: debouncedQuery, options: result, failed: false });
      })
      .catch(() => {
        if (!controller.signal.aborted) setAnswer({ query: debouncedQuery, options: [], failed: true });
      });
    return () => controller.abort();
  }, [fetchOptions, debouncedQuery, open]);

  const isCurrent = answer?.query === debouncedQuery && debouncedQuery === (query ?? "");
  const status: "idle" | "loading" | "error" =
    !fetchOptions || !open ? "idle" : !isCurrent ? "loading" : answer.failed ? "error" : "idle";

  const visible = useMemo(() => {
    if (fetchOptions) return answer?.options ?? [];
    const needle = (query ?? "").trim().toLowerCase();
    return needle ? options.filter((option) => option.label.toLowerCase().includes(needle)) : options;
  }, [fetchOptions, answer, options, query]);

  const optionId = (index: number) => `${listId}-option-${index}`;
  const hasList = open && visible.length > 0 && status !== "error";
  const activeId = hasList ? optionId(Math.min(active, visible.length - 1)) : undefined;

  useEffect(() => {
    if (activeId) document.getElementById(activeId)?.scrollIntoView?.({ block: "nearest" });
  }, [activeId]);

  const close = () => {
    setOpen(false);
    setQuery(null);
  };

  const choose = (option: ComboboxOption) => {
    if (option.disabled) return;
    onChange(option);
    close();
  };

  const move = (delta: number) => {
    if (!open) return setOpen(true);
    if (visible.length === 0) return;
    setActive((current) => (current + delta + visible.length) % visible.length);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        return move(1);
      case "ArrowUp":
        event.preventDefault();
        return move(-1);
      case "Enter":
        if (hasList) {
          event.preventDefault();
          choose(visible[Math.min(active, visible.length - 1)]);
        }
        return;
      case "Escape":
        if (open) {
          event.preventDefault();
          event.stopPropagation();
          close();
        } else if (value) {
          onChange(null);
        }
        return;
      case "Tab":
        return close();
    }
  };

  const message =
    status === "loading" ? loadingText : status === "error" ? errorText : visible.length === 0 ? emptyText : null;
  const announcement = message ?? `${visible.length} result${visible.length === 1 ? "" : "s"} available`;

  return (
    <div
      className="relative w-full"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) close();
      }}
    >
      <input
        ref={inputRef}
        id={control.id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={activeId}
        aria-label={rest["aria-label"]}
        aria-invalid={control.invalid || undefined}
        aria-describedby={control.describedBy}
        autoComplete="off"
        disabled={disabled}
        placeholder={placeholder}
        value={text}
        className={controlClasses(control.invalid, "pr-9")}
        onChange={(event) => {
          setQuery(event.target.value);
          setActive(0);
          setOpen(true);
        }}
        onClick={() => setOpen(true)}
        onKeyDown={onKeyDown}
      />
      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary">
        {status === "loading" ? <Spinner /> : <ChevronDown aria-hidden="true" className="h-4 w-4" />}
      </span>
      <VisuallyHidden>
        <span role="status" aria-live="polite">
          {open ? announcement : ""}
        </span>
      </VisuallyHidden>
      {open && (
        <div className="absolute z-30 mt-1 max-h-64 w-full overflow-auto rounded-card border border-border bg-surface-raised py-1 shadow-elev-2">
          <ul
            id={listId}
            role="listbox"
            aria-label={rest["aria-label"] ?? "Options"}
            className={cn(!hasList && "hidden")}
          >
            {visible.map((option, index) => {
              const isActive = optionId(index) === activeId;
              const isSelected = value?.value === option.value;
              return (
                // Keyboard users pick with Enter on the input (aria-activedescendant), so no key handler here.
                // eslint-disable-next-line jsx-a11y/click-events-have-key-events
                <li
                  key={option.value}
                  id={optionId(index)}
                  role="option"
                  aria-selected={isSelected}
                  aria-disabled={option.disabled || undefined}
                  // mousedown would blur the input before click lands, so it is cancelled to keep focus.
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => choose(option)}
                  onMouseMove={() => setActive(index)}
                  className={cn(
                    "flex cursor-pointer items-center justify-between gap-2 px-3 py-2 text-sm text-text-primary",
                    isActive && "bg-brand-subtle text-brand-subtle-fg",
                    option.disabled && "cursor-not-allowed opacity-50",
                  )}
                >
                  <span>
                    {option.label}
                    {option.description && (
                      <span className="block text-xs text-text-secondary">{option.description}</span>
                    )}
                  </span>
                  {isSelected && <Check aria-hidden="true" className="h-4 w-4 shrink-0" />}
                </li>
              );
            })}
          </ul>
          {message && <p className="px-3 py-2 text-sm text-text-secondary">{message}</p>}
        </div>
      )}
    </div>
  );
}
