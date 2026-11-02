import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useUnsavedChangesWarning } from "./use-unsaved-changes";

function leave(): BeforeUnloadEvent {
  const event = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(event);
  return event;
}

describe("useUnsavedChangesWarning", () => {
  it("asks the browser to confirm leaving while the form is dirty", () => {
    renderHook(() => useUnsavedChangesWarning(true));

    expect(leave().defaultPrevented).toBe(true);
  });

  it("stays silent when nothing is edited", () => {
    renderHook(() => useUnsavedChangesWarning(false));

    expect(leave().defaultPrevented).toBe(false);
  });

  it("stops warning once the form is clean again or the page unmounts", () => {
    const { rerender, unmount } = renderHook(({ dirty }) => useUnsavedChangesWarning(dirty), {
      initialProps: { dirty: true },
    });

    rerender({ dirty: false });
    expect(leave().defaultPrevented).toBe(false);

    rerender({ dirty: true });
    unmount();
    expect(leave().defaultPrevented).toBe(false);
  });
});
