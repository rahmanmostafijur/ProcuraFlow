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

export interface User {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  role: Role;
  created_at: string;
}

export interface Supplier {
  id: number;
  name: string;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
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

export type POStatus =
  | "draft"
  | "submitted"
  | "approved"
  | "ordered"
  | "partially_received"
  | "received"
  | "cancelled";

export interface POItem {
  id: number;
  product_id: number;
  quantity: number;
  unit_price: string;
  received_quantity: number;
}

export interface PurchaseOrder {
  id: number;
  po_number: string;
  supplier: Supplier;
  status: POStatus;
  expected_delivery_date: string | null;
  notes: string | null;
  items: POItem[];
  creator: User;
  approver: User | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
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
