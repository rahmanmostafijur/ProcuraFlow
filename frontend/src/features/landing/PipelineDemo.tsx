import { Pause, Play, SkipForward } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { KpiCard } from "@/components/ui/KpiCard";
import { LifecycleStepper } from "@/components/ui/LifecycleStepper";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatMoney } from "@/lib/format";

import { PIPELINE_STAGES, SAMPLE_LINES, SAMPLE_TOTALS, stepsFor } from "./pipeline-data";
import { usePrefersReducedMotion } from "./use-prefers-reduced-motion";

const STAGE_MS = 2200;

const money = (value: string | number) => formatMoney(value, SAMPLE_TOTALS.currency, SAMPLE_TOTALS.locale);

/**
 * The request-to-pay journey of one sample order, built from the same stepper, badge and KPI components the app
 * uses. It advances by itself unless the visitor prefers reduced motion or pauses it (WCAG 2.2.2).
 */
export function PipelineDemo() {
  const reducedMotion = usePrefersReducedMotion();
  const [stage, setStage] = useState(2);
  const [isPaused, setIsPaused] = useState(false);
  const isPlaying = !reducedMotion && !isPaused;

  useEffect(() => {
    if (!isPlaying) return;
    const timer = window.setInterval(() => setStage((s) => (s + 1) % PIPELINE_STAGES.length), STAGE_MS);
    return () => window.clearInterval(timer);
  }, [isPlaying]);

  const current = PIPELINE_STAGES[stage];

  return (
    <Card padding="lg" className="w-full space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-caption uppercase text-text-secondary">Sample order, request to paid</p>
        <div className="flex gap-2">
          {!reducedMotion && (
            <Button
              variant="secondary"
              size="sm"
              leadingIcon={
                isPlaying ? (
                  <Pause aria-hidden="true" className="h-4 w-4" />
                ) : (
                  <Play aria-hidden="true" className="h-4 w-4" />
                )
              }
              onClick={() => setIsPaused((paused) => !paused)}
            >
              {isPlaying ? "Pause" : "Play"}
            </Button>
          )}
          <Button
            variant="secondary"
            size="sm"
            leadingIcon={<SkipForward aria-hidden="true" className="h-4 w-4" />}
            onClick={() => setStage((s) => (s + 1) % PIPELINE_STAGES.length)}
          >
            Next step
          </Button>
        </div>
      </div>

      <LifecycleStepper steps={stepsFor(stage)} label="Sample order progress" />

      {/* Fixed height so the changing text never shifts the page. */}
      <div
        key={current.id}
        className="min-h-[13.5rem] space-y-3 rounded-card border border-border bg-bg p-4 motion-safe:animate-fade-in"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-cell text-text-secondary">
            {current.documentType} <span className="doc-number text-text-primary">{current.documentNumber}</span>
          </p>
          <StatusBadge status={current.status} />
        </div>
        <p className="text-cell text-text-secondary">{current.note}</p>
        <table className="w-full text-cell">
          <caption className="sr-only">Sample order lines</caption>
          <thead>
            <tr className="text-text-secondary">
              <th scope="col" className="text-left font-medium">
                Line
              </th>
              <th scope="col" className="text-right font-medium">
                Net
              </th>
              <th scope="col" className="text-right font-medium">
                Tax 20%
              </th>
            </tr>
          </thead>
          <tbody>
            {SAMPLE_LINES.map((line) => (
              <tr key={line.description}>
                <td>{line.description}</td>
                <td className="text-right">{money(line.net)}</td>
                <td className="text-right">{money(line.tax)}</td>
              </tr>
            ))}
            <tr className="border-t border-border font-semibold">
              <th scope="row" className="text-left">
                Total {money(SAMPLE_TOTALS.gross)}
              </th>
              <td className="text-right">{money(SAMPLE_TOTALS.net)}</td>
              <td className="text-right">{money(SAMPLE_TOTALS.tax)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <KpiCard label="Committed spend" value={money(current.committed)} hint="Open orders not yet paid" />
        <KpiCard label="Paid spend" value={money(current.paid)} hint="Released in payment runs" />
      </div>
    </Card>
  );
}
