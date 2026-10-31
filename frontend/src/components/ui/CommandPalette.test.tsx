import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CommandPalette } from "./CommandPalette";
import type { PaletteAction, SearchFetcher, SearchGroup } from "./command-palette/palette-types";
import { RECENT_STORAGE_KEY } from "./command-palette/recent-storage";
import { ShortcutProvider } from "./ShortcutProvider";

const GROUPS: SearchGroup[] = [
  {
    id: "po",
    label: "Purchase orders",
    items: [
      { id: "po-1", label: "PO-2026-00042", description: "Acme Supplies", href: "/purchase-orders/1", kind: "Order" },
      { id: "po-2", label: "PO-2026-00043", href: "/purchase-orders/2" },
    ],
  },
  { id: "sup", label: "Suppliers", items: [{ id: "s-1", label: "Acme Supplies", href: "/suppliers/1" }] },
];

function setup(search: SearchFetcher = () => Promise.resolve(GROUPS), actions: PaletteAction[] = []) {
  const onSelectItem = vi.fn();
  render(
    <ShortcutProvider>
      <CommandPalette search={search} actions={actions} onSelectItem={onSelectItem} debounceMs={0} />
    </ShortcutProvider>,
  );
  return { onSelectItem };
}

const openWithShortcut = (init: KeyboardEventInit = { key: "k", ctrlKey: true }) =>
  fireEvent.keyDown(document.body, init);

describe("CommandPalette", () => {
  beforeEach(() => window.localStorage.clear());

  it("opens with Ctrl+K and Cmd+K, focusing a labelled combobox, and closes with Escape", () => {
    setup();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    openWithShortcut();
    expect(screen.getByRole("dialog", { name: "Command palette" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Search or run a command" })).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    openWithShortcut({ key: "k", metaKey: true });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("opens even while typing in another field", () => {
    setup();
    const field = document.body.appendChild(document.createElement("input"));
    fireEvent.keyDown(field, { key: "k", ctrlKey: true });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    field.remove();
  });

  it("shows grouped results from the fetcher after typing, with option roles", async () => {
    const search = vi.fn<SearchFetcher>(() => Promise.resolve(GROUPS));
    setup(search);
    openWithShortcut();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "acme" } });
    expect(await screen.findByRole("group", { name: "Purchase orders" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Suppliers" })).toBeInTheDocument();
    expect(screen.getAllByRole("option")).toHaveLength(3);
    expect(search).toHaveBeenLastCalledWith("acme", expect.any(AbortSignal));
    expect(screen.getByRole("status")).toHaveTextContent("3 results");
  });

  it("navigates with the arrows, selects with Enter and remembers the choice", async () => {
    const { onSelectItem } = setup();
    openWithShortcut();
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "po" } });
    await screen.findAllByRole("option");
    expect(input).toHaveAttribute("aria-activedescendant", screen.getAllByRole("option")[0].id);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSelectItem).toHaveBeenCalledWith(GROUPS[0].items[1]);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(window.localStorage.getItem(RECENT_STORAGE_KEY)).toContain("po-2");
  });

  it("lists recent items first the next time it opens", async () => {
    setup();
    openWithShortcut();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "po" } });
    fireEvent.click(await screen.findByRole("option", { name: /PO-2026-00042/ }));
    openWithShortcut();
    const recent = screen.getByRole("group", { name: "Recent" });
    expect(recent).toHaveTextContent("PO-2026-00042");
  });

  it("filters and runs actions, and records them as recent", () => {
    const run = vi.fn();
    setup(
      () => Promise.resolve([]),
      [
        { id: "new-po", label: "Create purchase order", keywords: ["buy"], run },
        { id: "theme", label: "Toggle theme", run: vi.fn() },
      ],
    );
    openWithShortcut();
    expect(screen.getByRole("group", { name: "Actions" })).toBeInTheDocument();
    expect(screen.getAllByRole("option")).toHaveLength(2);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "buy" } });
    expect(screen.getAllByRole("option")).toHaveLength(1);
    fireEvent.keyDown(screen.getByRole("combobox"), { key: "Enter" });
    expect(run).toHaveBeenCalled();
    expect(window.localStorage.getItem(RECENT_STORAGE_KEY)).toContain("new-po");
  });

  it("shows searching, then the empty state", async () => {
    let finish: (g: SearchGroup[]) => void = () => undefined;
    const search = vi.fn<SearchFetcher>(() => new Promise((resolve) => (finish = resolve)));
    setup(search);
    openWithShortcut();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "zz" } });
    expect(screen.getAllByText("Searching…").length).toBeGreaterThan(0);
    await waitFor(() => expect(search).toHaveBeenCalled());
    act(() => finish([]));
    await waitFor(() => expect(screen.getAllByText("No results").length).toBeGreaterThan(0));
  });

  it("reports a failed search", async () => {
    setup(() => Promise.reject(new Error("503")));
    openWithShortcut();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "x" } });
    expect((await screen.findAllByText("Search failed. Try again.")).length).toBeGreaterThan(0);
  });

  it("still works when localStorage throws", async () => {
    const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const { onSelectItem } = setup();
    openWithShortcut();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "po" } });
    fireEvent.click(await screen.findByRole("option", { name: /PO-2026-00042/ }));
    expect(onSelectItem).toHaveBeenCalled();
    get.mockRestore();
    set.mockRestore();
  });

  it("ignores corrupt stored data", () => {
    window.localStorage.setItem(RECENT_STORAGE_KEY, '[{"type":"bogus"},"x",{"type":"item","item":{"id":1}}]');
    setup();
    openWithShortcut();
    expect(screen.queryByRole("group", { name: "Recent" })).not.toBeInTheDocument();
  });
});
