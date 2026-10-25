import type { ConvertInput } from "@/api/purchaseRequests";
import type { RequestLine } from "@/api/types";

export interface LineAssignment {
  included: boolean;
  supplierId: string;
  productId: string;
}

export type Assignments = Record<number, LineAssignment>;

export function isOrdered(line: RequestLine): boolean {
  return line.converted_po_id !== null;
}

export function initialAssignments(lines: readonly RequestLine[]): Assignments {
  return Object.fromEntries(
    lines.map((line) => [
      line.id,
      {
        included: !isOrdered(line),
        supplierId: line.supplier_id === null ? "" : String(line.supplier_id),
        productId: line.product_id === null ? "" : String(line.product_id),
      },
    ]),
  );
}

export interface LineErrors {
  supplier?: string;
  product?: string;
}

/** Errors by line id; an empty object means the choices can be sent. */
export function validateAssignments(
  lines: readonly RequestLine[],
  assignments: Assignments,
): Record<number, LineErrors> {
  const errors: Record<number, LineErrors> = {};
  for (const line of lines) {
    const choice = assignments[line.id];
    if (isOrdered(line) || !choice?.included) continue;
    if (choice.supplierId === "") errors[line.id] = { supplier: "Choose a supplier" };
    else if (line.product_id === null && choice.productId === "")
      errors[line.id] = { product: "Choose the product to order" };
  }
  return errors;
}

export function includedCount(lines: readonly RequestLine[], assignments: Assignments): number {
  return lines.filter((line) => !isOrdered(line) && assignments[line.id]?.included).length;
}

/** One order per supplier, in the order suppliers first appear. */
export function buildConvertInput(
  lines: readonly RequestLine[],
  assignments: Assignments,
  expectedDeliveryDate: string,
): ConvertInput {
  const bySupplier = new Map<number, ConvertInput["orders"][number]>();
  for (const line of lines) {
    const choice = assignments[line.id];
    if (isOrdered(line) || !choice?.included) continue;
    const supplierId = Number(choice.supplierId);
    const order = bySupplier.get(supplierId) ?? {
      supplier_id: supplierId,
      expected_delivery_date: expectedDeliveryDate === "" ? null : expectedDeliveryDate,
      lines: [],
    };
    order.lines = [
      ...order.lines,
      { line_id: line.id, product_id: line.product_id === null ? Number(choice.productId) : line.product_id },
    ];
    bySupplier.set(supplierId, order);
  }
  return { orders: [...bySupplier.values()] };
}
