export interface Permission {
  id: number;
  code: string;
  description: string | null;
}

export interface Role {
  id: number;
  name: string;
  description: string | null;
  permissions: Permission[];
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  role: Role;
  /** Only supplier-portal accounts have one. */
  supplier_id?: number | null;
  created_at: string;
}

export type DateFormat = "YYYY-MM-DD" | "MM/DD/YYYY" | "DD/MM/YYYY" | "DD.MM.YYYY";

export interface Branding {
  company_name: string;
  brand_color: string;
  logo_url: string | null;
}

export interface CompanySettings extends Branding {
  legal_name: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  region: string | null;
  postal_code: string | null;
  country_code: string | null;
  tax_id: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  base_currency_code: string;
  fiscal_year_start_month: number;
  date_format: DateFormat;
  timezone: string;
  po_number_prefix: string;
  invoice_tolerance_percent: string;
  default_payment_terms_days: number;
  /** Payer bank details are only sent to people who manage settings. */
  payer_iban?: string | null;
  payer_bic?: string | null;
  payer_routing_number?: string | null;
  payer_account_number?: string | null;
  ach_company_id?: string | null;
  updated_at: string;
}

export interface Supplier {
  id: number;
  name: string;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  country_code: string | null;
  tax_id: string | null;
  currency_code: string | null;
  payment_terms_days: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Currency {
  code: string;
  name: string;
  symbol: string;
  minor_units: number;
  is_active: boolean;
}

export interface ExchangeRate {
  id: number;
  base_currency_code: string;
  currency_code: string;
  rate: string;
  effective_date: string;
  created_at: string;
}

export type TaxType = "vat" | "sales_tax";

export interface TaxRate {
  id: number;
  name: string;
  percentage: string;
  tax_type: TaxType;
  is_inclusive: boolean;
  is_reverse_charge: boolean;
  region: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Category {
  id: number;
  name: string;
}

export interface Product {
  id: number;
  sku: string;
  name: string;
  category_id: number | null;
  unit: string;
  cost: string;
  minimum_stock: number;
  supplier_id: number | null;
  current_stock: number;
  is_active: boolean;
  category: Category | null;
  supplier: Supplier | null;
  created_at: string;
  updated_at: string;
}

export type POStatus = "draft" | "submitted" | "approved" | "ordered" | "partially_received" | "received" | "cancelled";

export interface POItem {
  id: number;
  product_id: number;
  quantity: number;
  unit_price: string;
  received_quantity: number;
  tax_rate_id: number | null;
  tax_name: string | null;
  tax_percent: string;
  tax_inclusive: boolean;
  reverse_charge: boolean;
  line_net: string;
  line_tax: string;
  line_total: string;
}

export interface PurchaseOrder {
  id: number;
  po_number: string;
  supplier: Supplier;
  status: POStatus;
  currency_code: string;
  cost_centre_id: number | null;
  purchase_request_id: number | null;
  // How many times the order was amended; 1 is the order as first approved.
  version: number;
  expected_delivery_date: string | null;
  notes: string | null;
  items: POItem[];
  creator: User;
  approver: User | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
  subtotal: string;
  tax_total: string;
  grand_total: string;
  // Locked at approval; null until then.
  exchange_rate: string | null;
  base_subtotal: string | null;
  base_tax_total: string | null;
  base_grand_total: string | null;
  total: string;
}

export type InventoryTransactionType = "receive" | "adjustment" | "po_receipt" | "opening_balance";

export interface InventoryTransaction {
  id: number;
  product_id: number;
  type: InventoryTransactionType;
  quantity_delta: number;
  resulting_stock: number;
  reference_po_id: number | null;
  reason: string | null;
  created_by: number;
  created_at: string;
}

export type DeliveryStatus = "pending" | "on_time" | "delayed" | "partial";

export interface Delivery {
  id: number;
  po_id: number;
  expected_date: string | null;
  actual_date: string | null;
  status: DeliveryStatus;
  ordered_quantity: number;
  received_quantity: number;
  created_at: string;
  updated_at: string;
}

export interface AuditLog {
  id: number;
  user_id: number | null;
  action: string;
  entity_type: string;
  entity_id: number | null;
  extra_data: Record<string, unknown> | null;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DashboardSummary {
  total_purchase_orders: number;
  pending_orders: number;
  completed_orders: number;
  supplier_count: number;
  inventory_value: string;
  low_stock_products: number;
  upcoming_deliveries: number;
}

export interface MonthlyTrendPoint {
  month: string;
  total_spend: string;
  order_count: number;
}

export interface RecentActivityItem {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number | null;
  created_at: string;
  user_name: string | null;
}

export interface SupplierPerformance {
  supplier_id: number;
  supplier_name: string;
  order_count: number;
  total_spend: string;
}

export interface DelayedDelivery {
  po_number: string;
  supplier_name: string;
  expected_date: string | null;
  actual_date: string | null;
  variance_days: number | null;
}

export interface Person {
  id: number;
  full_name: string;
}

// --- purchase requests -------------------------------------------------------------------------------------

export type PurchaseRequestStatus = "draft" | "submitted" | "approved" | "rejected" | "converted" | "cancelled";

export interface RequestLine {
  id: number;
  description: string;
  catalog_item_id: number | null;
  product_id: number | null;
  supplier_id: number | null;
  quantity: number;
  unit: string;
  estimated_unit_price: string;
  line_total: string;
  converted_po_id: number | null;
}

export interface PurchaseRequest {
  id: number;
  request_number: string;
  requester: Person;
  title: string;
  notes: string | null;
  cost_centre_id: number | null;
  currency_code: string;
  needed_by: string | null;
  status: PurchaseRequestStatus;
  estimated_total: string;
  base_estimated_total: string | null;
  submitted_at: string | null;
  decided_at: string | null;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
  lines: RequestLine[];
}

// --- approvals ---------------------------------------------------------------------------------------------

export type ApprovalDocumentType =
  "purchase_request" | "purchase_order" | "purchase_order_amendment" | "invoice_exception";
export type ApprovalStepStatus = "pending" | "approved" | "rejected" | "skipped";

export interface ApprovalStep {
  id: number;
  round: number;
  step_order: number;
  approver_role_id: number | null;
  required_permission: string | null;
  rule_name: string | null;
  amount_base: string;
  status: ApprovalStepStatus;
  decided_by: number | null;
  on_behalf_of: number | null;
  decided_at: string | null;
  comment: string | null;
  approver_label: string;
  decided_by_person: Person | null;
  on_behalf_of_person: Person | null;
}

export interface QueueItem {
  document_type: ApprovalDocumentType;
  document_id: number;
  // The order an order or amendment belongs to; null for other documents.
  po_id: number | null;
  label: string;
  title: string;
  amount_base: string;
  requester: Person;
  submitted_at: string | null;
  step_order: number;
  steps_total: number;
  rule_name: string | null;
  on_behalf_of: Person | null;
}

export interface QueuePage {
  items: QueueItem[];
  total: number;
}

export interface ApprovalRule {
  id: number;
  name: string;
  document_type: ApprovalDocumentType;
  min_amount: string;
  max_amount: string | null;
  is_active: boolean;
  steps: { step_order: number; approver_role_id: number }[];
}

export interface ApprovalLimit {
  id: number;
  user_id: number;
  document_type: ApprovalDocumentType;
  max_amount: string;
  updated_at: string;
}

export interface Delegation {
  id: number;
  delegator: Person;
  delegate: Person;
  starts_on: string;
  ends_on: string;
  revoked_at: string | null;
  created_at: string;
}

// --- budgets -----------------------------------------------------------------------------------------------

export interface CostCentre {
  id: number;
  code: string;
  name: string;
  manager_id: number | null;
  is_active: boolean;
}

export type BudgetHealth = "ok" | "warning" | "over";

export interface BudgetPosition {
  budget_id: number;
  cost_centre_id: number;
  cost_centre_code: string;
  cost_centre_name: string;
  fiscal_year: number;
  budget: string;
  spent: string;
  committed: string;
  remaining: string;
  utilisation_percent: string | null;
  health: BudgetHealth;
}

export interface BudgetChange {
  id: number;
  change_type: "created" | "adjusted" | "transfer_in" | "transfer_out";
  old_amount: string | null;
  new_amount: string;
  reason: string | null;
  transfer_id: number | null;
  changed_by: number;
  created_at: string;
}

export interface BudgetTransfer {
  id: number;
  from_budget_id: number;
  to_budget_id: number;
  from_label: string;
  to_label: string;
  amount: string;
  reason: string;
  status: "pending" | "approved" | "rejected";
  requested_by: Person;
  decided_by: Person | null;
  decided_at: string | null;
  decision_comment: string | null;
  created_at: string;
}

// --- catalog, attachments, order versions -------------------------------------------------------------------

export interface CatalogItem {
  id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  supplier_id: number;
  supplier_name: string;
  contract_price: string;
  currency_code: string;
  lead_time_days: number;
  valid_from: string | null;
  valid_until: string | null;
  is_active: boolean;
  is_current: boolean;
  created_at: string;
}

export type AttachmentParentType = "purchase_request" | "purchase_order";

export interface Attachment {
  id: number;
  parent_type: AttachmentParentType;
  parent_id: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_by: Person;
  created_at: string;
}

export interface VersionChange {
  kind: "field" | "line_added" | "line_removed" | "line_changed" | "total";
  label: string;
  field?: string;
  from?: string | number | null;
  to?: string | number | null;
  quantity?: number;
  unit_price?: string;
  line_total?: string;
  from_total?: string;
  to_total?: string;
  changes?: { field: string; label: string; from: string | number | null; to: string | number | null }[];
}

export interface PurchaseOrderVersion {
  id: number;
  po_id: number;
  version: number;
  status: "applied" | "pending_approval" | "rejected";
  reason: string;
  created_by_person: Person;
  created_at: string;
  decided_at: string | null;
  changes: VersionChange[];
}
