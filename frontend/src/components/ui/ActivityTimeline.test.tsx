import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ActivityTimeline, type ActivityEvent } from "./ActivityTimeline";

const NOW = new Date("2026-10-20T12:00:00Z");
const EVENTS: ActivityEvent[] = [
  { id: 1, actor: "Rita Requester", action: "submitted the request", at: "2026-10-18T12:00:00Z" },
  { id: 2, actor: "Alex Approver", action: "rejected it", at: "2026-10-20T09:00:00Z", comment: "Over budget" },
];

describe("ActivityTimeline", () => {
  it("lists events newest first with actor, relative time and a title holding the exact time", () => {
    render(<ActivityTimeline events={EVENTS} now={NOW} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Alex Approver rejected it");
    expect(items[1]).toHaveTextContent("Rita Requester submitted the request");
    const time = screen.getByText("3 hours ago");
    expect(time.tagName).toBe("TIME");
    expect(time).toHaveAttribute("dateTime", "2026-10-20T09:00:00Z");
    expect(time).toHaveAttribute("title");
    expect(screen.getByText("Over budget")).toBeInTheDocument();
  });

  it("can show oldest first", () => {
    render(<ActivityTimeline events={EVENTS} now={NOW} newestFirst={false} />);
    expect(screen.getAllByRole("listitem")[0]).toHaveTextContent("Rita Requester");
  });

  it("shows an empty message", () => {
    render(<ActivityTimeline events={[]} />);
    expect(screen.getByText("No activity yet.")).toBeInTheDocument();
  });

  it("has no composer unless a handler is given", () => {
    render(<ActivityTimeline events={EVENTS} />);
    expect(screen.queryByLabelText("Add a comment")).not.toBeInTheDocument();
  });

  it("posts a trimmed comment and clears the box", async () => {
    const onAddComment = vi.fn(() => Promise.resolve());
    render(<ActivityTimeline events={[]} onAddComment={onAddComment} />);
    const box = screen.getByLabelText("Add a comment");
    const post = screen.getByRole("button", { name: "Post comment" });
    expect(post).toBeDisabled();
    fireEvent.change(box, { target: { value: "  Looks fine  " } });
    expect(post).toBeEnabled();
    fireEvent.click(post);
    await waitFor(() => expect(box).toHaveValue(""));
    expect(onAddComment).toHaveBeenCalledWith("Looks fine");
  });

  it("keeps the text and explains when posting fails", async () => {
    render(<ActivityTimeline events={[]} onAddComment={() => Promise.reject(new Error("500"))} />);
    const box = screen.getByLabelText("Add a comment");
    fireEvent.change(box, { target: { value: "Try" } });
    fireEvent.click(screen.getByRole("button", { name: "Post comment" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be posted");
    expect(box).toHaveValue("Try");
    expect(box).toHaveAttribute("aria-invalid", "true");
  });
});
