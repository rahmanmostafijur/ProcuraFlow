import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useInvoices, type InvoiceStatus, type InvoiceSummary } from "@/api/supplierInvoices";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { Select } from "@/components/ui/Select";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useDebouncedValue } from "@/components/ui/use-debounced-value";
import { formatDate, formatMoney } from "@/lib/format";

import { INVOICE_STATUS_OPTIONS } from "./invoice-rules";
import { InvoiceTotals } from "./InvoiceTotals";

const PAGE_SIZE = 20;
const SEARCH_DELAY_MS = 300;

const COLUMNS: Column<InvoiceSummary>[] = [
  {
    header: "Invoice",
    accessor: (row) => <span className="font-medium text-text-primary">{row.invoice_number}</span>,
  },
  { header: "Supplier", accessor: (row) => row.supplier.name },
  { header: "Order", accessor: (row) => row.purchase_order.po_number },
  { header: "Status", accessor: (row) => <StatusBadge status={row.status} /> },
  { header: "Due", accessor: (row) => formatDate(row.due_date) },
  {
    header: "Total",
    isAmount: true,
    className: "tabular-nums",
    accessor: (row) => formatMoney(row.grand_total, row.currency_code),
  },
  {
    header: "Open",
    isAmount: true,
    className: "tabular-nums",
    accessor: (row) => formatMoney(row.open_amount, row.currency_code),
  },
];

export function InvoicesPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<InvoiceStatus | "">("");
  const [searchText, setSearchText] = useState("");
  const search = useDebouncedValue(searchText.trim(), SEARCH_DELAY_MS);

  const { data, isLoading, isError, refetch } = useInvoices({
    page,
    page_size: PAGE_SIZE,
    status: status || undefined,
    search: search || undefined,
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Supplier invoices" description="Match, approve and pay what suppliers bill us." />

      {data && <InvoiceTotals totals={data.totals} />}

      <Card>
        <div className="flex flex-wrap gap-3 border-b border-border p-4">
          <Input
            type="search"
            aria-label="Search invoices"
            placeholder="Search by invoice number or supplier"
            value={searchText}
            onChange={(event) => {
              setSearchText(event.target.value);
              setPage(1);
            }}
            className="w-72 max-w-full"
          />
          <Select
            aria-label="Filter by status"
            name="status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as InvoiceStatus | "");
              setPage(1);
            }}
            className="max-w-xs"
          >
            {INVOICE_STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
        <DataTable
          caption="Supplier invoices"
          columns={COLUMNS}
          rows={data?.items ?? []}
          keyExtractor={(row) => row.id}
          isLoading={isLoading}
          error={isError ? "The invoices could not be loaded." : null}
          onRetry={() => void refetch()}
          emptyTitle="No invoices found"
          emptyDescription="Invoices recorded against purchase orders appear here."
          onRowClick={(row) => void navigate(`/invoices/${row.id}`)}
          pagination={{ page, pageSize: PAGE_SIZE, total: data?.total ?? 0, onPageChange: setPage }}
        />
      </Card>
    </div>
  );
}
