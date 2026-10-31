import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { useSuppliers } from "@/api/suppliers";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { useAuth } from "@/lib/auth-context";

import { SupplierBankPanel } from "./SupplierBankPanel";
import { SupplierDocumentsPanel } from "./SupplierDocumentsPanel";
import { SupplierPortalPanel } from "./SupplierPortalPanel";

const LOOKUP_SIZE = 100;

export function SupplierDetailPage() {
  const { id } = useParams();
  const supplierId = Number(id);
  const { hasPermission } = useAuth();
  // There is no single-supplier endpoint in use yet, so the name comes from the list the page already has.
  const { data, isLoading } = useSuppliers({ page: 1, page_size: LOOKUP_SIZE });
  const supplier = data?.items.find((item) => item.id === supplierId);

  if (!Number.isInteger(supplierId)) return <ErrorState message="This supplier does not exist." />;

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/suppliers"
          className="mb-2 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"
        >
          <ArrowLeft className="h-4 w-4" /> Suppliers
        </Link>
        <h1 className="text-2xl font-semibold text-slate-900">{supplier?.name ?? `Supplier ${supplierId}`}</h1>
        {isLoading && <LoadingState />}
      </div>
      <SupplierDocumentsPanel supplierId={supplierId} />
      {hasPermission("supplier:bank_details") && <SupplierBankPanel supplierId={supplierId} />}
      <SupplierPortalPanel supplierId={supplierId} />
    </div>
  );
}
