import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "./StatusBadge";
import { STATUS_TONES, statusLabel } from "./status-tones";

describe("StatusBadge", () => {
  it("always carries a word and a decorative icon", () => {
    render(<StatusBadge status="partially_received" />);
    const badge = screen.getByText("Partially received");
    expect(badge.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("maps statuses to token tones", () => {
    render(
      <>
        <StatusBadge status="received" />
        <StatusBadge status="rejected" />
        <StatusBadge status="submitted" />
      </>,
    );
    expect(screen.getByText("Received").className).toContain("bg-success-bg");
    expect(screen.getByText("Rejected").className).toContain("bg-danger-bg");
    expect(screen.getByText("Submitted").className).toContain("bg-warning-bg");
  });

  it("falls back to neutral with the status text for unknown values and allows a custom label", () => {
    render(
      <>
        <StatusBadge status="mystery" />
        <StatusBadge status="draft" label="Entwurf" />
      </>,
    );
    expect(screen.getByText("Mystery").className).toContain("text-text-secondary");
    expect(screen.getByText("Entwurf")).toBeInTheDocument();
  });

  it("covers every status the legacy badge knew", () => {
    for (const key of ["draft", "approved", "ordered", "expired", "released", "pending_approval"]) {
      expect(STATUS_TONES[key]).toBeDefined();
    }
    expect(statusLabel("expiring_soon")).toBe("Expiring soon");
  });
});
