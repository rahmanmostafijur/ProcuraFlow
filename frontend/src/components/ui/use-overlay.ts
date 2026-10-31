import { type RefObject, useEffect, useRef } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// Overlays can nest (a confirm dialog over a drawer). Only the top one answers Escape and Tab.
const stack: symbol[] = [];
let scrollLocks = 0;

export function focusableWithin(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE));
}

interface OverlayOptions {
  active: boolean;
  onClose: () => void;
  containerRef: RefObject<HTMLElement | null>;
}

/**
 * Dialog behaviour shared by Modal, Drawer, CommandPalette and ShortcutHelp: on open remember the trigger and move
 * focus inside (an element marked data-autofocus, else the first control in data-overlay-body, else the first
 * control); Tab and Shift+Tab wrap inside; Escape closes; on close focus returns to the trigger; page scroll locks.
 */
export function useOverlay({ active, onClose, containerRef }: OverlayOptions): void {
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    if (!container) return;
    const id = Symbol("overlay");
    stack.push(id);
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;

    const body = container.querySelector<HTMLElement>("[data-overlay-body]");
    const target =
      container.querySelector<HTMLElement>("[data-autofocus]") ??
      (body ? focusableWithin(body)[0] : undefined) ??
      focusableWithin(container)[0] ??
      container;
    target.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (stack[stack.length - 1] !== id) return;
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusableWithin(container);
      if (items.length === 0) {
        event.preventDefault();
        container.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const current = document.activeElement;
      if (event.shiftKey && (current === first || !container.contains(current))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (current === last || !container.contains(current))) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    if (scrollLocks++ === 0) document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      stack.splice(stack.indexOf(id), 1);
      if (--scrollLocks === 0) document.body.style.overflow = "";
      if (trigger?.isConnected) trigger.focus();
    };
  }, [active, containerRef]);
}
