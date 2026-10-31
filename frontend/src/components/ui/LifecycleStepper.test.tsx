import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LifecycleStepper, type LifecycleStep } from "./LifecycleStepper";

const STEPS: LifecycleStep[] = [
  { id: "draft", label: "Draft", state: "done", at: "2026-10-01" },
  { id: "approval", label: "Approval", state: "current", description: "Waiting for Finance" },
  { id: "ordered", label: "Ordered", state: "upcoming" },
];

describe("LifecycleStepper", () => {
  it("is a named list with aria-current on the current step only", () => {
    render(<LifecycleStepper steps={STEPS} label="Request progress" />);
    const nav = screen.getByRole("navigation", { name: "Request progress" });
    const items = within(nav).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[1]).toHaveAttribute("aria-current", "step");
    expect(items[0]).not.toHaveAttribute("aria-current");
    expect(items[2]).not.toHaveAttribute("aria-current");
  });

  it("says each state in words, not only by colour", () => {
    render(<LifecycleStepper steps={STEPS} />);
    expect(screen.getByText("(completed)")).toBeInTheDocument();
    expect(screen.getByText("(current step)")).toBeInTheDocument();
    expect(screen.getByText("(not started)")).toBeInTheDocument();
    expect(screen.getByText("Waiting for Finance")).toBeInTheDocument();
  });

  it("marks a rejected step with a word and an icon", () => {
    render(
      <LifecycleStepper
        steps={[
          { id: "a", label: "Draft", state: "done" },
          { id: "b", label: "Approval", state: "rejected" },
        ]}
      />,
    );
    expect(screen.getByText("(rejected)")).toBeInTheDocument();
    expect(screen.getByText("Approval").closest("li")!.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("stacks vertically on small screens and supports a vertical layout", () => {
    const { rerender } = render(<LifecycleStepper steps={STEPS} />);
    expect(screen.getByRole("list").className).toContain("flex-col");
    expect(screen.getByRole("list").className).toContain("sm:flex-row");
    rerender(<LifecycleStepper steps={STEPS} orientation="vertical" />);
    expect(screen.getByRole("list").className).not.toContain("sm:flex-row");
  });
});
