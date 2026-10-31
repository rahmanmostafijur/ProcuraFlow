import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import { mockGet, renderWithProviders } from "@/test/render";

import { NotificationBell } from "./NotificationBell";

const notifications = [
  { id: 1, message: "PO-0007 needs your approval", is_read: false, created_at: "2026-10-30T09:00:00Z" },
  { id: 2, message: "PO-0006 was ordered", is_read: true, created_at: "2026-10-29T09:00:00Z" },
];

function serve(unread: number) {
  return mockGet({ "/notifications/unread-count": { unread }, "/notifications": notifications });
}

describe("NotificationBell", () => {
  afterEach(() => vi.restoreAllMocks());

  it("announces the unread count on the button", async () => {
    serve(3);
    renderWithProviders(<NotificationBell />);

    expect(await screen.findByRole("button", { name: "Notifications, 3 unread" })).toHaveTextContent("3");
  });

  it("has a plain label and no badge when nothing is unread", async () => {
    const get = serve(0);
    renderWithProviders(<NotificationBell />);

    await waitFor(() => expect(get).toHaveBeenCalledWith("/notifications/unread-count"));
    expect(screen.getByRole("button", { name: "Notifications" })).toHaveTextContent("");
  });

  it("lists recent notifications when opened and marks one read on click", async () => {
    serve(1);
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: undefined });
    renderWithProviders(<NotificationBell />);

    fireEvent.click(await screen.findByRole("button", { name: "Notifications, 1 unread" }));
    fireEvent.click(await screen.findByRole("button", { name: /PO-0007 needs your approval/ }));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/notifications/1/read"));
    expect(screen.getByText("PO-0006 was ordered")).toBeInTheDocument();
  });

  it("does not call the API when an already read notification is clicked", async () => {
    serve(1);
    const post = vi.spyOn(apiClient, "post");
    renderWithProviders(<NotificationBell />);

    fireEvent.click(await screen.findByRole("button", { name: "Notifications, 1 unread" }));
    fireEvent.click(await screen.findByRole("button", { name: /PO-0006 was ordered/ }));

    expect(post).not.toHaveBeenCalled();
  });

  it("marks everything read", async () => {
    serve(1);
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: { unread: 0 } });
    renderWithProviders(<NotificationBell />);

    fireEvent.click(await screen.findByRole("button", { name: "Notifications, 1 unread" }));
    fireEvent.click(await screen.findByRole("button", { name: "Mark all read" }));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/notifications/read-all"));
  });

  it("closes on Escape and returns focus to the bell", async () => {
    serve(1);
    renderWithProviders(<NotificationBell />);

    const bell = await screen.findByRole("button", { name: "Notifications, 1 unread" });
    fireEvent.click(bell);
    await screen.findByRole("region", { name: "Recent notifications" });

    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("region", { name: "Recent notifications" })).not.toBeInTheDocument();
    expect(bell).toHaveFocus();
  });
});
