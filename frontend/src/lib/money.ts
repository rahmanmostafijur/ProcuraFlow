/**
 * Display-side helpers for amounts the API has already computed.
 *
 * The server owns every calculation (rounding per line, tax, conversion). The browser only adds up figures that
 * are already rounded to the currency's decimals, so each value is moved to whole minor units before adding, which
 * keeps the sum exact; nothing here rounds a value that was not already rounded.
 */

const FALLBACK_DECIMALS = 2;

/** The number of decimals the currency is shown with (0 for JPY, 3 for BHD), from the runtime's currency data. */
export function currencyDecimals(currency: string): number {
  try {
    return (
      new Intl.NumberFormat("en-US", { style: "currency", currency }).resolvedOptions().maximumFractionDigits ??
      FALLBACK_DECIMALS
    );
  } catch {
    return FALLBACK_DECIMALS;
  }
}

/** Add decimal strings that already carry at most `decimals` decimals, returning an exact decimal string. */
export function sumAmounts(values: readonly string[], decimals: number): string {
  const scale = 10 ** decimals;
  const minorUnits = values.reduce((total, value) => total + Math.round(Number(value) * scale), 0);
  return (minorUnits / scale).toFixed(decimals);
}
