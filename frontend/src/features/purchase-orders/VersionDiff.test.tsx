import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { PurchaseOrderVersion, VersionChange } from "@/api/types";
import { person, purchaseOrder } from "@/test/fixtures";
import { mockGet, renderWithProviders } from "@/test/render";

import { VersionDiff } from "./VersionDiff";
import { VersionsPanel } from "./VersionsPanel";

const changes: VersionChange[] = [
  { kind: "field", field: "expected_delivery_date", label: "Expected delivery", from: null, to: "2026-12-15" },
  { kind: "line_added", label: "Plug", quantity: 4, unit_price: "2.5000", line_total: "10.00" },
  { kind: "line_removed", label: "Adapter", quantity: 1, unit_price: "8.0000", line_total: "8.00" },
  {
    kind: "line_changed",
    label: "Cable",
    changes: [{ field: "quantity", label: "Quantity", from: 10, to: 12 }],
    from_total: "50.00",
    to_total: "60.00",
  },
  { kind: "total", label: "Total", from: "50.00", to: "62.00" },
];

describe("VersionDiff", () => {
  it("renders each kind of change readably", () => {
    render(<VersionDiff changes={changes} currency="USD" />);

    expect(screen.getByText(/Expected delivery:/)).toBeInTheDocument();
    expect(screen.getByText("2026-12-15")).toBeInTheDocument();
    expect(screen.getByText("Added")).toBeInTheDocument();
    expect(screen.getByText(/4 × \$2\.50 = \$10\.00/)).toBeInTheDocument();
    expect(screen.getByText("Removed")).toBeInTheDocument();
    expect(screen.getByText(/Adapter/)).toBeInTheDocument();
    expect(screen.getByText("Changed")).toBeInTheDocument();
    expect(screen.getByText(/Quantity:/)).toBeInTheDocument();
    expect(screen.getByText("$62.00")).toBeInTheDocument();
  });

  it("says so when nothing changed", () => {
    render(<VersionDiff changes={[]} currency="USD" />);

    expect(screen.getByText("No changes from the version before.")).toBeInTheDocument();
  });
});

function version(overrides: Partial<PurchaseOrderVersion>): PurchaseOrderVersion {
  return {
    id: 31,
    po_id: 7,
    version: 2,
    status: "pending_approval",
    reason: "Price rise",
    created_by_person: person(1, "Me Myself"),
    created_at: "2026-10-21T09:00:00Z",
    decided_at: null,
    changes: [{ kind: "total", label: "Total", from: "50.00", to: "62.00" }],
    ...overrides,
  };
}

describe("VersionsPanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("lets the proposer withdraw a pending version", async () => {
    mockGet({ "/purchase-orders/7/versions": [version({})] });
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ data: version({ status: "rejected" }) });
    renderWithProviders(<VersionsPanel po={purchaseOrder({ status: "ordered" })} />);

    fireEvent.click(await screen.findByRole("button", { name: "Withdraw version 2" }));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/po-amendments/31/withdraw"));
  });

  it("hides Withdraw from anyone but the proposer and for versions already decided", async () => {
    mockGet({
      "/purchase-orders/7/versions": [
        version({ created_by_person: person(99, "Someone Else") }),
        version({ id: 32, version: 3, status: "applied" }),
      ],
    });
    renderWithProviders(<VersionsPanel po={purchaseOrder({ status: "ordered" })} />);

    const applied = (await screen.findByText("Version 3")).closest("li") as HTMLElement;
    expect(within(applied).getByText("applied")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Withdraw/ })).not.toBeInTheDocument();
  });
});
