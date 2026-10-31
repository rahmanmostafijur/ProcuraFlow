import type { RecentEntry } from "./palette-types";

export const RECENT_STORAGE_KEY = "pf-command-recent";
const MAX_RECENT = 6;

const entryKey = (entry: RecentEntry): string =>
  entry.type === "item" ? `item:${entry.item.id}` : `action:${entry.id}`;

function isEntry(value: unknown): value is RecentEntry {
  if (typeof value !== "object" || value === null) return false;
  const entry = value as { type?: unknown; id?: unknown; item?: { id?: unknown; label?: unknown } };
  if (entry.type === "action") return typeof entry.id === "string";
  return entry.type === "item" && typeof entry.item?.id === "string" && typeof entry.item.label === "string";
}

// Storage can throw (private windows, blocked site data) and may hold anything, so every access is guarded.
export function loadRecent(): RecentEntry[] {
  try {
    const raw = window.localStorage.getItem(RECENT_STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter(isEntry).slice(0, MAX_RECENT) : [];
  } catch {
    return [];
  }
}

/** Most recent first, no duplicates, capped. Returns the new list so the caller can show it without re-reading. */
export function rememberRecent(entry: RecentEntry): RecentEntry[] {
  const next = [entry, ...loadRecent().filter((existing) => entryKey(existing) !== entryKey(entry))].slice(
    0,
    MAX_RECENT,
  );
  try {
    window.localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Not persisted; the list still works for this page view.
  }
  return next;
}
