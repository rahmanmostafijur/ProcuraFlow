import { useState } from "react";

import { useProducts } from "@/api/products";
import type { ConvertInput } from "@/api/purchaseRequests";
import { useSuppliers } from "@/api/suppliers";
import type { PurchaseRequest } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";

import {
  buildConvertInput,
  includedCount,
  initialAssignments,
  isOrdered,
  validateAssignments,
  type Assignments,
  type LineErrors,
} from "./convertRequest";

interface ConvertRequestModalProps {
  isOpen: boolean;
  request: PurchaseRequest;
  isSubmitting: boolean;
  onClose: () => void;
  onSubmit: (input: ConvertInput) => void;
}

export function ConvertRequestModal(props: ConvertRequestModalProps) {
  return (
    <Modal isOpen={props.isOpen} onClose={props.onClose} title="Create purchase orders" size="lg">
      <ConvertForm {...props} />
    </Modal>
  );
}

// Mounted only while the modal is open, so every opening starts from the request's own choices.
function ConvertForm({ request, isSubmitting, onClose, onSubmit }: ConvertRequestModalProps) {
  const { data: suppliers } = useSuppliers({ page: 1, page_size: 100, is_active: true });
  const { data: products } = useProducts({ page: 1, page_size: 100, is_active: true });
  const [assignments, setAssignments] = useState<Assignments>(() => initialAssignments(request.lines));
  const [expected, setExpected] = useState("");
  const [errors, setErrors] = useState<Record<number, LineErrors>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const change = (lineId: number, patch: Partial<Assignments[number]>) =>
    setAssignments((current) => ({ ...current, [lineId]: { ...current[lineId], ...patch } }));

  const submit = () => {
    const found = validateAssignments(request.lines, assignments);
    setErrors(found);
    if (includedCount(request.lines, assignments) === 0) {
      setFormError("Include at least one line");
      return;
    }
    setFormError(null);
    if (Object.keys(found).length > 0) return;
    onSubmit(buildConvertInput(request.lines, assignments, expected));
  };

  return (
    <form
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      className="space-y-4"
    >
      <p className="text-sm text-text-secondary">
        Lines with the same supplier go on one draft purchase order. A line typed in by hand needs the product to order.
      </p>
      <ul className="space-y-3">
        {request.lines.map((line, index) => {
          const n = index + 1;
          const ordered = isOrdered(line);
          const choice = assignments[line.id];
          return (
            <li key={line.id} className="space-y-2 rounded-control border border-border p-3">
              <label className="flex items-center gap-2 text-sm font-medium text-text-primary">
                <input
                  type="checkbox"
                  aria-label={`Include line ${n}`}
                  checked={choice?.included ?? false}
                  disabled={ordered}
                  onChange={(event) => change(line.id, { included: event.target.checked })}
                />
                {line.description} · {line.quantity} {line.unit}
                {ordered && <span className="text-xs font-normal text-text-secondary">(already ordered)</span>}
              </label>
              {!ordered && choice?.included && (
                <div className="grid gap-2 sm:grid-cols-2">
                  <Select
                    aria-label={`Supplier for line ${n}`}
                    value={choice.supplierId}
                    onChange={(event) => change(line.id, { supplierId: event.target.value })}
                    error={errors[line.id]?.supplier}
                  >
                    <option value="">Choose a supplier</option>
                    {suppliers?.items.map((supplier) => (
                      <option key={supplier.id} value={supplier.id}>
                        {supplier.name}
                      </option>
                    ))}
                  </Select>
                  {line.product_id === null && (
                    <Select
                      aria-label={`Product for line ${n}`}
                      value={choice.productId}
                      onChange={(event) => change(line.id, { productId: event.target.value })}
                      error={errors[line.id]?.product}
                    >
                      <option value="">Choose the product to order</option>
                      {products?.items.map((product) => (
                        <option key={product.id} value={product.id}>
                          {product.sku} — {product.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <div className="max-w-xs">
        <Label htmlFor="convert_expected">Expected delivery</Label>
        <Input
          id="convert_expected"
          type="date"
          value={expected}
          onChange={(event) => setExpected(event.target.value)}
        />
      </div>
      {formError && <p className="text-xs text-danger-fg">{formError}</p>}
      <div className="flex justify-end gap-3">
        <Button type="button" variant="secondary" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Creating…" : "Create purchase orders"}
        </Button>
      </div>
    </form>
  );
}
