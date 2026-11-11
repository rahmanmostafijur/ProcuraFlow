import { Plus } from "lucide-react";
import { useState } from "react";

import { usePortalInvoices, type PortalInvoice } from "@/api/portal";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Pagination } from "@/components/ui/Pagination";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatCurrency, formatDate } from "@/lib/utils";

import { PortalInvoiceFilesModal } from "./PortalInvoiceFilesModal";
import { PortalInvoiceModal } from "./PortalInvoiceModal";

const PAGE_SIZE = 10;

export function PortalInvoicesPage() {
  const [page, setPage] = useState(1);
  const [isCreating, setCreating] = useState(false);
  const [filesFor, setFilesFor] = useState<PortalInvoice | null>(null);
  const { data, isLoading } = usePortalInvoices(page, PAGE_SIZE);

  const columns: Column<PortalInvoice>[] = [
    {
      header: "Invoice",
      accessor: (row) => <span className="font-medium text-text-primary">{row.invoice_number}</span>,
    },
    { header: "Order", accessor: (row) => row.po_number },
    { header: "Date", accessor: (row) => formatDate(row.invoice_date) },
    { header: "Total", accessor: (row) => formatCurrency(row.grand_total, row.currency_code) },
    { header: "Open", accessor: (row) => formatCurrency(row.open_amount, row.currency_code) },
    { header: "Status", accessor: (row) => <StatusBadge status={row.status} /> },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <PageHeader title="Your invoices" description="Send an invoice for an order; finance reviews it as a draft." />
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" /> New invoice
        </Button>
      </div>
      <Card>
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          keyExtractor={(row) => row.id}
          isLoading={isLoading}
          emptyTitle="No invoices yet"
          emptyDescription="Invoices you send appear here."
          onRowClick={setFilesFor}
        />
        {data && (
          <Pagination
            page={data.page}
            totalPages={data.total_pages}
            total={data.total}
            pageSize={data.page_size}
            onPageChange={setPage}
          />
        )}
      </Card>
      <PortalInvoiceModal isOpen={isCreating} onClose={() => setCreating(false)} />
      <PortalInvoiceFilesModal invoice={filesFor} onClose={() => setFilesFor(null)} />
    </div>
  );
}
