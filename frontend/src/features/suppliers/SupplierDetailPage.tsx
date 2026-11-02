import { useParams } from "react-router-dom";

import { useSupplier } from "@/api/suppliers";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingState } from "@/components/ui/LoadingState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Tabs, type TabItem } from "@/components/ui/Tabs";
import { useAuth } from "@/lib/auth-context";

import { SupplierBankPanel } from "./SupplierBankPanel";
import { SupplierDocumentsPanel } from "./SupplierDocumentsPanel";
import { SupplierPortalPanel } from "./SupplierPortalPanel";

export function SupplierDetailPage() {
  const { id } = useParams();
  const supplierId = Number(id);
  const { hasPermission } = useAuth();
  const { data: supplier, isLoading } = useSupplier(supplierId);

  if (!Number.isInteger(supplierId)) return <ErrorState message="This supplier does not exist." />;

  const tabs: TabItem[] = [
    { id: "documents", label: "Documents", content: <SupplierDocumentsPanel supplierId={supplierId} /> },
    ...(hasPermission("supplier:bank_details")
      ? [{ id: "bank", label: "Bank details", content: <SupplierBankPanel supplierId={supplierId} /> }]
      : []),
    { id: "portal", label: "Portal", content: <SupplierPortalPanel supplierId={supplierId} /> },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={supplier?.name ?? `Supplier ${supplierId}`}
        breadcrumbs={[{ label: "Suppliers", to: "/suppliers" }, { label: supplier?.name ?? `Supplier ${supplierId}` }]}
      />
      {isLoading && <LoadingState />}
      <Tabs label="Supplier sections" tabs={tabs} />
    </div>
  );
}
