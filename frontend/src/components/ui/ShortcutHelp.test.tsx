import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ShortcutHelp } from "./ShortcutHelp";
import { ShortcutProvider } from "./ShortcutProvider";
import { formatKeys, matchesCombo, useShortcut } from "./shortcuts-context";

function Registers({ handler, enabled = true }: { handler: () => void; enabled?: boolean }) {
  useShortcut({ keys: "g d", description: "Go to dashboard", group: "Navigation", handler, enabled });
  useShortcut({ keys: "n", description: "New request", group: "Create", handler: () => undefined });
  return null;
}

function setup(handler = vi.fn(), enabled = true) {
  render(
    <ShortcutProvider>
      <Registers handler={handler} enabled={enabled} />
      <ShortcutHelp />
      <input aria-label="Search box" />
    </ShortcutProvider>,
  );
  return handler;
}

describe("ShortcutHelp and useShortcut", () => {
  it("opens with ? and lists the registered shortcuts grouped, with keys in kbd", () => {
    setup();
    fireEvent.keyDown(document.body, { key: "?", shiftKey: true });
    const dialog = screen.getByRole("dialog", { name: "Keyboard shortcuts" });
    expect(within(dialog).getByRole("heading", { name: "Navigation" })).toBeInTheDocument();
    expect(within(dialog).getByRole("heading", { name: "Create" })).toBeInTheDocument();
    expect(within(dialog).getByText("Go to dashboard")).toBeInTheDocument();
    expect(within(dialog).getByText("Show keyboard shortcuts")).toBeInTheDocument();
    expect(dialog.querySelectorAll("kbd").length).toBeGreaterThanOrEqual(4);
  });

  it("closes with Escape and toggles with ? again", () => {
    setup();
    fireEvent.keyDown(document.body, { key: "?" });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.keyDown(document.body, { key: "?" });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("ignores plain keys typed in an input", () => {
    const handler = setup();
    const input = screen.getByRole("textbox", { name: "Search box" });
    fireEvent.keyDown(input, { key: "?" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.keyDown(input, { key: "g" });
    fireEvent.keyDown(input, { key: "d" });
    expect(handler).not.toHaveBeenCalled();
  });

  it("runs a two-key sequence, but not when the second key is too late or out of order", () => {
    vi.useFakeTimers();
    const handler = setup();
    fireEvent.keyDown(document.body, { key: "d" });
    expect(handler).not.toHaveBeenCalled();
    fireEvent.keyDown(document.body, { key: "g" });
    fireEvent.keyDown(document.body, { key: "d" });
    expect(handler).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(document.body, { key: "g" });
    vi.advanceTimersByTime(1500);
    fireEvent.keyDown(document.body, { key: "d" });
    expect(handler).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it("skips disabled shortcuts and unregisters on unmount", () => {
    const handler = vi.fn();
    const { unmount } = render(
      <ShortcutProvider>
        <Registers handler={handler} enabled={false} />
      </ShortcutProvider>,
    );
    fireEvent.keyDown(document.body, { key: "g" });
    fireEvent.keyDown(document.body, { key: "d" });
    expect(handler).not.toHaveBeenCalled();
    unmount();
  });

  it("supports controlled mode", () => {
    const onClose = vi.fn();
    render(
      <ShortcutProvider>
        <ShortcutHelp isOpen onClose={onClose} />
      </ShortcutProvider>,
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("matches and formats combos", () => {
    const press = (init: KeyboardEventInit) => new KeyboardEvent("keydown", init);
    expect(matchesCombo(press({ key: "k", ctrlKey: true }), "mod+k")).toBe(true);
    expect(matchesCombo(press({ key: "k", metaKey: true }), "mod+k")).toBe(true);
    expect(matchesCombo(press({ key: "k" }), "mod+k")).toBe(false);
    expect(matchesCombo(press({ key: "?", shiftKey: true }), "?")).toBe(true);
    expect(formatKeys("mod+k", false)).toEqual(["Ctrl", "K"]);
    expect(formatKeys("mod+k", true)).toEqual(["Cmd", "K"]);
    expect(formatKeys("g d")).toEqual(["G", "then", "D"]);
  });

  it("throws a clear error outside the provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    expect(() => render(<Registers handler={vi.fn()} />)).toThrow(/ShortcutProvider/);
    spy.mockRestore();
  });
});
