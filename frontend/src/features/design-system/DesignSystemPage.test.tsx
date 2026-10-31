import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { ThemeProvider } from "@/lib/theme";

import { DesignSystemPage } from "./DesignSystemPage";

beforeAll(() => {
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.classList.remove("dark");
  window.localStorage.clear();
});

function renderPage() {
  return render(
    <ThemeProvider>
      <ToastProvider>
        <MemoryRouter>
          <DesignSystemPage />
        </MemoryRouter>
      </ToastProvider>
    </ThemeProvider>,
  );
}

// The page mounts every component twice (current and forced dark), so a render is slow under a parallel run.
const SLOW = 30_000;

describe("DesignSystemPage", () => {
  it(
    "has a table of contents whose every anchor points at a section on the page",
    () => {
      const { container } = renderPage();
      const toc = screen.getAllByRole("navigation", { name: "Components" })[0];
      const links = within(toc).getAllByRole("link");
      expect(links.length).toBeGreaterThanOrEqual(8);
      for (const link of links) {
        const id = link.getAttribute("href")!.slice(1);
        expect(container.querySelector(`section#${id}`)).not.toBeNull();
      }
    },
    SLOW,
  );

  it(
    "shows each component family, with a forced dark copy of the themed blocks",
    () => {
      const { container } = renderPage();
      for (const title of ["Buttons", "Form controls", "Charts", "Tabs, stepper, page header and pagination"]) {
        expect(screen.getByRole("heading", { level: 2, name: title })).toBeInTheDocument();
      }
      expect(container.querySelectorAll(".dark.theme-dark").length).toBeGreaterThanOrEqual(6);
      // Every button variant appears in default, hover, focus, disabled and loading form.
      expect(screen.getAllByRole("button", { name: "Label" }).length).toBeGreaterThanOrEqual(4 * 4 * 2);
      expect(container.querySelectorAll("[aria-busy='true']").length).toBeGreaterThan(0);
      expect(screen.getAllByText("No purchase orders").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Could not load purchase orders.").length).toBeGreaterThan(0);
      expect(screen.getAllByRole("figure").length).toBeGreaterThanOrEqual(8);
    },
    SLOW,
  );

  it(
    "switches the page theme with the toggle",
    () => {
      renderPage();
      fireEvent.click(screen.getByRole("radio", { name: "Dark" }));
      expect(document.documentElement).toHaveAttribute("data-theme", "dark");
      fireEvent.click(screen.getByRole("radio", { name: "Light" }));
      expect(document.documentElement).toHaveAttribute("data-theme", "light");
    },
    SLOW,
  );

  it(
    "opens the command palette and the shortcut help from their buttons",
    () => {
      renderPage();
      fireEvent.click(screen.getByRole("button", { name: /Command palette/ }));
      expect(screen.getByRole("dialog", { name: "Command palette" })).toBeInTheDocument();
      fireEvent.keyDown(document, { key: "Escape" });
      fireEvent.click(screen.getByRole("button", { name: /Shortcut help/ }));
      expect(screen.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeInTheDocument();
    },
    SLOW,
  );

  it(
    "renders without console errors",
    () => {
      const error = vi.spyOn(console, "error").mockImplementation(() => undefined);
      renderPage();
      expect(error).not.toHaveBeenCalled();
      error.mockRestore();
    },
    SLOW,
  );
});
