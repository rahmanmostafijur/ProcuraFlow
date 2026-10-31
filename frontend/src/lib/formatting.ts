// Kept so existing imports keep working; the implementation lives in ./format.
import { formatMoney } from "./format";

export * from "./format";

/** Amounts arrive from the API as decimal strings; they are only formatted here, never used for arithmetic. */
export const formatCurrency = formatMoney;
