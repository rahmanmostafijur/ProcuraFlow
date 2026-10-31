import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Combobox, type ComboboxOption } from "./Combobox";

const OPTIONS: ComboboxOption[] = [
  { value: "1", label: "Acme Supplies" },
  { value: "2", label: "Apex Tools" },
  { value: "3", label: "Borealis Freight", disabled: true },
];

type Fetcher = (query: string, signal: AbortSignal) => Promise<ComboboxOption[]>;

function Harness({ fetchOptions, onPick }: { fetchOptions?: Fetcher; onPick?: (o: ComboboxOption | null) => void }) {
  const [value, setValue] = useState<ComboboxOption | null>(null);
  return (
    <Combobox
      aria-label="Supplier"
      value={value}
      onChange={(option) => {
        setValue(option);
        onPick?.(option);
      }}
      options={fetchOptions ? undefined : OPTIONS}
      fetchOptions={fetchOptions}
      debounceMs={0}
    />
  );
}

describe("Combobox", () => {
  it("exposes the combobox and listbox roles and starts collapsed", () => {
    render(<Harness />);
    const input = screen.getByRole("combobox", { name: "Supplier" });
    expect(input).toHaveAttribute("aria-expanded", "false");
    expect(input).toHaveAttribute("aria-autocomplete", "list");
  });

  it("moves the active descendant with the arrow keys and wraps", () => {
    render(<Harness />);
    const input = screen.getByRole("combobox");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(input).toHaveAttribute("aria-expanded", "true");
    const options = screen.getAllByRole("option");
    expect(input).toHaveAttribute("aria-activedescendant", options[0].id);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(input).toHaveAttribute("aria-activedescendant", options[1].id);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(input).toHaveAttribute("aria-activedescendant", options[0].id);
    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(input).toHaveAttribute("aria-activedescendant", options[2].id);
  });

  it("filters by what is typed and selects with Enter", () => {
    const onPick = vi.fn();
    render(<Harness onPick={onPick} />);
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "apex" } });
    expect(screen.getAllByRole("option")).toHaveLength(1);
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onPick).toHaveBeenCalledWith(OPTIONS[1]);
    expect(input).toHaveValue("Apex Tools");
    expect(input).toHaveAttribute("aria-expanded", "false");
  });

  it("closes on Escape and restores the chosen label", () => {
    render(<Harness />);
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "zzz" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(input).toHaveAttribute("aria-expanded", "false");
    expect(input).toHaveValue("");
  });

  it("shows the empty state and announces it", () => {
    render(<Harness />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "zzz" } });
    expect(screen.getAllByText("No results").length).toBeGreaterThan(0);
    expect(screen.getByRole("status")).toHaveTextContent("No results");
  });

  it("does not select a disabled option", () => {
    const onPick = vi.fn();
    render(<Harness onPick={onPick} />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "borealis" } });
    fireEvent.click(screen.getByRole("option", { name: /Borealis/ }));
    expect(onPick).not.toHaveBeenCalled();
  });

  it("loads options through the fetcher and shows a loading state first", async () => {
    let resolve: (options: ComboboxOption[]) => void = () => undefined;
    const fetchOptions = vi.fn<Fetcher>(() => new Promise((r) => (resolve = r)));
    render(<Harness fetchOptions={fetchOptions} />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "ac" } });
    expect(await screen.findAllByText("Loading…")).not.toHaveLength(0);
    resolve([OPTIONS[0]]);
    expect(await screen.findByRole("option", { name: "Acme Supplies" })).toBeInTheDocument();
    await waitFor(() => expect(fetchOptions).toHaveBeenLastCalledWith("ac", expect.any(AbortSignal)));
  });

  it("shows an error message when the fetcher fails", async () => {
    render(<Harness fetchOptions={() => Promise.reject(new Error("down"))} />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "x" } });
    expect((await screen.findAllByText("Could not load results")).length).toBeGreaterThan(0);
  });
});
