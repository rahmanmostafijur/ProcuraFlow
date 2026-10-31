import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FormField } from "./FormField";
import { Input } from "./Input";
import { Select } from "./Select";
import { Textarea } from "./Textarea";

describe("FormField", () => {
  it("ties label, hint and error to the control", () => {
    render(
      <FormField label="Supplier name" hint="As printed on the invoice" error="Required" required>
        <Input />
      </FormField>,
    );
    const input = screen.getByLabelText(/Supplier name/);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("As printed on the invoice Required");
    expect(screen.getByRole("alert")).toHaveTextContent("Required");
  });

  it("is valid and undescribed without hint or error", () => {
    render(
      <FormField label="Notes">
        <Textarea />
      </FormField>,
    );
    const field = screen.getByLabelText("Notes");
    expect(field).not.toHaveAttribute("aria-invalid");
    expect(field).not.toHaveAttribute("aria-describedby");
  });

  it("works with a select", () => {
    render(
      <FormField label="Currency" error="Pick one">
        <Select>
          <option value="">Choose</option>
        </Select>
      </FormField>,
    );
    expect(screen.getByLabelText("Currency")).toHaveAttribute("aria-invalid", "true");
  });

  it("describes a standalone control that has its own error", () => {
    render(<Input aria-label="Amount" error="Must be positive" />);
    expect(screen.getByRole("textbox", { name: "Amount" })).toHaveAccessibleDescription("Must be positive");
  });
});
