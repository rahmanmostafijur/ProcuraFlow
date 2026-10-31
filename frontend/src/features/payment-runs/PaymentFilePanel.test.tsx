import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { PaymentFile } from "@/api/paymentRuns";
import { apiError } from "@/test/apiError";
import { renderWithProviders } from "@/test/render";

import { PaymentFilePanel } from "./PaymentFilePanel";

const file: PaymentFile = {
  id: 1,
  run_id: 5,
  run_number: "PR-0005",
  file_format: "sepa_pain001",
  filename: "PR-0005-sepa.xml",
  content_type: "application/xml",
  size_bytes: 900,
  sha256: "ab12",
  currency_code: "EUR",
  transaction_count: 2,
  total: "1200.00",
  created_by: { id: 1, full_name: "Me Myself" },
  created_at: "2026-11-01T10:00:00Z",
};

function notGenerated() {
  vi.spyOn(apiClient, "get").mockRejectedValue(apiError(404, "No payment file"));
}

describe("PaymentFilePanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("generates the file and then offers the download", async () => {
    notGenerated();
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: file });
    renderWithProviders(<PaymentFilePanel runId={5} />);

    fireEvent.click(await screen.findByRole("button", { name: "Generate payment file" }));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/payment-runs/5/file"));
    expect(await screen.findByText("PR-0005-sepa.xml")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Download file/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Generate payment file" })).not.toBeInTheDocument();
  });

  it("shows an existing file without offering to generate again", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({ data: file });
    renderWithProviders(<PaymentFilePanel runId={5} />);

    expect(await screen.findByText("SEPA credit transfer (pain.001)")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Generate payment file" })).not.toBeInTheDocument();
  });

  it("lists every missing bank detail when the API answers 422", async () => {
    notGenerated();
    vi.spyOn(apiClient, "post").mockRejectedValue(
      apiError(
        422,
        "Cannot export PR-0005: Company settings: the payer IBAN is not set | Acme (invoice INV-1): missing IBAN | Beta (invoice INV-2): no approved bank details",
      ),
    );
    renderWithProviders(<PaymentFilePanel runId={5} />);

    fireEvent.click(await screen.findByRole("button", { name: "Generate payment file" }));

    const alert = await screen.findByRole("alert");
    const items = within(alert).getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual([
      "Company settings: the payer IBAN is not set",
      "Acme (invoice INV-1): missing IBAN",
      "Beta (invoice INV-2): no approved bank details",
    ]);
  });

  it("shows other refusals as a message instead of a list", async () => {
    notGenerated();
    vi.spyOn(apiClient, "post").mockRejectedValue(apiError(409, "Only a released payment run can be exported"));
    renderWithProviders(<PaymentFilePanel runId={5} />);

    fireEvent.click(await screen.findByRole("button", { name: "Generate payment file" }));

    expect(await screen.findByText("Only a released payment run can be exported")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
