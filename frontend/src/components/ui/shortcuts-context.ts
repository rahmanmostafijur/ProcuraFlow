import { createContext, useContext, useEffect, useRef } from "react";

export interface ShortcutDefinition {
  /**
   * "mod+k" (mod is Ctrl, or Cmd on Apple platforms), "shift+/" style combos, a bare character like "?", or a
   * two-key sequence separated by a space ("g d").
   */
  keys: string;
  description: string;
  group?: string;
  handler: (event: KeyboardEvent) => void;
  /** Mod combos work while typing by default; bare keys never do unless this is set. */
  allowInInputs?: boolean;
  enabled?: boolean;
}

export interface RegisteredShortcut extends Pick<ShortcutDefinition, "keys" | "description" | "group"> {
  id: number;
}

export interface ShortcutRegistry {
  register: (definition: () => ShortcutDefinition) => () => void;
  list: () => RegisteredShortcut[];
  subscribe: (listener: () => void) => () => void;
}

export const ShortcutContext = createContext<ShortcutRegistry | null>(null);

export const SEQUENCE_TIMEOUT_MS = 1000;

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export const isApplePlatform = (): boolean =>
  typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

/** Does this key press match a single combo such as "mod+k" or "?"? */
export function matchesCombo(event: KeyboardEvent, combo: string): boolean {
  const parts = combo.toLowerCase().split("+");
  const key = parts[parts.length - 1];
  const wantsMod = parts.includes("mod");
  const wantsShift = parts.includes("shift");
  const wantsAlt = parts.includes("alt");
  const hasMod = event.ctrlKey || event.metaKey;
  if (wantsMod !== hasMod || wantsAlt !== event.altKey) return false;
  // A bare "?" is typed with Shift, so Shift only counts when the combo names it explicitly.
  if (wantsShift && !event.shiftKey) return false;
  return event.key.toLowerCase() === key;
}

/** Display form: "mod+k" becomes ["Ctrl", "K"] (or Cmd on Apple), "g d" becomes ["G", "then D"]. */
export function formatKeys(keys: string, apple = isApplePlatform()): string[] {
  const label = (part: string) =>
    part === "mod"
      ? apple
        ? "Cmd"
        : "Ctrl"
      : part.length === 1
        ? part.toUpperCase()
        : part.charAt(0).toUpperCase() + part.slice(1);
  return keys.split(" ").flatMap((step, index) => {
    const parts = step.split("+").map(label);
    return index === 0 ? parts : ["then", ...parts];
  });
}

export function useShortcutRegistry(): ShortcutRegistry {
  const registry = useContext(ShortcutContext);
  if (!registry) throw new Error("Shortcut hooks must be used inside ShortcutProvider");
  return registry;
}

/**
 * Register a keyboard shortcut for the life of the component. Plain keys are ignored while the user is typing
 * in a field; the latest handler is always called, so it never needs to be memoised.
 */
export function useShortcut(definition: ShortcutDefinition): void {
  const registry = useShortcutRegistry();
  const latest = useRef(definition);
  useEffect(() => {
    latest.current = definition;
  });
  const { keys, description, group } = definition;
  useEffect(
    () => registry.register(() => ({ ...latest.current, keys, description, group })),
    [registry, keys, description, group],
  );
}
