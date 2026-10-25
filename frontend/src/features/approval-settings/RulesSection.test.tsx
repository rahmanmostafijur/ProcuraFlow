import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import axios from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { ApprovalRule } from "@/api/types";
import { mockGet, renderWithProviders } from "@/test/render";

import { ApprovalSettingsPage } from "./ApprovalSettingsPage";

const roles = [
  { id: 1, name: "department_manager", description: null, permissions: [] },
  { id: 2, name: "finance", description: null, permissions: [] },
];

const rule: ApprovalRule = {
  id: 9,
  name: "Small requests",
  document_type: "purchase_request",
  min_amount: "0.0000",
  max_amount: "1000.0000",
  is_active: true,
  steps: [{ step_order: 1, approver_role_id: 1 }],
};

function serve() {
  mockGet({
    "/approval-rules": [rule],
    "/approval-limits": [
      { id: 4, user_id: 12, document_type: "purchase_order", max_amount: "5000.0000", updated_at: "x" },
    ],
    "/roles": roles,
  });
}

function overlapError() {
  return new axios.AxiosError("conflict", "409", undefined, undefined, {
    status: 409,
    data: { detail: "This amount band overlaps the rule 'Small requests'" },
  } as never);
}

describe("Approval settings", () => {
  afterEach(() => vi.restoreAllMocks());

  it("lists rules with their steps in order", async () => {
    serve();
    renderWithProviders(<ApprovalSettingsPage />, { permissions: ["approval:manage"] });

    const row = (await screen.findByText("Small requests")).closest("tr") as HTMLElement;
    expect(within(row).getByText("department manager")).toBeInTheDocument();
    expect(within(row).getByText("$1,000.00", { exact: false })).toBeInTheDocument();
  });

  it("creates a rule whose steps keep the order they were arranged in", async () => {
    serve();
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: rule });
    renderWithProviders(<ApprovalSettingsPage />, { permissions: ["approval:manage"] });
    await screen.findByText("Small requests");

    fireEvent.click(screen.getByRole("button", { name: "New rule" }));
    fireEvent.change(await screen.findByLabelText(/Rule name/), { target: { value: "Big orders" } });
    fireEvent.change(screen.getByLabelText("Applies to"), { target: { value: "purchase_order" } });
    fireEvent.change(screen.getByLabelText("From amount"), { target: { value: "1000" } });
    fireEvent.change(screen.getByLabelText("Role for step 1"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    fireEvent.change(screen.getByLabelText("Role for step 2"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Move step 2 up" }));
    fireEvent.click(screen.getByRole("button", { name: "Save rule" }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/approval-rules", {
        name: "Big orders",
        document_type: "purchase_order",
        min_amount: "1000",
        max_amount: null,
        is_active: true,
        steps: [{ approver_role_id: 2 }, { approver_role_id: 1 }],
      }),
    );
  });

  it("validates the band and every step before sending", async () => {
    serve();
    const post = vi.spyOn(apiClient, "post");
    renderWithProviders(<ApprovalSettingsPage />, { permissions: ["approval:manage"] });
    await screen.findByText("Small requests");

    fireEvent.click(screen.getByRole("button", { name: "New rule" }));
    fireEvent.change(await screen.findByLabelText(/Rule name/), { target: { value: "Odd" } });
    fireEvent.change(screen.getByLabelText("From amount"), { target: { value: "500" } });
    fireEvent.change(screen.getByLabelText(/Up to amount/), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: "Save rule" }));

    expect(await screen.findByText("The upper limit must be greater than the lower limit")).toBeInTheDocument();
    expect(screen.getByText("Choose a role", { selector: "p" })).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it("shows the API's overlap message inside the form and keeps it open", async () => {
    serve();
    vi.spyOn(apiClient, "post").mockRejectedValue(overlapError());
    renderWithProviders(<ApprovalSettingsPage />, { permissions: ["approval:manage"] });
    await screen.findByText("Small requests");

    fireEvent.click(screen.getByRole("button", { name: "New rule" }));
    fireEvent.change(await screen.findByLabelText(/Rule name/), { target: { value: "Clash" } });
    fireEvent.change(screen.getByLabelText("Role for step 1"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Save rule" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("This amount band overlaps the rule 'Small requests'");
    expect(screen.getByLabelText(/Rule name/)).toHaveValue("Clash");
  });

  it("asks before deleting a rule", async () => {
    serve();
    const del = vi.spyOn(apiClient, "delete").mockResolvedValue({ data: null });
    renderWithProviders(<ApprovalSettingsPage />, { permissions: ["approval:manage"] });

    fireEvent.click(await screen.findByRole("button", { name: "Delete Small requests" }));
    expect(del).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: "Delete rule" }));

    await waitFor(() => expect(del).toHaveBeenCalledWith("/approval-rules/9"));
  });

  it("sets and removes a limit", async () => {
    serve();
    const put = vi.spyOn(apiClient, "put").mockResolvedValue({ data: {} });
    const del = vi.spyOn(apiClient, "delete").mockResolvedValue({ data: null });
    renderWithProviders(<ApprovalSettingsPage />, { permissions: ["approval:manage"] });
    await screen.findByText("Approval limits");

    fireEvent.click(screen.getByRole("button", { name: "Set limit" }));
    expect(await screen.findByText("Choose a person")).toBeInTheDocument();
    expect(put).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Person (user number)"), { target: { value: "12" } });
    fireEvent.change(screen.getByLabelText("Limit amount"), { target: { value: "7500" } });
    fireEvent.click(screen.getByRole("button", { name: "Set limit" }));
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith("/approval-limits", {
        user_id: 12,
        document_type: "purchase_request",
        max_amount: "7500",
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: /Remove limit for user 12/ }));
    await waitFor(() => expect(del).toHaveBeenCalledWith("/approval-limits/4"));
  });
});
