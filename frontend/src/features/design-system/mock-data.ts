import type { ComboboxOption } from "@/components/ui/Combobox";
import type { SearchGroup } from "@/components/ui/command-palette/palette-types";

export interface OrderRow {
  id: number;
  number: string;
  supplier: string;
  status: string;
  amount: string;
  date: string;
}

export const ORDERS: OrderRow[] = [
  {
    id: 1,
    number: "PO-2026-00042",
    supplier: "Acme Supplies",
    status: "approved",
    amount: "12480.50",
    date: "2026-10-02",
  },
  {
    id: 2,
    number: "PO-2026-00043",
    supplier: "Borealis Freight",
    status: "submitted",
    amount: "980.00",
    date: "2026-10-03",
  },
  {
    id: 3,
    number: "PO-2026-00044",
    supplier: "Cobalt Tools",
    status: "partially_received",
    amount: "45210.00",
    date: "2026-10-05",
  },
  {
    id: 4,
    number: "PO-2026-00045",
    supplier: "Acme Supplies",
    status: "received",
    amount: "3150.75",
    date: "2026-10-07",
  },
  { id: 5, number: "PO-2026-00046", supplier: "Dunmore Office", status: "draft", amount: "420.00", date: "2026-10-08" },
  {
    id: 6,
    number: "PO-2026-00047",
    supplier: "Evergreen Packaging",
    status: "rejected",
    amount: "7800.00",
    date: "2026-10-09",
  },
  {
    id: 7,
    number: "PO-2026-00048",
    supplier: "Borealis Freight",
    status: "ordered",
    amount: "15990.00",
    date: "2026-10-11",
  },
  {
    id: 8,
    number: "PO-2026-00049",
    supplier: "Cobalt Tools",
    status: "cancelled",
    amount: "610.20",
    date: "2026-10-12",
  },
];

export const SUPPLIERS: ComboboxOption[] = [
  { value: "1", label: "Acme Supplies", description: "Net 30 · Berlin" },
  { value: "2", label: "Borealis Freight", description: "Net 45 · Oslo" },
  { value: "3", label: "Cobalt Tools", description: "Net 30 · Leeds" },
  { value: "4", label: "Dunmore Office", description: "Net 14 · Cork", disabled: true },
  { value: "5", label: "Evergreen Packaging", description: "Net 60 · Lyon" },
];

/** Resolves after a short delay and honours the abort signal, like a real request. */
export function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("aborted", "AbortError"));
    });
  });
}

export async function fetchSuppliers(query: string, signal: AbortSignal): Promise<ComboboxOption[]> {
  await wait(300, signal);
  const needle = query.toLowerCase();
  return SUPPLIERS.filter((supplier) => supplier.label.toLowerCase().includes(needle));
}

export const neverResolves = (_query: string, signal: AbortSignal): Promise<ComboboxOption[]> =>
  wait(60_000, signal).then(() => []);

export const alwaysFails = (): Promise<ComboboxOption[]> => Promise.reject(new Error("Showcase failure"));

export async function mockSearch(query: string, signal: AbortSignal): Promise<SearchGroup[]> {
  await wait(250, signal);
  const needle = query.toLowerCase();
  const orders = ORDERS.filter(
    (o) => o.number.toLowerCase().includes(needle) || o.supplier.toLowerCase().includes(needle),
  );
  const suppliers = SUPPLIERS.filter((s) => s.label.toLowerCase().includes(needle));
  return [
    {
      id: "orders",
      label: "Purchase orders",
      items: orders.slice(0, 4).map((o) => ({
        id: `po-${o.id}`,
        label: o.number,
        description: o.supplier,
        kind: "Order",
        href: `/purchase-orders/${o.id}`,
      })),
    },
    {
      id: "suppliers",
      label: "Suppliers",
      items: suppliers.slice(0, 3).map((s) => ({
        id: `s-${s.value}`,
        label: s.label,
        description: s.description,
        kind: "Supplier",
        href: `/suppliers/${s.value}`,
      })),
    },
  ].filter((group) => group.items.length > 0);
}

export const MONTHLY = [
  { month: "May", spend: 82000, budget: 90000, committed: 14000 },
  { month: "Jun", spend: 91000, budget: 90000, committed: 18000 },
  { month: "Jul", spend: 76000, budget: 90000, committed: 22000 },
  { month: "Aug", spend: 99000, budget: 95000, committed: 12000 },
  { month: "Sep", spend: 104000, budget: 95000, committed: 20000 },
  { month: "Oct", spend: 88000, budget: 95000, committed: 31000 },
];

export const CATEGORIES = [
  { name: "Facilities", value: 42000 },
  { name: "IT hardware", value: 31000 },
  { name: "Logistics", value: 18500 },
  { name: "Office", value: 9400 },
];

export const TREND_UP = [12, 14, 13, 17, 19, 24, 28];
export const TREND_DOWN = [30, 28, 29, 24, 22, 19, 15];
