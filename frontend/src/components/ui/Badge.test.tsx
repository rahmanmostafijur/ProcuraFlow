import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Badge } from "./Badge";

describe("Badge", () => {
  it("renders its children", () => {
    render(<Badge status="draft">Draft</Badge>);
    expect(screen.getByText("Draft")).toBeInTheDocument();
  });

  it("falls back to a default style when status is unknown", () => {
    render(<Badge status="totally-unknown-status">Mystery</Badge>);
    const badge = screen.getByText("Mystery");
    expect(badge.className).toContain("bg-slate-100");
  });
});
