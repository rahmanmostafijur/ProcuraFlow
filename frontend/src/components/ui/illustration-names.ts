export const ILLUSTRATION_NAMES = [
  "inbox",
  "search",
  "documents",
  "orders",
  "approvals",
  "suppliers",
  "files",
  "error",
] as const;

export type IllustrationName = (typeof ILLUSTRATION_NAMES)[number];
