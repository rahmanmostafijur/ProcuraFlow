import { useCompanySettings } from "@/api/companySettings";

import { CurrenciesSection } from "./CurrenciesSection";
import { ExchangeRatesSection } from "./ExchangeRatesSection";
import { TaxRatesSection } from "./TaxRatesSection";

export function FinancePage() {
  const { data: settings } = useCompanySettings();
  const baseCurrency = settings?.base_currency_code ?? "USD";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Currencies &amp; tax</h1>
        <p className="text-sm text-slate-500">
          Reports and the dashboard are shown in {baseCurrency}, the base currency set in company settings.
        </p>
      </div>
      <CurrenciesSection baseCurrency={baseCurrency} />
      <ExchangeRatesSection baseCurrency={baseCurrency} />
      <TaxRatesSection />
    </div>
  );
}
