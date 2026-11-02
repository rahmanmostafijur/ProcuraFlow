import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useCreateSupplier, useSuppliers, useUpdateSupplier, type SupplierInput } from "@/api/suppliers";
import type { Supplier } from "@/api/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { useToast } from "@/components/ui/toast-context";
import { extractErrorMessage } from "@/api/client";
import { useAuth } from "@/lib/auth-context";
import { formatDate } from "@/lib/utils";

import { SupplierFormDrawer } from "./SupplierFormDrawer";

const PAGE_SIZE = 10;

export function SuppliersPage() {
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const [page, setPage] = useState(1);
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState(() => searchParams.get("search") ?? "");
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [isDrawerOpen, setDrawerOpen] = useState(false);

  const { data, isLoading } = useSuppliers({ page, page_size: PAGE_SIZE, search: search || undefined });
  const createSupplier = useCreateSupplier();
  const updateSupplier = useUpdateSupplier();

  const canWrite = hasPermission("supplier:write");

  const columns: Column<Supplier>[] = [
    { header: "Name", accessor: (row) => <span className="font-medium text-text-primary">{row.name}</span> },
    { header: "Contact", accessor: (row) => row.contact_name ?? "—" },
    { header: "Email", accessor: (row) => row.email ?? "—" },
    { header: "Phone", accessor: (row) => row.phone ?? "—" },
    {
      header: "Status",
      accessor: (row) => (
        <StatusBadge status={row.is_active ? "active" : "inactive"} label={row.is_active ? "Active" : "Inactive"} />
      ),
    },
    { header: "Added", accessor: (row) => formatDate(row.created_at) },
    ...(canWrite
      ? [
          {
            header: "Documents & bank",
            accessor: (row: Supplier) => (
              <Link
                to={`/suppliers/${row.id}`}
                aria-label={`Manage ${row.name}`}
                className="text-brand hover:underline"
                onClick={(event) => event.stopPropagation()}
              >
                Manage
              </Link>
            ),
          },
        ]
      : []),
  ];

  const openCreate = () => {
    setEditingSupplier(null);
    setDrawerOpen(true);
  };

  const openEdit = (supplier: Supplier) => {
    if (!canWrite) return;
    setEditingSupplier(supplier);
    setDrawerOpen(true);
  };

  const handleSubmit = async (values: SupplierInput & { is_active?: boolean }) => {
    try {
      if (editingSupplier) {
        await updateSupplier.mutateAsync({ id: editingSupplier.id, ...values });
        showToast("Supplier updated");
      } else {
        await createSupplier.mutateAsync(values);
        showToast("Supplier created");
      }
      setDrawerOpen(false);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  return (
    <div>
      <PageHeader
        title="Suppliers"
        description="Manage supplier records and their purchasing history."
        secondaryActions={
          canWrite ? (
            <Link to="/suppliers/expiring-documents">
              <Button variant="secondary">Documents expiring soon</Button>
            </Link>
          ) : undefined
        }
        primaryAction={
          canWrite ? (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" /> New Supplier
            </Button>
          ) : undefined
        }
      />

      <Card>
        <div className="border-b border-border p-4">
          <Input
            placeholder="Search suppliers…"
            aria-label="Search suppliers"
            name="search"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            className="max-w-xs"
          />
        </div>
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          keyExtractor={(row) => row.id}
          isLoading={isLoading}
          emptyTitle="No suppliers found"
          emptyDescription="Try adjusting your search, or add a new supplier."
          onRowClick={canWrite ? openEdit : undefined}
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

      <SupplierFormDrawer
        isOpen={isDrawerOpen}
        onClose={() => setDrawerOpen(false)}
        supplier={editingSupplier}
        onSubmit={handleSubmit}
        isSubmitting={createSupplier.isPending || updateSupplier.isPending}
      />
    </div>
  );
}
