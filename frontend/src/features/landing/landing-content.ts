import {
  BookMarked,
  Building2,
  CheckSquare,
  ClipboardList,
  ClipboardPenLine,
  FileSearch,
  FileText,
  Globe2,
  KeyRound,
  Landmark,
  PiggyBank,
  ScrollText,
  ShieldCheck,
  Timer,
  Truck,
  Users,
  Wallet,
  Warehouse,
  type LucideIcon,
} from "lucide-react";

export interface IconItem {
  title: string;
  body: string;
  icon: LucideIcon;
}

export const PROBLEMS: IconItem[] = [
  {
    title: "Requests in chat and spreadsheets",
    body: "Nobody can say who asked for what, who approved it or whether the money was ever available.",
    icon: ClipboardPenLine,
  },
  {
    title: "Three numbers for one purchase",
    body: "The order says one total, the invoice another and the ledger a third, and finance finds out at month end.",
    icon: FileSearch,
  },
  {
    title: "Paying for goods that never arrived",
    body: "Without a match between order, receipt and invoice, a short delivery is paid in full.",
    icon: Truck,
  },
];

export const HOW_STEPS: IconItem[] = [
  { title: "Request", body: "Anyone raises a request from the catalogue or free text.", icon: ClipboardPenLine },
  { title: "Approve", body: "Rules route it by amount and budget; delegates cover absences.", icon: CheckSquare },
  { title: "Order", body: "An approved request becomes a purchase order sent to the supplier.", icon: ClipboardList },
  { title: "Receive", body: "Warehouse staff book full or partial deliveries and stock updates.", icon: Warehouse },
  { title: "Match", body: "The invoice is checked against the order and the receipt line by line.", icon: FileText },
  { title: "Pay", body: "Matched invoices go into a payment run and are marked paid.", icon: Wallet },
];

export const FEATURES: IconItem[] = [
  {
    title: "Requests and approvals",
    body: "Multi-step rules by amount, delegation, and a full decision history.",
    icon: CheckSquare,
  },
  {
    title: "Purchase orders",
    body: "Amendments are versioned, so every change to an order stays visible.",
    icon: ClipboardList,
  },
  {
    title: "Deliveries and inventory",
    body: "Partial receipts, rejections, returns and stock levels per location.",
    icon: Warehouse,
  },
  {
    title: "Three-way matching",
    body: "Order, receipt and invoice compared, with duplicate-invoice detection.",
    icon: FileText,
  },
  {
    title: "Budgets",
    body: "Commitments and actuals against each budget, with a warning before it is exceeded.",
    icon: PiggyBank,
  },
  {
    title: "Supplier portal",
    body: "Suppliers see their own orders, upload documents and track invoices.",
    icon: Building2,
  },
  {
    title: "Multi-currency and tax",
    body: "Foreign-currency documents with rates and tax rules kept in one place.",
    icon: Globe2,
  },
  {
    title: "Catalogue",
    body: "Approved items and prices, so requests start from what you actually buy.",
    icon: BookMarked,
  },
  {
    title: "Payment runs and exports",
    body: "Batch payments, plus CSV exports of the records your accountant needs.",
    icon: Landmark,
  },
];

export const TRUST_POINTS: IconItem[] = [
  {
    title: "Money is never a float",
    body: "Every amount is stored and calculated as a decimal, so 0.1 plus 0.2 is exactly 0.3.",
    icon: Wallet,
  },
  {
    title: "Rounded half-up, per line",
    body: "Each line is rounded once, half-up, to the currency's minor unit. The document total is the sum of its lines.",
    icon: Timer,
  },
  {
    title: "The same total on every screen",
    body: "Dashboard, reports, budgets and exports read from the same figures, so they reconcile with each other.",
    icon: ScrollText,
  },
];

export const SECURITY_POINTS: IconItem[] = [
  { title: "Audit log", body: "Who changed what and when is recorded for every sensitive action.", icon: ScrollText },
  {
    title: "Role-based access",
    body: "Permissions per role decide which screens and actions a person sees.",
    icon: Users,
  },
  {
    title: "Token rotation",
    body: "Short-lived access tokens; the refresh token rotates and lives in an httpOnly cookie.",
    icon: KeyRound,
  },
  {
    title: "Throttling",
    body: "Sign-in and other sensitive endpoints are rate-limited against guessing.",
    icon: Timer,
  },
  {
    title: "Supplier isolation",
    body: "A supplier account can only reach its own orders, invoices and documents.",
    icon: ShieldCheck,
  },
];

export interface FaqItem {
  id: string;
  question: string;
  answer: string;
}

export const FAQS: FaqItem[] = [
  {
    id: "price",
    question: "Is there a monthly fee?",
    answer:
      "No. ProcuraFlow is self-hosted with a one-time licence. You pay for your own server or hosting, and there is no per-seat subscription.",
  },
  {
    id: "hosting",
    question: "Where does my data live?",
    answer:
      "On infrastructure you control. You run the application and its PostgreSQL database yourself, with Docker Compose or a hosted route, so your records stay in your environment.",
  },
  {
    id: "demo",
    question: "Can I try it before I buy?",
    answer:
      "Yes. The live demo has one-click sign-in for several roles, including a supplier. Demo data is reset regularly and some destructive actions are blocked.",
  },
  {
    id: "rounding",
    question: "How are amounts rounded?",
    answer:
      "Each line is rounded half-up to the currency's minor unit, and document totals are sums of rounded lines, so totals match what is printed on the document.",
  },
  {
    id: "suppliers",
    question: "Do suppliers need an account?",
    answer:
      "Only if you want them to use the portal. Invited suppliers see their own orders, invoices and documents and nothing else.",
  },
  {
    id: "export",
    question: "Can I get my data out?",
    answer: "Yes. Records can be exported as CSV, and the data sits in a standard PostgreSQL database you own.",
  },
];
