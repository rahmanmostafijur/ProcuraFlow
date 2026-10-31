import { useState, useSyncExternalStore } from "react";

import { Modal } from "./Modal";
import { type RegisteredShortcut, formatKeys, useShortcut, useShortcutRegistry } from "./shortcuts-context";

interface ShortcutHelpProps {
  /** Controlled mode. Leave both unset and the "?" shortcut opens and closes it. */
  isOpen?: boolean;
  onClose?: () => void;
}

function useRegisteredShortcuts(): RegisteredShortcut[] {
  const registry = useShortcutRegistry();
  // list() builds a fresh array each call; the snapshot is keyed by content so React sees a stable value.
  const snapshot = useSyncExternalStore(
    registry.subscribe,
    () => JSON.stringify(registry.list()),
    () => "[]",
  );
  return JSON.parse(snapshot) as RegisteredShortcut[];
}

function groupShortcuts(shortcuts: RegisteredShortcut[]): Array<[string, RegisteredShortcut[]]> {
  const groups = new Map<string, RegisteredShortcut[]>();
  for (const shortcut of shortcuts) {
    const name = shortcut.group ?? "General";
    groups.set(name, [...(groups.get(name) ?? []), shortcut]);
  }
  return Array.from(groups.entries());
}

export function ShortcutHelp({ isOpen, onClose }: ShortcutHelpProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  const controlled = isOpen !== undefined;
  const open = controlled ? isOpen : internalOpen;
  const close = () => (controlled ? onClose?.() : setInternalOpen(false));
  const shortcuts = useRegisteredShortcuts();

  // "?" is a bare key, so the registry already ignores it while the user types in a field.
  useShortcut({
    keys: "?",
    description: "Show keyboard shortcuts",
    group: "General",
    handler: () => (controlled ? undefined : setInternalOpen((current) => !current)),
  });

  return (
    <Modal isOpen={open} onClose={close} title="Keyboard shortcuts" size="md">
      <div className="space-y-5">
        {groupShortcuts(shortcuts).map(([group, items]) => (
          <section key={group} aria-labelledby={`shortcut-group-${group}`}>
            <h3 id={`shortcut-group-${group}`} className="mb-2 text-caption uppercase text-text-secondary">
              {group}
            </h3>
            <dl className="divide-y divide-border">
              {items.map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-4 py-2">
                  <dt className="text-sm text-text-primary">{item.description}</dt>
                  <dd className="flex items-center gap-1">
                    {formatKeys(item.keys).map((part, index) =>
                      part === "then" ? (
                        <span key={index} className="text-xs text-text-secondary">
                          then
                        </span>
                      ) : (
                        <kbd
                          key={index}
                          className="rounded-control border border-border-strong bg-bg px-1.5 py-0.5 font-mono text-xs text-text-primary"
                        >
                          {part}
                        </kbd>
                      ),
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>
    </Modal>
  );
}
