import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { extractErrorMessage } from "@/api/client";
import { useCreateRequest, useRequests, type PurchaseRequestInput } from "@/api/purchaseRequests";
import type { PurchaseRequest, PurchaseRequestStatus } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { ErrorState } from "@/components/ui/ErrorState";
import { Label } from "@/components/ui/Label";
import { Pagination } from "@/components/ui/Pagination";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/toast-context";
import { useAuth } from "@/lib/auth-context";
import { formatCurrency, formatDate } from "@/lib/utils";

import { RequestFormModal } from "./RequestFormModal";

const PAGE_SIZE = 10;
const STATUSES: PurchaseRequestStatus[] = ["draft", "submitted", "approved", "rejected", "converted", "cancelled"];

export function RequestsPage() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const canSeeAll = hasPermission("request:read_all");
  const canCreate = hasPermission("request:create");
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState<PurchaseRequestStatus | "">("");
  const [mineOnly, setMineOnly] = useState(false);
  const [isFormOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useRequests({
    page,
    page_size: PAGE_SIZE,
    status: status || undefined,
    mine: canSeeAll && mineOnly ? true : undefined,
  });
  const createRequest = useCreateRequest();

  const handleCreate = async (input: PurchaseRequestInput) => {
    try {
      const created = await createRequest.mutateAsync(input);
      showToast("Request saved as a draft");
      setFormOpen(false);
      void navigate(`/requests/${created.id}`);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const columns: Column<PurchaseRequest>[] = [
    {
      header: "Number",
      accessor: (row) => (
        <Link to={`/requests/${row.id}`} className="font-medium text-brand-700 hover:underline">
          {row.request_number}
        </Link>
      ),
    },
    { header: "Title", accessor: (row) => row.title },
    { header: "Requester", accessor: (row) => row.requester.full_name },
    { header: "Status", accessor: (row) => <Badge status={row.status}>{row.status}</Badge> },
    {
      header: "Estimated total",
      accessor: (row) => <span className="tabular-nums">{formatCurrency(row.estimated_total, row.currency_code)}</span>,
    },
    { header: "Needed by", accessor: (row) => formatDate(row.needed_by) },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Requests</h1>
          <p className="text-sm text-slate-500">Ask for something to be bought; approved requests become orders.</p>
        </div>
        {canCreate && (
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="h-4 w-4" /> New request
          </Button>
        )}
      </div>

      <Card>
        <div className="flex flex-wrap items-end gap-4 border-b border-slate-200 p-4">
          <div className="w-48">
            <Label htmlFor="request_status_filter">Status</Label>
            <Select
              id="request_status_filter"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as PurchaseRequestStatus | "");
                setPage(1);
              }}
            >
              <option value="">All statuses</option>
              {STATUSES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
          </div>
          {canSeeAll && (
            <label className="flex items-center gap-2 pb-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={mineOnly}
                onChange={(event) => {
                  setMineOnly(event.target.checked);
                  setPage(1);
                }}
              />
              Mine
            </label>
          )}
        </div>
        {isError ? (
          <ErrorState message="Requests could not be loaded." />
        ) : (
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            keyExtractor={(row) => row.id}
            isLoading={isLoading}
            emptyTitle="No requests found"
            emptyDescription={canCreate ? "Raise a new request to get started." : undefined}
          />
        )}
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

      <RequestFormModal
        isOpen={isFormOpen}
        isSubmitting={createRequest.isPending}
        onClose={() => setFormOpen(false)}
        onSubmit={handleCreate}
      />
    </div>
  );
}
