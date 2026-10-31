import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";
import { IconButton } from "./IconButton";

describe("Button", () => {
  it("blocks clicks and announces busy while loading", () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Save
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("is not busy by default and honours disabled", () => {
    render(<Button disabled>Send</Button>);
    const button = screen.getByRole("button", { name: "Send" });
    expect(button).not.toHaveAttribute("aria-busy");
    expect(button).toBeDisabled();
  });

  it("uses the focus ring token and a semantic variant", () => {
    render(<Button variant="danger">Delete</Button>);
    const classes = screen.getByRole("button", { name: "Delete" }).className;
    expect(classes).toContain("focus-visible:ring-focus");
    expect(classes).toContain("bg-danger-solid");
  });
});

describe("IconButton", () => {
  it("is named by aria-label and hides the icon from assistive technology", () => {
    render(<IconButton aria-label="Close panel" icon={<svg data-testid="icon" />} />);
    const button = screen.getByRole("button", { name: "Close panel" });
    expect(button).toHaveAttribute("title", "Close panel");
    expect(screen.getByTestId("icon").parentElement).toHaveAttribute("aria-hidden", "true");
  });

  it("is disabled while loading", () => {
    render(<IconButton aria-label="Refresh" icon={<svg />} loading />);
    expect(screen.getByRole("button", { name: "Refresh" })).toBeDisabled();
  });
});
