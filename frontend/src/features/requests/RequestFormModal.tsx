import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { useEffect } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";

import { useCostCentres } from "@/api/budgets";
import { useCatalog } from "@/api/catalog";
import { useCurrencies } from "@/api/finance";
import type { PurchaseRequestInput } from "@/api/purchaseRequests";
import type { CatalogItem, PurchaseRequest } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";

import {
  EMPTY_LINE,
  EMPTY_REQUEST,
  requestFormSchema,
  toRequestInput,
  valuesFromRequest,
  type RequestFormValues,
} from "./requestForm";

interface RequestFormModalProps {
  isOpen: boolean;
  /** When given, the form edits this request instead of creating one. */
  request?: PurchaseRequest;
  isSubmitting: boolean;
  onClose: () => void;
  onSubmit: (input: PurchaseRequestInput) => Promise<void>;
}

export function RequestFormModal({ isOpen, request, isSubmitting, onClose, onSubmit }: RequestFormModalProps) {
  const { data: costCentres } = useCostCentres(true);
  const { data: currencies } = useCurrencies(true);
  const { data: catalog } = useCatalog({ active_only: true });
  const {
    register,
    control,
    handleSubmit,
    reset,
    setValue,
    getValues,
    formState: { errors },
  } = useForm<RequestFormValues>({ resolver: zodResolver(requestFormSchema), defaultValues: EMPTY_REQUEST });
  const { fields, append, remove } = useFieldArray({ control, name: "lines" });
  const watchedLines = useWatch({ control, name: "lines" });

  useEffect(() => {
    if (isOpen) reset(request ? valuesFromRequest(request) : EMPTY_REQUEST);
  }, [isOpen, request, reset]);

  const pickCatalogItem = (index: number, item: CatalogItem | undefined) => {
    const line = `lines.${index}` as const;
    setValue(`${line}.catalog_item_id`, item ? String(item.id) : "");
    setValue(`${line}.product_id`, item ? String(item.product_id) : "");
    setValue(`${line}.supplier_id`, item ? String(item.supplier_id) : "");
    if (!item) return;
    setValue(`${line}.estimated_unit_price`, item.contract_price);
    if (getValues(`${line}.description`).trim() === "") setValue(`${line}.description`, item.product_name);
  };

  const submit = handleSubmit(async (values) => {
    await onSubmit(toRequestInput(values));
  });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={request ? "Edit request" : "New request"} size="lg">
      <form onSubmit={(event) => void submit(event)} className="space-y-4" noValidate>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Label htmlFor="request_title" required>
              Title
            </Label>
            <Input id="request_title" error={errors.title?.message} {...register("title")} />
          </div>
          <div>
            <Label htmlFor="request_cost_centre">Cost centre</Label>
            <Select id="request_cost_centre" {...register("cost_centre_id")}>
              <option value="">None</option>
              {costCentres?.map((centre) => (
                <option key={centre.id} value={centre.id}>
                  {centre.code} — {centre.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="request_currency">Currency</Label>
            <Select id="request_currency" {...register("currency_code")}>
              <option value="">Company currency</option>
              {currencies?.map((currency) => (
                <option key={currency.code} value={currency.code}>
                  {currency.code} — {currency.name}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="request_needed_by">Needed by</Label>
            <Input id="request_needed_by" type="date" {...register("needed_by")} />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="request_notes">Notes</Label>
            <Textarea id="request_notes" rows={2} error={errors.notes?.message} {...register("notes")} />
          </div>
        </div>

        <fieldset>
          <legend className="mb-2 text-sm font-medium text-slate-700">Lines</legend>
          {errors.lines?.message && <p className="mb-2 text-xs text-red-600">{errors.lines.message}</p>}
          <div className="space-y-3">
            {fields.map((field, index) => {
              const n = index + 1;
              const lineErrors = errors.lines?.[index];
              return (
                <div
                  key={field.id}
                  className="grid grid-cols-6 items-start gap-2 rounded-md border border-slate-200 p-3"
                >
                  <div className="col-span-6">
                    <Select
                      aria-label={`Catalog item for line ${n}`}
                      value={watchedLines?.[index]?.catalog_item_id ?? ""}
                      onChange={(event) =>
                        pickCatalogItem(
                          index,
                          catalog?.find((item) => String(item.id) === event.target.value),
                        )
                      }
                    >
                      <option value="">Not from the catalog</option>
                      {catalog?.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.product_name} — {item.supplier_name} ({item.currency_code} {item.contract_price})
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div className="col-span-6 sm:col-span-3">
                    <Input
                      aria-label={`Description for line ${n}`}
                      placeholder="Description"
                      error={lineErrors?.description?.message}
                      {...register(`lines.${index}.description` as const)}
                    />
                  </div>
                  <div className="col-span-2 sm:col-span-1">
                    <Input
                      type="number"
                      aria-label={`Quantity for line ${n}`}
                      placeholder="Qty"
                      error={lineErrors?.quantity?.message}
                      {...register(`lines.${index}.quantity` as const)}
                    />
                  </div>
                  <div className="col-span-2 sm:col-span-1">
                    <Input
                      aria-label={`Unit for line ${n}`}
                      placeholder="Unit"
                      error={lineErrors?.unit?.message}
                      {...register(`lines.${index}.unit` as const)}
                    />
                  </div>
                  <div className="col-span-2 sm:col-span-1">
                    <Input
                      inputMode="decimal"
                      aria-label={`Estimated unit price for line ${n}`}
                      placeholder="Unit price"
                      error={lineErrors?.estimated_unit_price?.message}
                      {...register(`lines.${index}.estimated_unit_price` as const)}
                    />
                  </div>
                  <div className="col-span-6 flex justify-end">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      aria-label={`Remove line ${n}`}
                      onClick={() => remove(index)}
                      disabled={fields.length === 1}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
          <Button type="button" variant="secondary" size="sm" className="mt-2" onClick={() => append(EMPTY_LINE)}>
            <Plus className="h-3.5 w-3.5" /> Add line
          </Button>
        </fieldset>

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : request ? "Save changes" : "Save as draft"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
