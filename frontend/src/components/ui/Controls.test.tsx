import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Checkbox } from "./Checkbox";
import { RadioGroup } from "./Radio";
import { Switch } from "./Switch";

describe("Checkbox", () => {
  it("shows the mixed state through the indeterminate property", () => {
    render(<Checkbox label="Select all" indeterminate onChange={() => undefined} checked={false} />);
    expect(screen.getByRole<HTMLInputElement>("checkbox", { name: "Select all" }).indeterminate).toBe(true);
  });

  it("toggles and is labelled by its text", () => {
    const onChange = vi.fn();
    render(<Checkbox label="Remember me" onChange={onChange} />);
    fireEvent.click(screen.getByRole("checkbox", { name: "Remember me" }));
    expect(onChange).toHaveBeenCalled();
  });
});

describe("RadioGroup", () => {
  function Harness() {
    const [value, setValue] = useState("a");
    return (
      <RadioGroup
        legend="Delivery"
        value={value}
        onChange={setValue}
        options={[
          { value: "a", label: "Standard" },
          { value: "b", label: "Express", hint: "Next day" },
          { value: "c", label: "Pickup", disabled: true },
        ]}
      />
    );
  }

  it("is a labelled group with one checked option that follows selection", () => {
    render(<Harness />);
    expect(screen.getByRole("group", { name: "Delivery" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Standard/ })).toBeChecked();
    fireEvent.click(screen.getByRole("radio", { name: /Express/ }));
    expect(screen.getByRole("radio", { name: /Express/ })).toBeChecked();
    expect(screen.getByRole("radio", { name: /Standard/ })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "Pickup" })).toBeDisabled();
  });
});

describe("Switch", () => {
  function Harness({ disabled }: { disabled?: boolean }) {
    const [on, setOn] = useState(false);
    return <Switch label="Email alerts" hint="Sent daily" checked={on} onChange={setOn} disabled={disabled} />;
  }

  it("exposes role=switch with aria-checked and toggles", () => {
    render(<Harness />);
    const toggle = screen.getByRole("switch", { name: /Email alerts/ });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(toggle).toHaveAccessibleDescription("Sent daily");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("does not toggle when disabled", () => {
    render(<Harness disabled />);
    const toggle = screen.getByRole("switch");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "false");
  });
});
