import { type ReactNode, useEffect, useMemo, useRef } from "react";

import {
  type RegisteredShortcut,
  SEQUENCE_TIMEOUT_MS,
  ShortcutContext,
  type ShortcutDefinition,
  type ShortcutRegistry,
  isTypingTarget,
  matchesCombo,
} from "./shortcuts-context";

interface Entry {
  id: number;
  read: () => ShortcutDefinition;
}

/** One keydown listener for the whole app, dispatching to whatever shortcuts are currently registered. */
export function ShortcutProvider({ children }: { children: ReactNode }) {
  const entries = useRef(new Map<number, Entry>());
  const listeners = useRef(new Set<() => void>());
  const nextId = useRef(1);
  const pendingKey = useRef<{ key: string; timer: ReturnType<typeof setTimeout> } | null>(null);

  const registry = useMemo<ShortcutRegistry>(() => {
    const notify = () => listeners.current.forEach((listener) => listener());
    return {
      register: (read) => {
        const id = nextId.current++;
        entries.current.set(id, { id, read });
        notify();
        return () => {
          entries.current.delete(id);
          notify();
        };
      },
      list: (): RegisteredShortcut[] =>
        Array.from(entries.current.values()).map(({ id, read }) => {
          const { keys, description, group } = read();
          return { id, keys, description, group };
        }),
      subscribe: (listener) => {
        listeners.current.add(listener);
        return () => listeners.current.delete(listener);
      },
    };
  }, []);

  useEffect(() => {
    const clearPending = () => {
      if (pendingKey.current) clearTimeout(pendingKey.current.timer);
      pendingKey.current = null;
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing) return;
      const typing = isTypingTarget(event.target);
      const pending = pendingKey.current;
      clearPending();

      for (const { read } of entries.current.values()) {
        const shortcut = read();
        if (shortcut.enabled === false) continue;
        const hasMod = /(^|\+)mod\+/.test(shortcut.keys);
        if (typing && !shortcut.allowInInputs && !hasMod) continue;
        const [first, second] = shortcut.keys.split(" ");

        if (second !== undefined) {
          if (pending && pending.key === first.toLowerCase() && matchesCombo(event, second)) {
            event.preventDefault();
            shortcut.handler(event);
            return;
          }
          continue;
        }
        if (matchesCombo(event, first)) {
          event.preventDefault();
          shortcut.handler(event);
          return;
        }
      }

      // Not a complete shortcut: it may be the first key of a sequence like "g d".
      if (!typing && !event.ctrlKey && !event.metaKey && !event.altKey) {
        const key = event.key.toLowerCase();
        const startsSequence = Array.from(entries.current.values()).some(({ read }) => {
          const [first, second] = read().keys.split(" ");
          return second !== undefined && first.toLowerCase() === key;
        });
        if (startsSequence) {
          pendingKey.current = { key, timer: setTimeout(clearPending, SEQUENCE_TIMEOUT_MS) };
        }
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      clearPending();
    };
  }, []);

  return <ShortcutContext.Provider value={registry}>{children}</ShortcutContext.Provider>;
}
