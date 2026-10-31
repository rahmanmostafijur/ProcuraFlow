import { type ClassValue, clsx } from "clsx";

export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}

// Formatting follows the company settings; kept importable from here so existing call sites stay unchanged.
export {
  formatCurrency,
  formatDate,
  formatDateTime,
  formatMoney,
  formatCompactMoney,
  formatNumber,
  formatPercent,
  formatRelative,
} from "./formatting";
