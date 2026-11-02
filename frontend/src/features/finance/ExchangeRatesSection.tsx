import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { extractErrorMessage } from "@/api/client";
import { useAddExchangeRate, useCurrencies, useDeleteExchangeRate, useExchangeRates } from "@/api/finance";
import type { ExchangeRate } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Pagination } from "@/components/ui/Pagination";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/toast-context";
import { getFormattingConfig } from "@/lib/formatting";
import { formatDate } from "@/lib/utils";

const PAGE_SIZE = 10;

const schema = z.object({
  currency_code: z.string().min(1, "Choose a currency"),
  rate: z
    .string()
    .trim()
    .regex(/^\d+(\.\d{1,8})?$/, "A positive number with up to 8 decimals")
    .refine((value) => Number(value) > 0, "Must be greater than 0"),
  effective_date: z.string().min(1, "Choose a date"),
});

type FormValues = z.infer<typeof schema>;

/** Today's calendar date in the company time zone, as YYYY-MM-DD for a date input. */
function companyToday(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: getFormattingConfig().timeZone }).format(new Date());
}

export function ExchangeRatesSection({ baseCurrency }: { baseCurrency: string }) {
  const { showToast } = useToast();
  const [page, setPage] = useState(1);
  const { data: currencies } = useCurrencies(true);
  const { data: rates, isLoading } = useExchangeRates({ page, page_size: PAGE_SIZE });
  const addRate = useAddExchangeRate();
  const deleteRate = useDeleteExchangeRate();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { currency_code: "", rate: "", effective_date: companyToday() },
  });

  const onSubmit = async (values: FormValues) => {
    try {
      await addRate.mutateAsync(values);
      reset({ currency_code: values.currency_code, rate: "", effective_date: companyToday() });
      showToast("Rate saved");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const remove = async (rate: ExchangeRate) => {
    try {
      await deleteRate.mutateAsync(rate.id);
      showToast("Rate removed");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const columns: Column<ExchangeRate>[] = [
    { header: "Currency", accessor: (row) => <span className="font-mono font-medium">{row.currency_code}</span> },
    {
      header: `Rate (${baseCurrency} per 1)`,
      accessor: (row) => <span className="tabular-nums">{row.rate}</span>,
    },
    { header: "Effective from", accessor: (row) => formatDate(row.effective_date) },
    {
      header: "",
      accessor: (row) => (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-label={`Remove ${row.currency_code} rate from ${row.effective_date}`}
          onClick={() => void remove(row)}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      ),
    },
  ];

  const foreign = (currencies ?? []).filter((currency) => currency.code !== baseCurrency);

  return (
    <Card>
      <div className="border-b border-border p-4">
        <h2 className="text-base font-semibold text-text-primary">Exchange rates</h2>
        <p className="text-sm text-text-secondary">
          Entered by hand. An order is converted to {baseCurrency} when it is approved, using the latest rate on or
          before that day, and keeps that rate for good.
        </p>
      </div>
      <DataTable
        columns={columns}
        rows={rates?.items ?? []}
        keyExtractor={(row) => row.id}
        isLoading={isLoading}
        emptyTitle="No exchange rates yet"
        emptyDescription="Add a rate before approving orders in a foreign currency."
      />
      {rates && (
        <Pagination
          page={rates.page}
          totalPages={rates.total_pages}
          total={rates.total}
          pageSize={rates.page_size}
          onPageChange={setPage}
        />
      )}
      <form
        onSubmit={(event) => void handleSubmit(onSubmit)(event)}
        className="grid gap-3 border-t border-border p-4 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end"
      >
        <div>
          <Label htmlFor="rate_currency">Currency</Label>
          <Select id="rate_currency" error={errors.currency_code?.message} {...register("currency_code")}>
            <option value="">Choose…</option>
            {foreign.map((currency) => (
              <option key={currency.code} value={currency.code}>
                {currency.code} — {currency.name}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="rate_value">{`Rate (${baseCurrency} per 1)`}</Label>
          <Input id="rate_value" inputMode="decimal" error={errors.rate?.message} {...register("rate")} />
        </div>
        <div>
          <Label htmlFor="rate_date">Effective from</Label>
          <Input id="rate_date" type="date" error={errors.effective_date?.message} {...register("effective_date")} />
        </div>
        <Button type="submit" disabled={addRate.isPending}>
          <Plus className="h-4 w-4" /> Save rate
        </Button>
      </form>
    </Card>
  );
}
