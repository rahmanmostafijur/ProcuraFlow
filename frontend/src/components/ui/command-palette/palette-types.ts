export interface SearchItem {
  id: string;
  label: string;
  description?: string;
  href?: string;
  /** Kind of record, e.g. "Purchase order"; shown as a hint beside the label. */
  kind?: string;
}

/** The server decides what the user may see and how results are grouped; the palette only renders them. */
export interface SearchGroup {
  id: string;
  label: string;
  items: SearchItem[];
}

export type SearchFetcher = (query: string, signal: AbortSignal) => Promise<SearchGroup[]>;

export interface PaletteAction {
  id: string;
  label: string;
  description?: string;
  keywords?: string[];
  run: () => void;
}

/** One selectable line in the list. */
export interface PaletteRow {
  key: string;
  label: string;
  description?: string;
  kind?: string;
  onSelect: () => void;
}

export interface PaletteSection {
  id: string;
  label: string;
  rows: PaletteRow[];
}

export type RecentEntry = { type: "item"; item: SearchItem } | { type: "action"; id: string };

export const paletteOptionId = (listId: string, index: number): string => `${listId}-option-${index}`;
