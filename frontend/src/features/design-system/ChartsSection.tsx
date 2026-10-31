import { Card } from "@/components/ui/Card";
import { ThemedBarChart } from "@/components/ui/charts/ThemedBarChart";
import { ThemedDonutChart } from "@/components/ui/charts/ThemedDonutChart";
import { ThemedLineChart } from "@/components/ui/charts/ThemedLineChart";
import { formatCompactMoney, formatMoney } from "@/lib/format";

import { CATEGORIES, MONTHLY } from "./mock-data";
import { Section, ThemePair } from "./showcase";

const money = (value: number) => formatMoney(value);

export function ChartsSection() {
  return (
    <Section
      id="charts"
      title="Charts"
      intro="Series colours come from --chart-1..6, so the charts repaint with the theme. Lines also differ by dash, legends carry a marker, and a visually hidden table holds the numbers for screen readers. Hover a point for the custom tooltip."
    >
      <ThemePair>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card padding="md">
            <ThemedLineChart
              title="Spend against budget"
              description="Monthly, base currency"
              data={MONTHLY}
              xKey="month"
              series={[
                { key: "spend", label: "Spend" },
                { key: "budget", label: "Budget" },
              ]}
              formatValue={money}
            />
          </Card>
          <Card padding="md">
            <ThemedLineChart
              title="Committed spend"
              data={MONTHLY}
              xKey="month"
              series={[{ key: "committed", label: "Committed" }]}
              formatValue={money}
              area
            />
          </Card>
          <Card padding="md">
            <ThemedBarChart
              title="Spend and committed"
              description="Stacked"
              data={MONTHLY}
              xKey="month"
              series={[
                { key: "spend", label: "Spend" },
                { key: "committed", label: "Committed" },
              ]}
              formatValue={money}
              stacked
            />
          </Card>
          <Card padding="md">
            <ThemedDonutChart title="Spend by category" data={CATEGORIES} formatValue={(v) => formatCompactMoney(v)} />
          </Card>
        </div>
      </ThemePair>
    </Section>
  );
}
