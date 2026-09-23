import { Plus } from "lucide-react";
import { useState } from "react";

import { extractErrorMessage } from "@/api/client";
import { useCreateProduct, useProducts, useUpdateProduct, type ProductInput } from "@/api/products";
import type { Product } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
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
  const [search, setSearch] = useState("");
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
    { header: "SKU", accessor: (row) => <span className="font-mono text-xs text-slate-500">{row.sku}</span> },
    { header: "Name", accessor: (row) => <span className="font-medium text-slate-900">{row.name}</span> },
    { header: "Category", accessor: (row) => row.category?.name ?? "—" },
    { header: "Supplier", accessor: (row) => row.supplier?.name ?? "—" },
    {
      header: "Stock",
      accessor: (row) => (
        <span className={cn(row.current_stock <= row.minimum_stock ? "font-semibold text-red-600" : "text-slate-700")}>
          {row.current_stock} {row.unit}
          {row.current_stock <= row.minimum_stock && " (low)"}
        </span>
      ),
    },
    { header: "Cost", accessor: (row) => formatCurrency(row.cost) },
    {
      header: "Status",
      accessor: (row) => (
        <Badge status={row.is_active ? "active" : "inactive"}>{row.is_active ? "Active" : "Inactive"}</Badge>
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Products</h1>
          <p className="text-sm text-slate-500">Manage catalog items, stock thresholds, and cost.</p>
        </div>
        {canWrite && (
          <Button onClick={openCreate}>
            <Plus className="h-4 w-4" /> New Product
          </Button>
        )}
      </div>

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 p-4">
          <Input
            placeholder="Search products…"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            className="max-w-xs"
          />
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={lowStockOnly}
              onChange={(event) => {
                setLowStockOnly(event.target.checked);
                setPage(1);
              }}
              className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
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
