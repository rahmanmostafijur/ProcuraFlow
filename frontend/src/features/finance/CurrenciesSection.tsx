import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { extractErrorMessage } from "@/api/client";
import { useCreateCurrency, useCurrencies, useUpdateCurrency } from "@/api/finance";
import type { Currency } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { useToast } from "@/components/ui/toast-context";

const schema = z.object({
  code: z
    .string()
    .trim()
    .regex(/^[A-Za-z]{3}$/, "Three letters, e.g. CHF"),
  name: z.string().trim().min(1, "Name is required").max(100),
  symbol: z.string().trim().min(1, "Symbol is required").max(8),
  minor_units: z.coerce.number().int("Whole number").min(0).max(4),
});

type FormValues = z.infer<typeof schema>;

export function CurrenciesSection({ baseCurrency }: { baseCurrency: string }) {
  const { showToast } = useToast();
  const { data: currencies, isLoading } = useCurrencies();
  const createCurrency = useCreateCurrency();
  const updateCurrency = useUpdateCurrency();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { code: "", name: "", symbol: "", minor_units: 2 },
  });

  const onSubmit = async (values: FormValues) => {
    try {
      await createCurrency.mutateAsync({ ...values, code: values.code.toUpperCase() });
      reset();
      showToast("Currency added");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const toggle = async (currency: Currency) => {
    try {
      await updateCurrency.mutateAsync({ code: currency.code, is_active: !currency.is_active });
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const columns: Column<Currency>[] = [
    { header: "Code", accessor: (row) => <span className="font-mono font-medium text-slate-900">{row.code}</span> },
    { header: "Name", accessor: (row) => row.name },
    { header: "Symbol", accessor: (row) => row.symbol },
    { header: "Decimals", accessor: (row) => row.minor_units },
    {
      header: "Status",
      accessor: (row) =>
        row.code === baseCurrency ? (
          <Badge status="active">Base currency</Badge>
        ) : (
          <Badge status={row.is_active ? "active" : "inactive"}>{row.is_active ? "Active" : "Off"}</Badge>
        ),
    },
    {
      header: "",
      accessor: (row) =>
        row.code === baseCurrency ? null : (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label={`${row.is_active ? "Switch off" : "Switch on"} ${row.code}`}
            onClick={() => void toggle(row)}
          >
            {row.is_active ? "Switch off" : "Switch on"}
          </Button>
        ),
    },
  ];

  return (
    <Card>
      <div className="border-b border-slate-200 p-4">
        <h2 className="text-base font-semibold text-slate-900">Currencies</h2>
        <p className="text-sm text-slate-500">Only active currencies can be chosen on purchase orders and suppliers.</p>
      </div>
      <DataTable columns={columns} rows={currencies ?? []} keyExtractor={(row) => row.code} isLoading={isLoading} />
      <form
        onSubmit={(event) => void handleSubmit(onSubmit)(event)}
        className="grid gap-3 border-t border-slate-200 p-4 sm:grid-cols-[6rem_1fr_6rem_6rem_auto] sm:items-end"
      >
        <div>
          <Label htmlFor="currency_code">Code</Label>
          <Input id="currency_code" error={errors.code?.message} {...register("code")} />
        </div>
        <div>
          <Label htmlFor="currency_name">Currency name</Label>
          <Input id="currency_name" error={errors.name?.message} {...register("name")} />
        </div>
        <div>
          <Label htmlFor="currency_symbol">Symbol</Label>
          <Input id="currency_symbol" error={errors.symbol?.message} {...register("symbol")} />
        </div>
        <div>
          <Label htmlFor="currency_decimals">Decimals</Label>
          <Input
            id="currency_decimals"
            type="number"
            min={0}
            max={4}
            error={errors.minor_units?.message}
            {...register("minor_units")}
          />
        </div>
        <Button type="submit" disabled={createCurrency.isPending}>
          <Plus className="h-4 w-4" /> Add currency
        </Button>
      </form>
    </Card>
  );
}
