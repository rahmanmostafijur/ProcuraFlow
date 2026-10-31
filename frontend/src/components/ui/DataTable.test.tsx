import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { DataTable, type Column, type RowKey } from "./DataTable";

interface Row {
  id: number;
  name: string;
  status: string;
  amount: number;
}

const columns: Column<Row>[] = [{ header: "Name", accessor: (row) => row.name }];

const DATA: Row[] = [
  { id: 1, name: "Charlie", status: "open", amount: 300 },
  { id: 2, name: "Alpha", status: "closed", amount: 100 },
  { id: 3, name: "Bravo", status: "open", amount: 200 },
  { id: 4, name: "Delta", status: "closed", amount: 400 },
  { id: 5, name: "Echo", status: "open", amount: 500 },
];

const richColumns: Column<Row>[] = [
  { header: "Name", accessor: (r) => r.name, sortValue: (r) => r.name, filterable: true, alwaysVisible: true },
  {
    header: "Status",
    accessor: (r) => r.status,
    filterable: true,
    filterOptions: [
      { value: "open", label: "Open" },
      { value: "closed", label: "Closed" },
    ],
    filterValue: (r) => r.status,
  },
  { header: "Amount", accessor: (r) => r.amount, sortValue: (r) => r.amount, isAmount: true },
];

const names = () =>
  within(screen.getAllByRole("rowgroup")[1])
    .getAllByRole("row")
    .map((row) => within(row).getAllByRole("cell")[0].textContent);

const bodyCell = () => within(screen.getAllByRole("rowgroup")[1]).getAllByRole("cell")[0];

describe("DataTable (legacy API)", () => {
  it("shows a loading state instead of rows", () => {
    render(<DataTable columns={columns} rows={[]} keyExtractor={(row) => row.id} isLoading />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows an empty state when there are no rows", () => {
    render(<DataTable columns={columns} rows={[]} keyExtractor={(row) => row.id} emptyTitle="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("renders a row per item and reacts to row clicks", () => {
    const onRowClick = vi.fn();
    render(<DataTable columns={columns} rows={[DATA[0]]} keyExtractor={(row) => row.id} onRowClick={onRowClick} />);
    screen.getByText("Charlie").closest("tr")?.click();
    expect(onRowClick).toHaveBeenCalledWith(DATA[0]);
  });
});

describe("DataTable", () => {
  it("sorts ascending, descending, then back to the original order, with aria-sort", () => {
    render(<DataTable caption="People" columns={richColumns} rows={DATA} keyExtractor={(r) => r.id} />);
    const header = screen.getByRole("columnheader", { name: /Name/ });
    expect(header).toHaveAttribute("aria-sort", "none");
    fireEvent.click(within(header).getByRole("button"));
    expect(header).toHaveAttribute("aria-sort", "ascending");
    expect(names()).toEqual(["Alpha", "Bravo", "Charlie", "Delta", "Echo"]);
    fireEvent.click(within(header).getByRole("button"));
    expect(header).toHaveAttribute("aria-sort", "descending");
    expect(names()[0]).toBe("Echo");
    fireEvent.click(within(header).getByRole("button"));
    expect(header).toHaveAttribute("aria-sort", "none");
    expect(names()[0]).toBe("Charlie");
    expect(screen.getByRole("columnheader", { name: "Status" })).not.toHaveAttribute("aria-sort");
  });

  it("sorts numbers numerically and right-aligns amounts", () => {
    render(<DataTable columns={richColumns} rows={DATA} keyExtractor={(r) => r.id} />);
    fireEvent.click(screen.getByRole("button", { name: /Amount/ }));
    expect(names()).toEqual(["Alpha", "Bravo", "Charlie", "Delta", "Echo"]);
    expect(screen.getByRole("columnheader", { name: /Amount/ }).className).toContain("text-right");
    expect(screen.getAllByRole("cell", { name: "100" })[0].className).toContain("text-right");
  });

  it("lets the parent sort when it controls the sort state", () => {
    const onSortChange = vi.fn();
    const serverColumns: Column<Row>[] = [{ header: "Name", accessor: (r) => r.name, sortable: true }];
    render(
      <DataTable
        columns={serverColumns}
        rows={DATA}
        keyExtractor={(r) => r.id}
        sort={null}
        onSortChange={onSortChange}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Name/ }));
    expect(onSortChange).toHaveBeenCalledWith({ columnId: "Name", direction: "asc" });
    expect(names()[0]).toBe("Charlie");
  });

  it("filters by text and by select, and clears the filters from the empty result", () => {
    render(<DataTable columns={richColumns} rows={DATA} keyExtractor={(r) => r.id} />);
    fireEvent.change(screen.getByRole("textbox", { name: "Filter Name" }), { target: { value: "a" } });
    expect(names()).toEqual(["Charlie", "Alpha", "Bravo", "Delta"]);
    fireEvent.change(screen.getByRole("combobox", { name: "Filter Status" }), { target: { value: "closed" } });
    expect(names()).toEqual(["Alpha", "Delta"]);
    fireEvent.change(screen.getByRole("textbox", { name: "Filter Name" }), { target: { value: "zzz" } });
    expect(screen.getByText("No matching records")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(names()).toHaveLength(5);
  });

  it("selects rows, selects all and shows the mixed state", () => {
    function Harness() {
      const [keys, setKeys] = useState<Set<RowKey>>(new Set());
      return (
        <DataTable
          columns={richColumns}
          rows={DATA}
          keyExtractor={(r) => r.id}
          selectable
          selectedKeys={keys}
          onSelectionChange={setKeys}
          rowLabel={(r) => r.name}
        />
      );
    }
    render(<Harness />);
    const all = screen.getByRole<HTMLInputElement>("checkbox", { name: "Select all rows" });
    fireEvent.click(screen.getByRole("checkbox", { name: "Select Alpha" }));
    expect(all.indeterminate).toBe(true);
    expect(all).not.toBeChecked();
    expect(screen.getByText("1 selected")).toBeInTheDocument();
    fireEvent.click(all);
    expect(all).toBeChecked();
    expect(screen.getByText("5 selected")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Select Echo" })).toBeChecked();
    fireEvent.click(all);
    expect(screen.queryByText(/selected/)).not.toBeInTheDocument();
  });

  it("does not trigger the row action when its checkbox is clicked", () => {
    const onRowClick = vi.fn();
    render(
      <DataTable columns={richColumns} rows={DATA} keyExtractor={(r) => r.id} selectable onRowClick={onRowClick} />,
    );
    fireEvent.click(screen.getByRole("checkbox", { name: "Select row 1" }));
    expect(onRowClick).not.toHaveBeenCalled();
  });

  it("pages client-side with Previous and Next", () => {
    render(<DataTable columns={richColumns} rows={DATA} keyExtractor={(r) => r.id} pageSize={2} />);
    expect(names()).toEqual(["Charlie", "Alpha"]);
    const nav = screen.getByRole("navigation", { name: "Pagination" });
    expect(within(nav).getByRole("button", { name: /Previous/ })).toBeDisabled();
    fireEvent.click(within(nav).getByRole("button", { name: /Next/ }));
    expect(names()).toEqual(["Bravo", "Delta"]);
    fireEvent.click(within(nav).getByRole("button", { name: /Next/ }));
    expect(names()).toEqual(["Echo"]);
    expect(within(nav).getByRole("button", { name: /Next/ })).toBeDisabled();
  });

  it("hides and shows columns from the column menu but keeps required ones", () => {
    render(<DataTable columns={richColumns} rows={DATA} keyExtractor={(r) => r.id} showColumnMenu />);
    fireEvent.click(screen.getByRole("button", { name: "Columns" }));
    const group = screen.getByRole("group", { name: "Visible columns" });
    expect(within(group).getByRole("checkbox", { name: "Name" })).toBeDisabled();
    fireEvent.click(within(group).getByRole("checkbox", { name: "Amount" }));
    expect(screen.queryByRole("columnheader", { name: /Amount/ })).not.toBeInTheDocument();
    fireEvent.click(within(group).getByRole("checkbox", { name: "Amount" }));
    expect(screen.getByRole("columnheader", { name: /Amount/ })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("group", { name: "Visible columns" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Columns" })).toHaveFocus();
  });

  it("toggles density", () => {
    render(<DataTable columns={richColumns} rows={DATA} keyExtractor={(r) => r.id} showDensityToggle />);
    const toggle = screen.getByRole("button", { name: /Comfortable rows/ });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    expect(bodyCell().className).toContain("py-3");
    fireEvent.click(toggle);
    expect(screen.getByRole("button", { name: /Compact rows/ })).toHaveAttribute("aria-pressed", "true");
    expect(bodyCell().className).toContain("py-1.5");
  });

  it("activates a row with Enter and Space on the row itself", () => {
    const onRowClick = vi.fn();
    render(<DataTable columns={richColumns} rows={DATA} keyExtractor={(r) => r.id} onRowClick={onRowClick} />);
    const row = screen.getByText("Alpha").closest("tr")!;
    expect(row).toHaveAttribute("tabindex", "0");
    fireEvent.keyDown(row, { key: "Enter" });
    fireEvent.keyDown(row, { key: " " });
    expect(onRowClick).toHaveBeenCalledTimes(2);
    expect(onRowClick).toHaveBeenCalledWith(DATA[1]);
  });

  it("makes the scroll region keyboard focusable and sticky when asked", () => {
    render(<DataTable caption="People" stickyHeader columns={richColumns} rows={DATA} keyExtractor={(r) => r.id} />);
    const region = screen.getByRole("region", { name: "People (scrollable)" });
    expect(region).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("columnheader", { name: /Name/ }).className).toContain("sticky");
  });

  it("renders skeleton rows with a status while loading", () => {
    render(<DataTable columns={richColumns} rows={[]} keyExtractor={(r) => r.id} isLoading />);
    expect(screen.getByRole("table")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows an error with a retry button", () => {
    const onRetry = vi.fn();
    render(
      <DataTable
        columns={richColumns}
        rows={[]}
        keyExtractor={(r) => r.id}
        error="Could not load orders"
        onRetry={onRetry}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load orders");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("announces the row count and sort", () => {
    render(<DataTable columns={richColumns} rows={DATA} keyExtractor={(r) => r.id} />);
    expect(screen.getByRole("status")).toHaveTextContent("5 rows");
    fireEvent.click(screen.getByRole("button", { name: /Name/ }));
    expect(screen.getByRole("status")).toHaveTextContent("5 rows, sorted by Name ascending");
  });
});
