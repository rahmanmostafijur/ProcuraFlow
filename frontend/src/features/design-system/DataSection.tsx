import { useState } from "react";

import { Card } from "@/components/ui/Card";
import { type Column, DataTable, type Density, type RowKey } from "@/components/ui/DataTable";
import { KpiCard } from "@/components/ui/KpiCard";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { STATUS_TONES } from "@/components/ui/status-tones";
import { formatCompactMoney, formatDate, formatMoney } from "@/lib/format";

import { ORDERS, type OrderRow, TREND_DOWN, TREND_UP } from "./mock-data";
import { Section, SubHeading, ThemePair } from "./showcase";

const columns: Column<OrderRow>[] = [
  {
    header: "Order",
    accessor: (row) => <span className="doc-number">{row.number}</span>,
    sortValue: (row) => row.number,
    filterable: true,
    alwaysVisible: true,
  },
  { header: "Supplier", accessor: (row) => row.supplier, sortValue: (row) => row.supplier, filterable: true },
  {
    header: "Status",
    accessor: (row) => <StatusBadge status={row.status} />,
    filterable: true,
    filterOptions: Object.keys(STATUS_TONES)
      .filter((status) => ORDERS.some((order) => order.status === status))
      .map((status) => ({ value: status, label: status.replace(/_/g, " ") })),
    filterValue: (row) => row.status,
  },
  { header: "Date", accessor: (row) => formatDate(row.date), sortValue: (row) => row.date, defaultHidden: true },
  {
    header: "Amount",
    accessor: (row) => formatMoney(row.amount),
    sortValue: (row) => Number(row.amount),
    isAmount: true,
  },
];

function FullTable() {
  const [selected, setSelected] = useState<Set<RowKey>>(new Set());
  const [density, setDensity] = useState<Density>("comfortable");
  const [clicked, setClicked] = useState<string | null>(null);
  return (
    <Card>
      <DataTable
        caption="Purchase orders"
        columns={columns}
        rows={ORDERS}
        keyExtractor={(row) => row.id}
        selectable
        selectedKeys={selected}
        onSelectionChange={setSelected}
        rowLabel={(row) => row.number}
        pageSize={5}
        stickyHeader
        maxHeightClass="max-h-96"
        showColumnMenu
        showDensityToggle
        density={density}
        onDensityChange={setDensity}
        onRowClick={(row) => setClicked(row.number)}
      />
      <p aria-live="polite" className="border-t border-border px-4 py-2 text-xs text-text-secondary">
        {clicked ? `Last opened: ${clicked}` : "Click or press Enter on a row to open it."}
      </p>
    </Card>
  );
}

function TableStates() {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card>
        <SubHeading>Loading</SubHeading>
        <DataTable
          caption="Loading example"
          columns={columns.slice(0, 3)}
          rows={[]}
          keyExtractor={(r) => r.id}
          isLoading
        />
      </Card>
      <Card>
        <SubHeading>Empty</SubHeading>
        <DataTable
          columns={columns}
          rows={[]}
          keyExtractor={(r) => r.id}
          emptyTitle="No purchase orders"
          emptyDescription="Orders you create will show up here."
          emptyIllustration="orders"
        />
      </Card>
      <Card>
        <SubHeading>Error</SubHeading>
        <DataTable
          columns={columns}
          rows={[]}
          keyExtractor={(r) => r.id}
          error="Could not load purchase orders."
          onRetry={() => undefined}
        />
      </Card>
    </div>
  );
}

function Badges() {
  return (
    <div className="flex flex-wrap gap-2">
      {Object.keys(STATUS_TONES).map((status) => (
        <StatusBadge key={status} status={status} />
      ))}
      <StatusBadge status="not-in-the-map" />
    </div>
  );
}

function Kpis() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <KpiCard
        label="Spend this month"
        value={formatCompactMoney(1284000)}
        exactValue={formatMoney(1284000)}
        delta={12.5}
        goodWhen="down"
        trend={TREND_UP}
        hint="of $1.5M budget"
      />
      <KpiCard label="Open requests" value="38" delta={-8.1} goodWhen="down" trend={TREND_DOWN} />
      <KpiCard label="Approvals waiting" value="7" delta={0} />
      <KpiCard label="Loading" value="x" isLoading />
    </div>
  );
}

export function DataSection() {
  return (
    <Section
      id="data"
      title="Status, KPIs and data table"
      intro="Badges always carry a word and an icon. KPI deltas say up or down and whether it is favourable in words. The table adds sorting, filters, column visibility, selection, paging and density."
    >
      <ThemePair>
        <div className="space-y-8">
          <div>
            <SubHeading>Status badges</SubHeading>
            <Badges />
          </div>
          <div>
            <SubHeading>KPI cards with sparkline</SubHeading>
            <Kpis />
          </div>
          <div>
            <SubHeading>Data table (sort, filter, select, columns, density, sticky header, pages)</SubHeading>
            <FullTable />
          </div>
          <div>
            <SubHeading>Table states</SubHeading>
            <TableStates />
          </div>
        </div>
      </ThemePair>
    </Section>
  );
}
