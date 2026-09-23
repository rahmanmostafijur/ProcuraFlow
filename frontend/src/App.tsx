import { Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { AuditLogPage } from "@/features/audit/AuditLogPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { DeliveriesPage } from "@/features/deliveries/DeliveriesPage";
import { InventoryPage } from "@/features/inventory/InventoryPage";
import { ProductsPage } from "@/features/products/ProductsPage";
import { PurchaseOrderDetailPage } from "@/features/purchase-orders/PurchaseOrderDetailPage";
import { PurchaseOrdersPage } from "@/features/purchase-orders/PurchaseOrdersPage";
import { ReportsPage } from "@/features/reports/ReportsPage";
import { SuppliersPage } from "@/features/suppliers/SuppliersPage";
import { UsersPage } from "@/features/users/UsersPage";
import { PermissionRoute } from "@/routes/PermissionRoute";
import { ProtectedRoute } from "@/routes/ProtectedRoute";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/suppliers" element={<SuppliersPage />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/purchase-orders" element={<PurchaseOrdersPage />} />
          <Route path="/purchase-orders/:id" element={<PurchaseOrderDetailPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/deliveries" element={<DeliveriesPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route element={<PermissionRoute permission="audit:read" />}>
            <Route path="/audit-log" element={<AuditLogPage />} />
          </Route>
          <Route element={<PermissionRoute permission="user:manage" />}>
            <Route path="/users" element={<UsersPage />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}
