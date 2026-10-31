import { Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { ApprovalSettingsPage } from "@/features/approval-settings/ApprovalSettingsPage";
import { ApprovalsPage } from "@/features/approvals/ApprovalsPage";
import { AuditLogPage } from "@/features/audit/AuditLogPage";
import { AcceptInvitationPage } from "@/features/auth/AcceptInvitationPage";
import { ForgotPasswordPage } from "@/features/auth/ForgotPasswordPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { ResetPasswordPage } from "@/features/auth/ResetPasswordPage";
import { EmailTemplatesPage } from "@/features/email-templates/EmailTemplatesPage";
import { ProfilePage } from "@/features/profile/ProfilePage";
import { BudgetsPage } from "@/features/budgets/BudgetsPage";
import { CatalogPage } from "@/features/catalog/CatalogPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { DeliveriesPage } from "@/features/deliveries/DeliveriesPage";
import { FinancePage } from "@/features/finance/FinancePage";
import { InventoryPage } from "@/features/inventory/InventoryPage";
import { ProductsPage } from "@/features/products/ProductsPage";
import { PurchaseOrderDetailPage } from "@/features/purchase-orders/PurchaseOrderDetailPage";
import { PurchaseOrdersPage } from "@/features/purchase-orders/PurchaseOrdersPage";
import { RequestDetailPage } from "@/features/requests/RequestDetailPage";
import { RequestsPage } from "@/features/requests/RequestsPage";
import { ReportsPage } from "@/features/reports/ReportsPage";
import { CompanySettingsPage } from "@/features/settings/CompanySettingsPage";
import { CompanySettingsProvider } from "@/lib/CompanySettingsProvider";
import { SuppliersPage } from "@/features/suppliers/SuppliersPage";
import { UsersPage } from "@/features/users/UsersPage";
import { PermissionRoute } from "@/routes/PermissionRoute";
import { ProtectedRoute } from "@/routes/ProtectedRoute";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/accept-invitation" element={<AcceptInvitationPage />} />
      <Route element={<ProtectedRoute />}>
        <Route
          element={
            <CompanySettingsProvider>
              <AppShell />
            </CompanySettingsProvider>
          }
        >
          <Route path="/" element={<DashboardPage />} />
          <Route path="/suppliers" element={<SuppliersPage />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/purchase-orders" element={<PurchaseOrdersPage />} />
          <Route path="/purchase-orders/:id" element={<PurchaseOrderDetailPage />} />
          <Route path="/requests" element={<RequestsPage />} />
          <Route path="/requests/:id" element={<RequestDetailPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route element={<PermissionRoute permission="budget:read" />}>
            <Route path="/budgets" element={<BudgetsPage />} />
          </Route>
          <Route element={<PermissionRoute permission="approval:manage" />}>
            <Route path="/approval-settings" element={<ApprovalSettingsPage />} />
          </Route>
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/deliveries" element={<DeliveriesPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route element={<PermissionRoute permission="audit:read" />}>
            <Route path="/audit-log" element={<AuditLogPage />} />
          </Route>
          <Route element={<PermissionRoute permission="user:manage" />}>
            <Route path="/users" element={<UsersPage />} />
          </Route>
          <Route element={<PermissionRoute permission="settings:manage" />}>
            <Route path="/settings" element={<CompanySettingsPage />} />
            <Route path="/settings/email-templates" element={<EmailTemplatesPage />} />
          </Route>
          <Route element={<PermissionRoute permission="finance:manage" />}>
            <Route path="/finance" element={<FinancePage />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}
