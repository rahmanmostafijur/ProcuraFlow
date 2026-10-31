import { downloadFile } from "./downloads";

export interface ExportKind {
  key: string;
  label: string;
  description: string;
  path: string;
  filename: string;
  /** Status values the API accepts for this export; empty when it takes none worth offering. */
  statuses: string[];
}

export const EXPORT_KINDS: ExportKind[] = [
  {
    key: "quickbooks",
    label: "Bills for QuickBooks Online",
    description: "Supplier invoices in the QuickBooks Online bill import layout.",
    path: "/exports/bills/quickbooks.csv",
    filename: "bills-quickbooks.csv",
    statuses: ["approved", "paid"],
  },
  {
    key: "xero",
    label: "Bills for Xero",
    description: "Supplier invoices in the Xero bill import layout.",
    path: "/exports/bills/xero.csv",
    filename: "bills-xero.csv",
    statuses: ["approved", "paid"],
  },
  {
    key: "purchase-orders",
    label: "Purchase orders",
    description: "Every purchase order in the period.",
    path: "/exports/purchase-orders.csv",
    filename: "purchase-orders.csv",
    statuses: ["draft", "submitted", "approved", "ordered", "partially_received", "received", "cancelled"],
  },
  {
    key: "invoices",
    label: "Supplier invoices",
    description: "Every supplier invoice in the period.",
    path: "/exports/invoices.csv",
    filename: "invoices.csv",
    statuses: ["draft", "matched", "exception", "approved", "on_hold", "paid", "void"],
  },
  {
    key: "suppliers",
    label: "Suppliers",
    description: "The supplier list.",
    path: "/exports/suppliers.csv",
    filename: "suppliers.csv",
    statuses: [],
  },
];

export interface ExportFilters {
  date_from: string;
  date_to: string;
  status: string;
}

/** Only filters the person filled in are sent. */
export function exportParams(filters: ExportFilters): Record<string, string> {
  const params: Record<string, string> = {};
  if (filters.date_from) params.date_from = filters.date_from;
  if (filters.date_to) params.date_to = filters.date_to;
  if (filters.status) params.status = filters.status;
  return params;
}

export function downloadExport(kind: ExportKind, filters: ExportFilters): Promise<void> {
  return downloadFile(kind.path, kind.filename, exportParams(filters));
}
