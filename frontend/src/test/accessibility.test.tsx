import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeAll, describe, expect, it } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";
import { DesignSystemPage } from "@/features/design-system/DesignSystemPage";
import { ExportsPage } from "@/features/exports/ExportsPage";
import { LandingPage } from "@/features/landing/LandingPage";
import { ThemeProvider } from "@/lib/theme";
import { renderWithProviders } from "@/test/render";

import { blockingViolations } from "./axe";

// axe walks the whole design-system page, which is far larger than the 5 s default allows.
const AXE_ON_LARGE_PAGE_MS = 90_000;

beforeAll(() => {
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

describe("accessibility (axe: no serious or critical violations)", () => {
  it("catches a control without a name, so a clean result means something", async () => {
    const { container } = render(<input type="text" />);
    expect((await blockingViolations(container)).join("\n")).toContain("label");
  });

  it("landing page", async () => {
    const { container } = renderWithProviders(
      <ThemeProvider>
        <LandingPage />
      </ThemeProvider>,
    );
    expect(await blockingViolations(container)).toEqual([]);
  });

  it(
    "design system page, which shows every component in every state",
    async () => {
      const { container } = render(
        <ThemeProvider>
          <ToastProvider>
            <MemoryRouter>
              <DesignSystemPage />
            </MemoryRouter>
          </ToastProvider>
        </ThemeProvider>,
      );
      expect(await blockingViolations(container)).toEqual([]);
    },
    AXE_ON_LARGE_PAGE_MS,
  );

  it("exports page", async () => {
    const { container } = renderWithProviders(<ExportsPage />);
    expect(await blockingViolations(container)).toEqual([]);
  });
});
