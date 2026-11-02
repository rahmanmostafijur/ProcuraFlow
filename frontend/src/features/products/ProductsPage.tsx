import { Plus } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { extractErrorMessage } from "@/api/client";
import { useCreateProduct, useProducts, useUpdateProduct, type ProductInput } from "@/api/products";
import type { Product } from "@/api/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { useToast } from "@/components/ui/toast-context";
import { useAuth } from "@/lib/auth-context";
import { cn, formatCurrency } from "@/lib/utils";

import { ProductFormDrawer } from "./ProductFormDrawer";

const PAGE_SIZE = 10;

export function ProductsPage() {
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const [page, setPage] = useState(1);
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState(() => searchParams.get("search") ?? "");
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [isDrawerOpen, setDrawerOpen] = useState(false);

  const { data, isLoading } = useProducts({
    page,
    page_size: PAGE_SIZE,
    search: search || undefined,
    low_stock_only: lowStockOnly || undefined,
  });
  const createProduct = useCreateProduct();
  const updateProduct = useUpdateProduct();

  const canWrite = hasPermission("product:write");

  const columns: Column<Product>[] = [
    { header: "SKU", accessor: (row) => <span className="font-mono text-xs text-text-secondary">{row.sku}</span> },
    { header: "Name", accessor: (row) => <span className="font-medium text-text-primary">{row.name}</span> },
    { header: "Category", accessor: (row) => row.category?.name ?? "—" },
    { header: "Supplier", accessor: (row) => row.supplier?.name ?? "—" },
    {
      header: "Stock",
      accessor: (row) => (
        <span
          className={cn(
            row.current_stock <= row.minimum_stock ? "font-semibold text-danger-fg" : "text-text-secondary",
          )}
        >
          {row.current_stock} {row.unit}
          {row.current_stock <= row.minimum_stock && " (low)"}
        </span>
      ),
    },
    { header: "Cost", accessor: (row) => formatCurrency(row.cost), isAmount: true },
    {
      header: "Status",
      accessor: (row) => (
        <StatusBadge status={row.is_active ? "active" : "inactive"} label={row.is_active ? "Active" : "Inactive"} />
      ),
    },
  ];

  const openCreate = () => {
    setEditingProduct(null);
    setDrawerOpen(true);
  };

  const openEdit = (product: Product) => {
    if (!canWrite) return;
    setEditingProduct(product);
    setDrawerOpen(true);
  };

  const handleSubmit = async (values: ProductInput & { is_active?: boolean }) => {
    try {
      if (editingProduct) {
        await updateProduct.mutateAsync({ id: editingProduct.id, ...values });
        showToast("Product updated");
      } else {
        await createProduct.mutateAsync(values);
        showToast("Product created");
      }
      setDrawerOpen(false);
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Products"
        description="Manage catalog items, stock thresholds, and cost."
        primaryAction={
          canWrite && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" /> New Product
            </Button>
          )
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-border p-4">
          <Input
            placeholder="Search products…"
            aria-label="Search products"
            name="search"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            className="max-w-xs"
          />
          <label className="flex items-center gap-2 text-sm text-text-secondary">
            <input
              type="checkbox"
              name="lowStockOnly"
              checked={lowStockOnly}
              onChange={(event) => {
                setLowStockOnly(event.target.checked);
                setPage(1);
              }}
              className="rounded border-border-strong text-brand focus:ring-focus"
            />
            Low stock only
          </label>
        </div>
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          keyExtractor={(row) => row.id}
          isLoading={isLoading}
          emptyTitle="No products found"
          emptyDescription="Try adjusting your filters, or add a new product."
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

      <ProductFormDrawer
        isOpen={isDrawerOpen}
        onClose={() => setDrawerOpen(false)}
        product={editingProduct}
        onSubmit={handleSubmit}
        isSubmitting={createProduct.isPending || updateProduct.isPending}
      />
    </div>
  );
}
