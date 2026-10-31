import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { SupplierDocument } from "@/api/supplierDocuments";
import { mockGet, renderWithProviders } from "@/test/render";

import { SupplierDocumentsPanel } from "./SupplierDocumentsPanel";

function document(overrides: Partial<SupplierDocument>): SupplierDocument {
  return {
    id: 1,
    supplier_id: 3,
    document_type: "insurance",
    issue_date: null,
    expiry_date: "2027-01-01",
    status: "valid",
    days_until_expiry: 60,
    filename: "policy.pdf",
    content_type: "application/pdf",
    size_bytes: 100,
    uploaded_by: { id: 1, full_name: "Me Myself" },
    created_at: "2026-11-01T00:00:00Z",
    ...overrides,
  };
}

const documents = [
  document({ id: 1, filename: "policy.pdf", status: "valid" }),
  document({ id: 2, filename: "w9.pdf", document_type: "w9", status: "expiring_soon", days_until_expiry: 5 }),
  // Expiry date in the future on purpose: the badge must follow the server's status, not the date.
  document({
    id: 3,
    filename: "iso.pdf",
    document_type: "iso_certificate",
    status: "expired",
    expiry_date: "2099-01-01",
  }),
];

describe("SupplierDocumentsPanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("labels each document with the status the server computed", async () => {
    mockGet({ "/suppliers/3/documents": documents });
    renderWithProviders(<SupplierDocumentsPanel supplierId={3} />);

    const rows = await screen.findAllByRole("row");
    expect(within(rows[1]).getByText("Valid")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Expiring soon")).toBeInTheDocument();
    expect(within(rows[3]).getByText("Expired")).toBeInTheDocument();
  });

  it("uploads a file with its type and dates as multipart form data", async () => {
    mockGet({ "/suppliers/3/documents": [] });
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: documents[0] });
    renderWithProviders(<SupplierDocumentsPanel supplierId={3} />);
    await screen.findByText("No documents on file.");

    fireEvent.change(screen.getByLabelText("Document type"), { target: { value: "vat_certificate" } });
    fireEvent.change(screen.getByLabelText("Expires on"), { target: { value: "2027-05-01" } });
    const file = new File(["%PDF"], "vat.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("File"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload document" }));

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    const [url, form] = post.mock.calls[0];
    expect(url).toBe("/suppliers/3/documents");
    const body = form as FormData;
    expect(body.get("document_type")).toBe("vat_certificate");
    expect(body.get("expiry_date")).toBe("2027-05-01");
    expect((body.get("file") as File).name).toBe("vat.pdf");
    expect(body.has("issue_date")).toBe(false);
  });

  it("refuses to upload without a file", async () => {
    mockGet({ "/suppliers/3/documents": [] });
    const post = vi.spyOn(apiClient, "post");
    renderWithProviders(<SupplierDocumentsPanel supplierId={3} />);

    fireEvent.click(await screen.findByRole("button", { name: "Upload document" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Choose a file to upload");
    expect(post).not.toHaveBeenCalled();
  });

  it("deletes a document", async () => {
    mockGet({ "/suppliers/3/documents": documents });
    const remove = vi.spyOn(apiClient, "delete").mockResolvedValue({ data: null });
    renderWithProviders(<SupplierDocumentsPanel supplierId={3} />);

    fireEvent.click(await screen.findByRole("button", { name: "Delete w9.pdf" }));

    await waitFor(() => expect(remove).toHaveBeenCalledWith("/suppliers/3/documents/2"));
  });
});
