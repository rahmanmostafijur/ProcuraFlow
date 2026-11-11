import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";

import { LoadingState } from "@/components/ui/LoadingState";
import { CompanySettingsProvider } from "@/lib/CompanySettingsProvider";
import { InternalRoute } from "@/routes/InternalRoute";
import { PermissionRoute } from "@/routes/PermissionRoute";
import { LandingRoute } from "@/routes/LandingRoute";
import { PortalRoute } from "@/routes/PortalRoute";
import { ProtectedRoute } from "@/routes/ProtectedRoute";

// The shell and the sign-in pages are loaded on demand: a visitor of the landing page needs none of them, and
// they bring the form, validation and navigation libraries with them.
const AppShell = lazy(() => import("@/components/layout/AppShell").then((m) => ({ default: m.AppShell })));
const AcceptInvitationPage = lazy(() =>
  import("@/features/auth/AcceptInvitationPage").then((m) => ({ default: m.AcceptInvitationPage })),
);
const ForgotPasswordPage = lazy(() =>
  import("@/features/auth/ForgotPasswordPage").then((m) => ({ default: m.ForgotPasswordPage })),
);
const LoginPage = lazy(() => import("@/features/auth/LoginPage").then((m) => ({ default: m.LoginPage })));
const ResetPasswordPage = lazy(() =>
  import("@/features/auth/ResetPasswordPage").then((m) => ({ default: m.ResetPasswordPage })),
);
const ApprovalSettingsPage = lazy(() =>
  import("@/features/approval-settings/ApprovalSettingsPage").then((m) => ({ default: m.ApprovalSettingsPage })),
);
const ApprovalsPage = lazy(() =>
  import("@/features/approvals/ApprovalsPage").then((m) => ({ default: m.ApprovalsPage })),
);
const AuditLogPage = lazy(() => import("@/features/audit/AuditLogPage").then((m) => ({ default: m.AuditLogPage })));
const ExportsPage = lazy(() => import("@/features/exports/ExportsPage").then((m) => ({ default: m.ExportsPage })));
const GdprPage = lazy(() => import("@/features/gdpr/GdprPage").then((m) => ({ default: m.GdprPage })));
const PaymentRunsPage = lazy(() =>
  import("@/features/payment-runs/PaymentRunsPage").then((m) => ({ default: m.PaymentRunsPage })),
);
const PortalDocumentsPage = lazy(() =>
  import("@/features/portal/PortalDocumentsPage").then((m) => ({ default: m.PortalDocumentsPage })),
);
const PortalInvoicesPage = lazy(() =>
  import("@/features/portal/PortalInvoicesPage").then((m) => ({ default: m.PortalInvoicesPage })),
);
const PortalOrdersPage = lazy(() =>
  import("@/features/portal/PortalOrdersPage").then((m) => ({ default: m.PortalOrdersPage })),
);
const PortalShell = lazy(() => import("@/features/portal/PortalShell").then((m) => ({ default: m.PortalShell })));
const ExpiringDocumentsPage = lazy(() =>
  import("@/features/suppliers/ExpiringDocumentsPage").then((m) => ({ default: m.ExpiringDocumentsPage })),
);
const SupplierDetailPage = lazy(() =>
  import("@/features/suppliers/SupplierDetailPage").then((m) => ({ default: m.SupplierDetailPage })),
);
const EmailTemplatesPage = lazy(() =>
  import("@/features/email-templates/EmailTemplatesPage").then((m) => ({ default: m.EmailTemplatesPage })),
);
const ProfilePage = lazy(() => import("@/features/profile/ProfilePage").then((m) => ({ default: m.ProfilePage })));
const BudgetsPage = lazy(() => import("@/features/budgets/BudgetsPage").then((m) => ({ default: m.BudgetsPage })));
const CatalogPage = lazy(() => import("@/features/catalog/CatalogPage").then((m) => ({ default: m.CatalogPage })));
const DashboardPage = lazy(() =>
  import("@/features/dashboard/DashboardPage").then((m) => ({ default: m.DashboardPage })),
);
const DeliveriesPage = lazy(() =>
  import("@/features/deliveries/DeliveriesPage").then((m) => ({ default: m.DeliveriesPage })),
);
const FinancePage = lazy(() => import("@/features/finance/FinancePage").then((m) => ({ default: m.FinancePage })));
const InventoryPage = lazy(() =>
  import("@/features/inventory/InventoryPage").then((m) => ({ default: m.InventoryPage })),
);
const ProductsPage = lazy(() => import("@/features/products/ProductsPage").then((m) => ({ default: m.ProductsPage })));
const InvoiceDetailPage = lazy(() =>
  import("@/features/invoices/InvoiceDetailPage").then((m) => ({ default: m.InvoiceDetailPage })),
);
const InvoicesPage = lazy(() => import("@/features/invoices/InvoicesPage").then((m) => ({ default: m.InvoicesPage })));
const PurchaseOrderDetailPage = lazy(() =>
  import("@/features/purchase-orders/PurchaseOrderDetailPage").then((m) => ({ default: m.PurchaseOrderDetailPage })),
);
const PurchaseOrdersPage = lazy(() =>
  import("@/features/purchase-orders/PurchaseOrdersPage").then((m) => ({ default: m.PurchaseOrdersPage })),
);
const RequestDetailPage = lazy(() =>
  import("@/features/requests/RequestDetailPage").then((m) => ({ default: m.RequestDetailPage })),
);
const RequestsPage = lazy(() => import("@/features/requests/RequestsPage").then((m) => ({ default: m.RequestsPage })));
const ReportsPage = lazy(() => import("@/features/reports/ReportsPage").then((m) => ({ default: m.ReportsPage })));
const CompanySettingsPage = lazy(() =>
  import("@/features/settings/CompanySettingsPage").then((m) => ({ default: m.CompanySettingsPage })),
);
const SuppliersPage = lazy(() =>
  import("@/features/suppliers/SuppliersPage").then((m) => ({ default: m.SuppliersPage })),
);
const UsersPage = lazy(() => import("@/features/users/UsersPage").then((m) => ({ default: m.UsersPage })));

// Development only. Vite replaces import.meta.env.DEV with a literal, so in a production build this is `null`,
// the dynamic import is dead code and the design-system chunk is never emitted.
const DesignSystemPage = import.meta.env.DEV
  ? lazy(() => import("@/features/design-system/DesignSystemPage").then((m) => ({ default: m.DesignSystemPage })))
  : null;

export function App() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-bg">
          <LoadingState />
        </div>
      }
    >
      <Routes>
        <Route path="/" element={<LandingRoute />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/accept-invitation" element={<AcceptInvitationPage />} />
        {DesignSystemPage && (
          <Route
            path="/design-system"
            element={
              <Suspense fallback={null}>
                <DesignSystemPage />
              </Suspense>
            }
          />
        )}
        <Route element={<ProtectedRoute />}>
          <Route element={<PortalRoute />}>
            <Route path="/portal" element={<PortalShell />}>
              <Route index element={<PortalOrdersPage />} />
              <Route path="invoices" element={<PortalInvoicesPage />} />
              <Route path="documents" element={<PortalDocumentsPage />} />
              <Route path="password" element={<ProfilePage />} />
            </Route>
          </Route>
          <Route element={<InternalRoute />}>
            <Route
              element={
                <CompanySettingsProvider>
                  <AppShell />
                </CompanySettingsProvider>
              }
            >
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/suppliers" element={<SuppliersPage />} />
              <Route element={<PermissionRoute permission="supplier:write" />}>
                <Route path="/suppliers/expiring-documents" element={<ExpiringDocumentsPage />} />
                <Route path="/suppliers/:id" element={<SupplierDetailPage />} />
              </Route>
              <Route path="/products" element={<ProductsPage />} />
              <Route element={<PermissionRoute permission="invoice:read" />}>
                <Route path="/invoices" element={<InvoicesPage />} />
                <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
              </Route>
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
              <Route element={<PermissionRoute permission="invoice:read" />}>
                <Route path="/payment-runs" element={<PaymentRunsPage />} />
              </Route>
              <Route element={<PermissionRoute permission="export:read" />}>
                <Route path="/exports" element={<ExportsPage />} />
              </Route>
              <Route element={<PermissionRoute permission="gdpr:manage" />}>
                <Route path="/gdpr" element={<GdprPage />} />
              </Route>
              <Route element={<PermissionRoute permission="finance:manage" />}>
                <Route path="/finance" element={<FinancePage />} />
              </Route>
            </Route>
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}
