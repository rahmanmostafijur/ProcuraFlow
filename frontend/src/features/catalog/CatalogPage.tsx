import { Plus } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useCatalog } from "@/api/catalog";
import type { CatalogItem } from "@/api/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/lib/auth-context";
import { formatCurrency, formatDate } from "@/lib/utils";

import { CatalogFormDrawer } from "./CatalogFormDrawer";

export function CatalogPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("catalog:manage");
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState(() => searchParams.get("search") ?? "");
  const [editing, setEditing] = useState<CatalogItem | null>(null);
  const [isDrawerOpen, setDrawerOpen] = useState(false);
  const { data, isLoading, isError } = useCatalog({ search: search || undefined });

  const columns: Column<CatalogItem>[] = [
    {
      header: "Product",
      accessor: (row) => (
        <div>
          <p className="font-medium text-text-primary">{row.product_name}</p>
          <p className="text-xs text-text-secondary">{row.product_sku}</p>
        </div>
      ),
    },
    { header: "Supplier", accessor: (row) => row.supplier_name },
    {
      header: "Contract price",
      accessor: (row) => formatCurrency(row.contract_price, row.currency_code),
      isAmount: true,
    },
    { header: "Currency", accessor: (row) => row.currency_code },
    { header: "Lead time", accessor: (row) => `${row.lead_time_days} days` },
    {
      header: "Valid",
      accessor: (row) =>
        row.valid_from || row.valid_until ? `${formatDate(row.valid_from)} – ${formatDate(row.valid_until)}` : "Always",
    },
    {
      header: "Status",
      accessor: (row) => (
        <StatusBadge
          status={row.is_current ? "active" : "inactive"}
          label={row.is_current ? "Current" : "Not current"}
        />
      ),
    },
    ...(canManage
      ? [
          {
            header: "",
            accessor: (row: CatalogItem) => (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`Edit ${row.product_name} from ${row.supplier_name}`}
                onClick={() => {
                  setEditing(row);
                  setDrawerOpen(true);
                }}
              >
                Edit
              </Button>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Catalog"
        description="Contract prices agreed with suppliers."
        primaryAction={
          canManage && (
            <Button
              onClick={() => {
                setEditing(null);
                setDrawerOpen(true);
              }}
            >
              <Plus className="h-4 w-4" /> New contract price
            </Button>
          )
        }
      />
      <Card>
        <div className="border-b border-border p-4">
          <Input
            placeholder="Search the catalog…"
            aria-label="Search the catalog"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="max-w-xs"
          />
        </div>
        {isError ? (
          <ErrorState message="The catalog could not be loaded." />
        ) : (
          <DataTable
            columns={columns}
            rows={data ?? []}
            keyExtractor={(row) => row.id}
            isLoading={isLoading}
            emptyTitle="No catalog items"
            emptyDescription="Try another search."
          />
        )}
      </Card>
      {canManage && <CatalogFormDrawer isOpen={isDrawerOpen} item={editing} onClose={() => setDrawerOpen(false)} />}
    </div>
  );
}
