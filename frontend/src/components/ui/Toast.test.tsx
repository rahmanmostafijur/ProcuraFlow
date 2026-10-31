import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "./ToastProvider";
import { type ToastOptions, useToast } from "./toast-context";

function Trigger({ options, legacy }: { options?: ToastOptions; legacy?: boolean }) {
  const { toast, showToast } = useToast();
  return <button onClick={() => (legacy ? showToast("Saved") : toast(options!))}>Fire</button>;
}

const regions = () => ({
  polite: document.querySelector<HTMLElement>('[aria-live="polite"]')!,
  assertive: document.querySelector<HTMLElement>('[aria-live="assertive"]')!,
});

function show(options: ToastOptions) {
  render(
    <ToastProvider>
      <Trigger options={options} />
    </ToastProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Fire" }));
}

describe("Toast system", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("keeps both live regions mounted before anything is shown", () => {
    render(
      <ToastProvider>
        <p>app</p>
      </ToastProvider>,
    );
    expect(regions().polite).toBeEmptyDOMElement();
    expect(regions().assertive).toBeEmptyDOMElement();
  });

  it("announces success politely and errors assertively", () => {
    show({ message: "Order approved", type: "success" });
    expect(regions().polite).toHaveTextContent("Success: Order approved");
    fireEvent.click(screen.getByRole("button", { name: "Fire" }));
    expect(regions().assertive).toBeEmptyDOMElement();
  });

  it("puts an error in the assertive region with its word", () => {
    show({ message: "Payment failed", type: "error" });
    expect(regions().assertive).toHaveTextContent("Error: Payment failed");
    expect(regions().polite).toBeEmptyDOMElement();
  });

  it("still supports the original showToast(message) call", () => {
    render(
      <ToastProvider>
        <Trigger legacy />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Fire" }));
    expect(regions().polite).toHaveTextContent("Saved");
  });

  it("dismisses itself after the duration", () => {
    show({ message: "Gone soon", durationMs: 3000 });
    act(() => void vi.advanceTimersByTime(2999));
    expect(screen.getByText("Gone soon")).toBeInTheDocument();
    act(() => void vi.advanceTimersByTime(2));
    expect(screen.queryByText("Gone soon")).not.toBeInTheDocument();
  });

  it("pauses while hovered and resumes with the time that was left", () => {
    show({ message: "Hover me", durationMs: 3000 });
    const toast = screen.getByText("Hover me").closest("div.pointer-events-auto")!;
    act(() => void vi.advanceTimersByTime(2000));
    fireEvent.mouseEnter(toast);
    act(() => void vi.advanceTimersByTime(60_000));
    expect(screen.getByText("Hover me")).toBeInTheDocument();
    fireEvent.mouseLeave(toast);
    act(() => void vi.advanceTimersByTime(900));
    expect(screen.getByText("Hover me")).toBeInTheDocument();
    act(() => void vi.advanceTimersByTime(200));
    expect(screen.queryByText("Hover me")).not.toBeInTheDocument();
  });

  it("stays until dismissed when the duration is 0 and can be closed by button", () => {
    show({ message: "Sticky", durationMs: 0 });
    act(() => void vi.advanceTimersByTime(120_000));
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));
    expect(screen.queryByText("Sticky")).not.toBeInTheDocument();
  });

  it("runs a toast action and dismisses it", () => {
    const onClick = vi.fn();
    show({ message: "Deleted", durationMs: 0, action: { label: "Undo", onClick } });
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(onClick).toHaveBeenCalled();
    expect(screen.queryByText("Deleted")).not.toBeInTheDocument();
  });

  it("stacks at most five, dropping the oldest", () => {
    render(
      <ToastProvider>
        <Trigger options={{ message: "Note", durationMs: 0 }} />
      </ToastProvider>,
    );
    for (let i = 0; i < 7; i++) fireEvent.click(screen.getByRole("button", { name: "Fire" }));
    expect(screen.getAllByRole("button", { name: "Dismiss notification" })).toHaveLength(5);
  });
});
