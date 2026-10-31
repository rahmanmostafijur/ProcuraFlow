import { Search } from "lucide-react";
import { type KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";

import { PaletteResults } from "./command-palette/PaletteResults";
import {
  type PaletteAction,
  type PaletteSection,
  type RecentEntry,
  type SearchFetcher,
  type SearchGroup,
  type SearchItem,
  paletteOptionId,
} from "./command-palette/palette-types";
import { loadRecent, rememberRecent } from "./command-palette/recent-storage";
import { useShortcut } from "./shortcuts-context";
import { useDebouncedValue } from "./use-debounced-value";
import { useOverlay } from "./use-overlay";
import { VisuallyHidden } from "./VisuallyHidden";

interface CommandPaletteProps {
  /** Async search. Injected so the palette knows nothing about the API; the server groups and scopes results. */
  search: SearchFetcher;
  actions?: PaletteAction[];
  /** Called when a search result is chosen (navigate to `item.href`, open a drawer...). */
  onSelectItem: (item: SearchItem) => void;
  debounceMs?: number;
  /** Controlled mode. Leave both unset and Ctrl/Cmd+K opens and closes it. */
  isOpen?: boolean;
  onClose?: () => void;
}

const matchesAction = (action: PaletteAction, needle: string): boolean =>
  [action.label, ...(action.keywords ?? [])].some((text) => text.toLowerCase().includes(needle));

export function CommandPalette({
  search,
  actions = [],
  onSelectItem,
  debounceMs = 200,
  isOpen,
  onClose,
}: CommandPaletteProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const controlled = isOpen !== undefined;
  const open = controlled ? isOpen : internalOpen;
  const close = () => (controlled ? onClose?.() : setInternalOpen(false));

  useShortcut({
    keys: "mod+k",
    description: "Open command palette",
    group: "General",
    allowInInputs: true,
    handler: () => (controlled ? undefined : setInternalOpen((current) => !current)),
  });

  if (!open) return null;
  return (
    <PaletteDialog
      search={search}
      actions={actions}
      onSelectItem={onSelectItem}
      debounceMs={debounceMs}
      onClose={close}
    />
  );
}

interface DialogProps extends Pick<CommandPaletteProps, "search" | "onSelectItem"> {
  actions: PaletteAction[];
  debounceMs: number;
  onClose: () => void;
}

// Mounted only while open, so the query, highlight and results reset every time.
function PaletteDialog({ search, actions, onSelectItem, debounceMs, onClose }: DialogProps) {
  const listId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [recent, setRecent] = useState<RecentEntry[]>(loadRecent);
  const [answer, setAnswer] = useState<{ query: string; groups: SearchGroup[]; failed: boolean } | null>(null);
  useOverlay({ active: true, onClose, containerRef: panelRef });

  const trimmed = query.trim();
  const debounced = useDebouncedValue(trimmed, debounceMs);

  useEffect(() => {
    if (!debounced) return;
    const controller = new AbortController();
    search(debounced, controller.signal)
      .then((groups) => {
        if (!controller.signal.aborted) setAnswer({ query: debounced, groups, failed: false });
      })
      .catch(() => {
        if (!controller.signal.aborted) setAnswer({ query: debounced, groups: [], failed: true });
      });
    return () => controller.abort();
  }, [search, debounced]);

  const isLoading = Boolean(trimmed) && (debounced !== trimmed || answer?.query !== trimmed);
  const failed = !isLoading && Boolean(trimmed) && answer?.failed === true;

  const sections = useMemo<PaletteSection[]>(() => {
    const pickItem = (item: SearchItem) => () => {
      setRecent(rememberRecent({ type: "item", item }));
      onClose();
      onSelectItem(item);
    };
    const pickAction = (action: PaletteAction) => () => {
      setRecent(rememberRecent({ type: "action", id: action.id }));
      onClose();
      action.run();
    };
    const actionRows = (list: PaletteAction[]) =>
      list.map((action) => ({
        key: `action:${action.id}`,
        label: action.label,
        description: action.description,
        kind: "Action",
        onSelect: pickAction(action),
      }));

    if (!trimmed) {
      const recentRows = recent.flatMap((entry) => {
        if (entry.type === "item") {
          return [
            {
              key: `recent:${entry.item.id}`,
              label: entry.item.label,
              description: entry.item.description,
              kind: entry.item.kind,
              onSelect: pickItem(entry.item),
            },
          ];
        }
        const action = actions.find((candidate) => candidate.id === entry.id);
        return action ? actionRows([action]).map((row) => ({ ...row, key: `recent:${row.key}` })) : [];
      });
      return [
        { id: "recent", label: "Recent", rows: recentRows },
        { id: "actions", label: "Actions", rows: actionRows(actions) },
      ].filter((section) => section.rows.length > 0);
    }

    const results: PaletteSection[] =
      isLoading || failed
        ? []
        : (answer?.groups ?? []).map((group) => ({
            id: `group-${group.id}`,
            label: group.label,
            rows: group.items.map((item) => ({
              key: `${group.id}:${item.id}`,
              label: item.label,
              description: item.description,
              kind: item.kind,
              onSelect: pickItem(item),
            })),
          }));
    const needle = trimmed.toLowerCase();
    const matching = actions.filter((action) => matchesAction(action, needle));
    return [...results, { id: "actions", label: "Actions", rows: actionRows(matching) }].filter(
      (section) => section.rows.length > 0,
    );
  }, [trimmed, recent, actions, answer, isLoading, failed, onClose, onSelectItem]);

  const rows = sections.flatMap((section) => section.rows);
  const activeIndex = Math.min(active, Math.max(rows.length - 1, 0));
  const activeId = rows.length > 0 ? paletteOptionId(listId, activeIndex) : undefined;

  useEffect(() => {
    if (activeId) document.getElementById(activeId)?.scrollIntoView?.({ block: "nearest" });
  }, [activeId]);

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (rows.length === 0) return;
      setActive((activeIndex + (event.key === "ArrowDown" ? 1 : -1) + rows.length) % rows.length);
    } else if (event.key === "Enter" && rows[activeIndex]) {
      event.preventDefault();
      rows[activeIndex].onSelect();
    }
  };

  const message = isLoading
    ? "Searching…"
    : failed
      ? "Search failed. Try again."
      : rows.length === 0
        ? "No results"
        : `${rows.length} result${rows.length === 1 ? "" : "s"}`;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center p-4 pt-[12vh]">
      <div className="scrim absolute inset-0 animate-fade-in" aria-hidden="true" onClick={onClose} />
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="relative w-full max-w-xl animate-pop-in overflow-hidden rounded-overlay border border-border bg-surface-raised text-text-primary shadow-elev-3 focus:outline-none"
      >
        <div className="flex items-center gap-3 border-b border-border px-4">
          <Search aria-hidden="true" className="h-4 w-4 shrink-0 text-text-secondary" />
          <input
            data-autofocus
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={activeId}
            aria-label="Search or run a command"
            autoComplete="off"
            placeholder="Search records or run a command…"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActive(0);
            }}
            onKeyDown={onKeyDown}
            className="h-12 w-full bg-transparent text-body text-text-primary placeholder:text-text-muted focus:outline-none"
          />
        </div>
        {rows.length > 0 ? (
          <PaletteResults sections={sections} listId={listId} activeIndex={activeIndex} onActivate={setActive} />
        ) : (
          <p className="px-4 py-6 text-center text-sm text-text-secondary">{message}</p>
        )}
        <VisuallyHidden>
          <span role="status" aria-live="polite">
            {message}
          </span>
        </VisuallyHidden>
      </div>
    </div>
  );
}
