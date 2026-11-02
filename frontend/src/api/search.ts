import type { SearchFetcher, SearchGroup } from "@/components/ui/command-palette/palette-types";

import { apiClient } from "./client";

interface ApiSearchItem {
  id: number;
  title: string;
  subtitle: string | null;
  status: string | null;
  url: string;
}

interface ApiSearchResponse {
  query: string;
  groups: Array<{ type: string; label: string; items: ApiSearchItem[] }>;
}

/** Calls GET /search and reshapes the scoped, server-grouped result for the command palette. */
export const searchEverything: SearchFetcher = async (query, signal) => {
  const { data } = await apiClient.get<ApiSearchResponse>("/search", { params: { q: query }, signal });
  return data.groups.map((group): SearchGroup => ({
    id: group.type,
    label: group.label,
    items: group.items.map((item) => ({
      id: `${group.type}-${item.id}`,
      label: item.title,
      description: [item.subtitle, item.status].filter(Boolean).join(" · ") || undefined,
      href: item.url,
      kind: group.label,
    })),
  }));
};
