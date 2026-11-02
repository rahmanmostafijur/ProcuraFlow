import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { THEME_STORAGE_KEY, ThemeProvider, useTheme } from "./theme";

function Probe() {
  const { mode, resolved, setMode } = useTheme();
  return (
    <div>
      <span data-testid="state">{`${mode}/${resolved}`}</span>
      <button onClick={() => setMode("dark")}>dark</button>
      <button onClick={() => setMode("system")}>system</button>
      <button onClick={() => setMode("light")}>light</button>
    </div>
  );
}

function mockSystemDark(matches: boolean) {
  const listeners = new Set<(event: MediaQueryListEvent) => void>();
  window.matchMedia = vi.fn().mockImplementation(() => ({
    matches,
    addEventListener: (_: string, fn: (event: MediaQueryListEvent) => void) => listeners.add(fn),
    removeEventListener: (_: string, fn: (event: MediaQueryListEvent) => void) => listeners.delete(fn),
  }));
  return (next: boolean) => listeners.forEach((fn) => fn({ matches: next } as MediaQueryListEvent));
}

const root = document.documentElement;

beforeEach(() => {
  window.localStorage.clear();
  root.removeAttribute("data-theme");
  root.classList.remove("dark");
  mockSystemDark(false);
});

afterEach(() => vi.restoreAllMocks());

describe("ThemeProvider", () => {
  it("defaults to following the system and leaves data-theme unset", () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("state")).toHaveTextContent("system/light");
    expect(root).not.toHaveAttribute("data-theme");
    expect(root).not.toHaveClass("dark");
  });

  it("applies and persists an explicit dark choice", () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );

    act(() => screen.getByText("dark").click());

    expect(root).toHaveAttribute("data-theme", "dark");
    expect(root).toHaveClass("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
  });

  it("restores the stored mode on load and ignores junk", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "dark");
    const first = render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("state")).toHaveTextContent("dark/dark");
    first.unmount();

    window.localStorage.setItem(THEME_STORAGE_KEY, "purple");
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("state")).toHaveTextContent("system/light");
  });

  it("in system mode leaves data-theme unset and follows the OS", () => {
    const setSystem = mockSystemDark(true);
    window.localStorage.setItem(THEME_STORAGE_KEY, "system");
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );

    expect(screen.getByTestId("state")).toHaveTextContent("system/dark");
    expect(root).not.toHaveAttribute("data-theme");
    expect(root).toHaveClass("dark");

    act(() => setSystem(false));

    expect(screen.getByTestId("state")).toHaveTextContent("system/light");
    expect(root).not.toHaveClass("dark");
  });

  it("still works when localStorage throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );

    act(() => screen.getByText("dark").click());

    expect(screen.getByTestId("state")).toHaveTextContent("dark/dark");
    expect(root).toHaveAttribute("data-theme", "dark");
  });

  it("useTheme outside the provider throws a clear error", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow("useTheme must be used inside ThemeProvider");
  });
});
