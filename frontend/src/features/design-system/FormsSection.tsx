import { useState } from "react";

import { Checkbox } from "@/components/ui/Checkbox";
import { Combobox, type ComboboxOption } from "@/components/ui/Combobox";
import { DateRangePicker, type IsoDateRange } from "@/components/ui/DateRangePicker";
import { FORCED_FOCUS } from "@/components/ui/focus";
import { FormField } from "@/components/ui/FormField";
import { Input } from "@/components/ui/Input";
import { RadioGroup } from "@/components/ui/Radio";
import { Select } from "@/components/ui/Select";
import { Switch } from "@/components/ui/Switch";
import { Textarea } from "@/components/ui/Textarea";

import { alwaysFails, fetchSuppliers, neverResolves, SUPPLIERS } from "./mock-data";
import { Section, StateCell, SubHeading, ThemePair } from "./showcase";

const TODAY = new Date(2026, 9, 15);

function TextFields() {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <FormField label="Default" hint="Helper text sits under the field">
        <Input placeholder="Supplier name" />
      </FormField>
      <FormField label="Focus (forced)">
        <Input className={FORCED_FOCUS} defaultValue="Acme Supplies" />
      </FormField>
      <FormField label="Error" error="Enter a supplier name" required>
        <Input defaultValue="" />
      </FormField>
      <FormField label="Disabled">
        <Input disabled defaultValue="Locked by approval" />
      </FormField>
      <FormField label="Textarea" hint="Shown on the purchase order">
        <Textarea rows={3} placeholder="Delivery notes" />
      </FormField>
      <FormField label="Textarea error" error="Notes are limited to 500 characters">
        <Textarea rows={3} defaultValue="Too long" />
      </FormField>
      <FormField label="Select">
        <Select defaultValue="usd">
          <option value="usd">US dollar</option>
          <option value="eur">Euro</option>
        </Select>
      </FormField>
      <FormField label="Select error" error="Choose a currency">
        <Select defaultValue="">
          <option value="">Choose…</option>
          <option value="usd">US dollar</option>
        </Select>
      </FormField>
    </div>
  );
}

function Toggles() {
  const [radio, setRadio] = useState("net30");
  const [on, setOn] = useState(true);
  const [off, setOff] = useState(false);
  return (
    <div className="grid gap-6 sm:grid-cols-3">
      <div className="space-y-2">
        <SubHeading>Checkbox</SubHeading>
        <Checkbox label="Unchecked" />
        <br />
        <Checkbox label="Checked" defaultChecked />
        <br />
        <Checkbox label="Indeterminate" indeterminate onChange={() => undefined} checked={false} />
        <br />
        <Checkbox label="Disabled" disabled />
        <br />
        <Checkbox label="Focus (forced)" className={FORCED_FOCUS} />
      </div>
      <div className="space-y-2">
        <SubHeading>Radio</SubHeading>
        <RadioGroup
          legend="Payment terms"
          value={radio}
          onChange={setRadio}
          options={[
            { value: "net30", label: "Net 30" },
            { value: "net45", label: "Net 45", hint: "Needs Finance approval" },
            { value: "prepay", label: "Prepayment", disabled: true },
          ]}
        />
      </div>
      <div className="space-y-3">
        <SubHeading>Switch</SubHeading>
        <Switch label="On" checked={on} onChange={setOn} hint="Email me approvals" />
        <Switch label="Off" checked={off} onChange={setOff} />
        <Switch label="Disabled" checked={false} onChange={() => undefined} disabled />
        <Switch label="Focus (forced)" checked={on} onChange={setOn} className={FORCED_FOCUS} />
      </div>
    </div>
  );
}

function Comboboxes() {
  const [chosen, setChosen] = useState<ComboboxOption | null>(null);
  const [remote, setRemote] = useState<ComboboxOption | null>(null);
  const [none, setNone] = useState<ComboboxOption | null>(null);
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <FormField label="Static options">
        <Combobox value={chosen} onChange={setChosen} options={SUPPLIERS} placeholder="Search suppliers" />
      </FormField>
      <FormField label="Async (300 ms mock request)" hint="Type to search">
        <Combobox value={remote} onChange={setRemote} fetchOptions={fetchSuppliers} placeholder="Search suppliers" />
      </FormField>
      <StateCell label="Empty result">
        <Combobox
          aria-label="Empty example"
          value={none}
          onChange={setNone}
          options={[]}
          placeholder="Nothing to pick"
        />
      </StateCell>
      <StateCell label="Loading (click, request never ends)">
        <Combobox
          aria-label="Loading example"
          value={null}
          onChange={() => undefined}
          fetchOptions={neverResolves}
          placeholder="Click to load"
        />
      </StateCell>
      <StateCell label="Error (click)">
        <Combobox
          aria-label="Error example"
          value={null}
          onChange={() => undefined}
          fetchOptions={alwaysFails}
          placeholder="Click to fail"
        />
      </StateCell>
      <FormField label="Invalid" error="Pick a supplier">
        <Combobox value={null} onChange={() => undefined} options={SUPPLIERS} />
      </FormField>
      <StateCell label="Disabled">
        <Combobox aria-label="Disabled example" value={null} onChange={() => undefined} options={SUPPLIERS} disabled />
      </StateCell>
    </div>
  );
}

function DateRanges() {
  const [range, setRange] = useState<IsoDateRange>({ start: "2026-10-01", end: "2026-10-15" });
  const [empty, setEmpty] = useState<IsoDateRange>({ start: null, end: null });
  const [bad, setBad] = useState<IsoDateRange>({ start: null, end: null });
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <DateRangePicker label="Filled" value={range} onChange={setRange} today={TODAY} />
      <DateRangePicker label="Empty" value={empty} onChange={setEmpty} today={TODAY} />
      <DateRangePicker label="Try typing 2026-13-40" value={bad} onChange={setBad} today={TODAY} />
    </div>
  );
}

export function FormsSection() {
  return (
    <Section
      id="forms"
      title="Form controls"
      intro="Every control reads its id, hint and error wiring from FormField, so label, aria-describedby and aria-invalid are always set. Errors carry an icon and text, not only a red border."
    >
      <ThemePair>
        <div className="space-y-8">
          <TextFields />
          <Toggles />
          <div>
            <SubHeading>Combobox</SubHeading>
            <Comboboxes />
          </div>
          <div>
            <SubHeading>Date range picker</SubHeading>
            <DateRanges />
          </div>
        </div>
      </ThemePair>
    </Section>
  );
}
