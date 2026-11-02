import { useCompanySettings } from "@/api/companySettings";

import { PageHeader } from "@/components/ui/PageHeader";

import { CurrenciesSection } from "./CurrenciesSection";
import { ExchangeRatesSection } from "./ExchangeRatesSection";
import { TaxRatesSection } from "./TaxRatesSection";

export function FinancePage() {
  const { data: settings } = useCompanySettings();
  const baseCurrency = settings?.base_currency_code ?? "USD";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Currencies & tax"
        description={`Reports and the dashboard are shown in ${baseCurrency}, the base currency set in company settings.`}
      />
      <CurrenciesSection baseCurrency={baseCurrency} />
      <ExchangeRatesSection baseCurrency={baseCurrency} />
      <TaxRatesSection />
    </div>
  );
}
