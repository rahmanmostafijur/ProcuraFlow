import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { extractErrorMessage } from "@/api/client";
import { useCreateTaxRate, useTaxRates, useUpdateTaxRate } from "@/api/finance";
import type { TaxRate } from "@/api/types";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Select } from "@/components/ui/Select";
import { useToast } from "@/components/ui/toast-context";

const TAX_TYPE_LABELS = { vat: "VAT", sales_tax: "Sales tax" } as const;

const schema = z
  .object({
    name: z.string().trim().min(1, "Name is required").max(100),
    percentage: z
      .string()
      .trim()
      .regex(/^\d{1,3}(\.\d{1,4})?$/, "A percentage with up to 4 decimals")
      .refine((value) => Number(value) <= 100, "100 or less"),
    tax_type: z.enum(["vat", "sales_tax"]),
    treatment: z.enum(["exclusive", "inclusive", "reverse_charge"]),
    region: z.string().trim().max(10, "At most 10 characters"),
  })
  .refine((values) => values.treatment !== "reverse_charge" || Number(values.percentage) === 0, {
    path: ["percentage"],
    message: "Reverse charge is always 0%",
  });

type FormValues = z.infer<typeof schema>;

function treatmentLabel(rate: TaxRate): string {
  if (rate.is_reverse_charge) return "Reverse charge";
  return rate.is_inclusive ? "Included in price" : "Added on top";
}

export function TaxRatesSection() {
  const { showToast } = useToast();
  const { data: taxRates, isLoading } = useTaxRates();
  const createTaxRate = useCreateTaxRate();
  const updateTaxRate = useUpdateTaxRate();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", percentage: "", tax_type: "vat", treatment: "exclusive", region: "" },
  });

  const onSubmit = async (values: FormValues) => {
    try {
      await createTaxRate.mutateAsync({
        name: values.name,
        percentage: values.percentage,
        tax_type: values.tax_type,
        is_inclusive: values.treatment === "inclusive",
        is_reverse_charge: values.treatment === "reverse_charge",
        region: values.region || null,
      });
      reset();
      showToast("Tax rate added");
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const toggle = async (rate: TaxRate) => {
    try {
      await updateTaxRate.mutateAsync({ id: rate.id, is_active: !rate.is_active });
    } catch (error) {
      showToast(extractErrorMessage(error), "error");
    }
  };

  const columns: Column<TaxRate>[] = [
    { header: "Name", accessor: (row) => <span className="font-medium text-text-primary">{row.name}</span> },
    { header: "Rate", accessor: (row) => <span className="tabular-nums">{Number(row.percentage)}%</span> },
    { header: "Type", accessor: (row) => TAX_TYPE_LABELS[row.tax_type] },
    { header: "Treatment", accessor: treatmentLabel },
    { header: "Region", accessor: (row) => row.region ?? "—" },
    {
      header: "Status",
      accessor: (row) => (
        <StatusBadge status={row.is_active ? "active" : "inactive"} label={row.is_active ? "Active" : "Retired"} />
      ),
    },
    {
      header: "",
      accessor: (row) => (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-label={`${row.is_active ? "Retire" : "Reactivate"} ${row.name}`}
          onClick={() => void toggle(row)}
        >
          {row.is_active ? "Retire" : "Reactivate"}
        </Button>
      ),
    },
  ];

  return (
    <Card>
      <div className="border-b border-border p-4">
        <h2 className="text-base font-semibold text-text-primary">Tax rates</h2>
        <p className="text-sm text-text-secondary">
          The examples are starting points, not tax advice. A purchase order line keeps the rate it was priced with, so
          editing or retiring a rate never changes existing orders.
        </p>
      </div>
      <DataTable columns={columns} rows={taxRates ?? []} keyExtractor={(row) => row.id} isLoading={isLoading} />
      <form
        onSubmit={(event) => void handleSubmit(onSubmit)(event)}
        className="grid gap-3 border-t border-border p-4 sm:grid-cols-6 sm:items-end"
      >
        <div className="sm:col-span-2">
          <Label htmlFor="tax_name">Tax rate name</Label>
          <Input id="tax_name" error={errors.name?.message} {...register("name")} />
        </div>
        <div>
          <Label htmlFor="tax_percentage">Rate (%)</Label>
          <Input
            id="tax_percentage"
            inputMode="decimal"
            error={errors.percentage?.message}
            {...register("percentage")}
          />
        </div>
        <div>
          <Label htmlFor="tax_type">Type</Label>
          <Select id="tax_type" {...register("tax_type")}>
            <option value="vat">VAT</option>
            <option value="sales_tax">Sales tax</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="tax_treatment">Treatment</Label>
          <Select id="tax_treatment" {...register("treatment")}>
            <option value="exclusive">Added on top</option>
            <option value="inclusive">Included in price</option>
            <option value="reverse_charge">Reverse charge</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="tax_region">Region</Label>
          <Input id="tax_region" placeholder="e.g. DE" error={errors.region?.message} {...register("region")} />
        </div>
        <div className="sm:col-span-6 sm:flex sm:justify-end">
          <Button type="submit" disabled={createTaxRate.isPending}>
            <Plus className="h-4 w-4" /> Add tax rate
          </Button>
        </div>
      </form>
    </Card>
  );
}
