import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { BankDetails } from "@/api/supplierBank";
import { apiError } from "@/test/apiError";
import { mockGet, renderWithProviders } from "@/test/render";

import { SupplierBankPanel } from "./SupplierBankPanel";

function details(overrides: Partial<BankDetails>): BankDetails {
  return {
    id: 1,
    supplier_id: 3,
    status: "approved",
    bank_account_name: "Acme GmbH",
    bank_country: "DE",
    iban: "DE89370400440532013000",
    bic: null,
    bank_account_number: null,
    routing_number: null,
    requested_by: { id: 2, full_name: "Rita Requester" },
    requested_at: "2026-10-01T09:00:00Z",
    decided_by: null,
    decided_at: null,
    decision_comment: null,
    superseded_at: null,
    ...overrides,
  };
}

function serve(pending: BankDetails | null) {
  mockGet({
    "/suppliers/3/bank-details": { current: details({}), pending, history: [] },
  });
}

describe("SupplierBankPanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows account identifiers masked", async () => {
    serve(null);
    renderWithProviders(<SupplierBankPanel supplierId={3} />, { permissions: ["supplier:bank_details"] });

    expect(await screen.findByText("••••••••••••••••••3000")).toBeInTheDocument();
    expect(screen.queryByText(/DE8937/)).not.toBeInTheDocument();
  });

  it("does not let the requester approve their own change", async () => {
    serve(details({ id: 7, status: "pending", requested_by: { id: 1, full_name: "Me Myself" } }));
    renderWithProviders(<SupplierBankPanel supplierId={3} />, { permissions: ["supplier:bank_details"] });

    expect(await screen.findByText(/someone else has to approve/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve change" })).not.toBeInTheDocument();
  });

  it("lets another person approve and posts to the approve endpoint", async () => {
    serve(details({ id: 7, status: "pending" }));
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: details({ id: 7 }) });
    renderWithProviders(<SupplierBankPanel supplierId={3} />, { permissions: ["supplier:bank_details"] });

    fireEvent.click(await screen.findByRole("button", { name: "Approve change" }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith("/suppliers/3/bank-details/changes/7/approve", { comment: null }),
    );
  });

  it("shows the server's detail when approval is refused with 403", async () => {
    serve(details({ id: 7, status: "pending" }));
    vi.spyOn(apiClient, "post").mockRejectedValue(apiError(403, "You cannot approve a change you requested"));
    renderWithProviders(<SupplierBankPanel supplierId={3} />, { permissions: ["supplier:bank_details"] });

    fireEvent.click(await screen.findByRole("button", { name: "Approve change" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("You cannot approve a change you requested");
  });
});
