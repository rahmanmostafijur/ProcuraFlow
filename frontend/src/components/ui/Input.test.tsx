import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Input } from "./Input";

describe("Input", () => {
  it("keeps browsers from autofilling business-record fields by default", () => {
    render(<Input aria-label="Supplier name" />);

    expect(screen.getByRole("textbox", { name: "Supplier name" })).toHaveAttribute("autocomplete", "off");
  });

  it("lets a caller opt into autofill, as the sign-in form does", () => {
    render(<Input aria-label="Email" autoComplete="username" />);

    expect(screen.getByRole("textbox", { name: "Email" })).toHaveAttribute("autocomplete", "username");
  });
});
