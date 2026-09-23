import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DataTable, type Column } from "./DataTable";

interface Row {
  id: number;
  name: string;
}

const columns: Column<Row>[] = [{ header: "Name", accessor: (row) => row.name }];

describe("DataTable", () => {
  it("shows a loading state instead of rows", () => {
    render(<DataTable columns={columns} rows={[]} keyExtractor={(row) => row.id} isLoading />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows an empty state when there are no rows", () => {
    render(
      <DataTable
        columns={columns}
        rows={[]}
        keyExtractor={(row) => row.id}
        emptyTitle="Nothing here"
      />
    );
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("renders a row per item and reacts to row clicks", () => {
    const onRowClick = vi.fn();
    render(
      <DataTable
        columns={columns}
        rows={[{ id: 1, name: "Widget" }]}
        keyExtractor={(row) => row.id}
        onRowClick={onRowClick}
      />
    );
    screen.getByText("Widget").closest("tr")?.click();
    expect(onRowClick).toHaveBeenCalledWith({ id: 1, name: "Widget" });
  });
});
